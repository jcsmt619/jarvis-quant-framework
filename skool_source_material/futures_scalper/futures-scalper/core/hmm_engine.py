"""Intraday volatility-regime engine built on a Gaussian HMM.

Two design choices carry over from the stock template and matter a lot here.

First, regime detection uses the forward algorithm (filtered inference), never
``model.predict``. predict runs Viterbi over the whole sequence and revises past
states using future bars, which is look-ahead bias that flatters a backtest. The
forward pass uses only bars up to and including the current one, so the regime
printed at a given bar never changes when more data arrives. ``test_look_ahead``
enforces this.

Second, regimes are sorted and labelled by volatility, not by return. For
intraday futures the useful question is "how violent is the tape right now",
which decides position size and which playbook to run. Expected return per
regime is still stored so the scalping engine can read a directional lean.
"""

from __future__ import annotations

import pickle
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM


# Volatility-ordered labels (quiet -> violent). Sorted ascending by vol.
REGIME_LABEL_SCHEMES: dict[int, list[str]] = {
    2: ["QUIET", "VOLATILE"],
    3: ["QUIET", "NORMAL", "VOLATILE"],
    4: ["QUIET", "NORMAL", "ACTIVE", "VOLATILE"],
    5: ["QUIET", "NORMAL", "ACTIVE", "VOLATILE", "EXTREME"],
    6: ["DEAD", "QUIET", "NORMAL", "ACTIVE", "VOLATILE", "EXTREME"],
}


@dataclass
class RegimeInfo:
    regime_id: int            # index after sorting by volatility (0 = quietest)
    regime_name: str
    expected_return: float
    expected_volatility: float
    vol_rank: float           # 0.0 (quietest) .. 1.0 (most volatile)


@dataclass
class RegimeState:
    label: str
    state_id: int
    probability: float
    state_probabilities: np.ndarray
    timestamp: Optional[pd.Timestamp]
    is_confirmed: bool = True
    consecutive_bars: int = 1


@dataclass
class TrainingMetrics:
    n_regimes_selected: int
    bic_scores: dict[int, float]
    log_likelihood: float
    converged: bool
    n_iterations: int
    n_samples: int
    n_features: int
    training_time_seconds: float
    timestamp: pd.Timestamp = field(default_factory=lambda: pd.Timestamp.now(tz="UTC"))


class HMMEngine:
    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.n_candidates = list(cfg.get("n_candidates", [3, 4, 5]))
        self.n_init = int(cfg.get("n_init", 8))
        self.covariance_type = cfg.get("covariance_type", "full")
        self.n_iter = int(cfg.get("n_iter", 150))
        self.random_state = int(cfg.get("random_state", 42))
        self.min_train_bars = int(cfg.get("min_train_bars", 300))
        self.stability_bars = int(cfg.get("stability_bars", 2))
        self.flicker_window = int(cfg.get("flicker_window", 20))
        self.flicker_threshold = int(cfg.get("flicker_threshold", 5))

        self._model: Optional[GaussianHMM] = None
        self._feature_cols: list[str] = []
        self._raw_to_sorted: dict[int, int] = {}
        self._sorted_to_raw: dict[int, int] = {}
        self._regime_infos: list[RegimeInfo] = []
        self._metrics: Optional[TrainingMetrics] = None

        # Live stability tracking.
        self._confirmed_sorted: Optional[int] = None
        self._pending_sorted: Optional[int] = None
        self._pending_count: int = 0
        self._consecutive: int = 0
        self._recent_changes: deque[int] = deque(maxlen=self.flicker_window)
        self._last_sorted: Optional[int] = None

    # -- properties --------------------------------------------------------
    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    @property
    def n_regimes(self) -> int:
        return 0 if self._model is None else self._model.n_components

    @property
    def regime_infos(self) -> list[RegimeInfo]:
        return list(self._regime_infos)

    @property
    def last_training_metrics(self) -> Optional[TrainingMetrics]:
        return self._metrics

    # -- training ----------------------------------------------------------
    def fit(self, features: pd.DataFrame) -> TrainingMetrics:
        if len(features) < self.min_train_bars:
            raise ValueError(
                f"need >= {self.min_train_bars} feature rows to fit, got {len(features)}")
        self._feature_cols = list(features.columns)
        X = features.to_numpy(dtype=float)

        t0 = time.time()
        best_model, best_bic, best_n = None, np.inf, None
        bic_scores: dict[int, float] = {}
        for n in self.n_candidates:
            model, bic = self._fit_single(X, n)
            if model is None:
                continue
            bic_scores[n] = bic
            if bic < best_bic:
                best_model, best_bic, best_n = model, bic, n

        if best_model is None:
            raise RuntimeError("HMM failed to fit for every candidate regime count")

        self._model = best_model
        self._build_label_maps(features)
        self.reset_tracking()

        self._metrics = TrainingMetrics(
            n_regimes_selected=best_n,
            bic_scores=bic_scores,
            log_likelihood=float(best_model.score(X)),
            converged=bool(getattr(best_model.monitor_, "converged", False)),
            n_iterations=int(getattr(best_model.monitor_, "iter", 0)),
            n_samples=X.shape[0],
            n_features=X.shape[1],
            training_time_seconds=time.time() - t0,
            timestamp=pd.Timestamp.now(tz="UTC"),
        )
        return self._metrics

    def _fit_single(self, X: np.ndarray, n: int):
        try:
            model = GaussianHMM(
                n_components=n,
                covariance_type=self.covariance_type,
                n_iter=self.n_iter,
                random_state=self.random_state,
                init_params="stmc",
            )
            model.n_init = self.n_init  # informational only
            best, best_ll = None, -np.inf
            for seed in range(self.n_init):
                m = GaussianHMM(
                    n_components=n, covariance_type=self.covariance_type,
                    n_iter=self.n_iter, random_state=self.random_state + seed,
                )
                m.fit(X)
                ll = m.score(X)
                if np.isfinite(ll) and ll > best_ll:
                    best, best_ll = m, ll
            if best is None:
                return None, np.inf
            n_params = self._count_params(n, X.shape[1])
            bic = -2 * best_ll + n_params * np.log(X.shape[0])
            return best, bic
        except Exception:
            return None, np.inf

    def _count_params(self, n: int, n_features: int) -> int:
        start = n - 1
        trans = n * (n - 1)
        means = n * n_features
        if self.covariance_type == "full":
            cov = n * n_features * (n_features + 1) // 2
        elif self.covariance_type == "diag":
            cov = n * n_features
        elif self.covariance_type == "tied":
            cov = n_features * (n_features + 1) // 2
        else:
            cov = n
        return start + trans + means + cov

    def _build_label_maps(self, features: pd.DataFrame) -> None:
        """Sort raw HMM states by realized volatility and assign vol labels."""
        X = features.to_numpy(dtype=float)
        raw_states = self._model.predict(X)  # in-sample labelling only; fine here
        # Use the realized-vol feature if present, else mean abs of all features.
        if "rvol_20" in features.columns:
            vol_signal = features["rvol_20"].to_numpy()
        else:
            vol_signal = np.nanmean(np.abs(X), axis=1)
        ret_signal = features["ret_1"].to_numpy() if "ret_1" in features.columns else np.zeros(len(X))

        per_state_vol, per_state_ret = {}, {}
        for s in range(self._model.n_components):
            mask = raw_states == s
            per_state_vol[s] = float(np.nanmean(vol_signal[mask])) if mask.any() else 0.0
            per_state_ret[s] = float(np.nanmean(ret_signal[mask])) if mask.any() else 0.0

        order = sorted(per_state_vol, key=lambda s: per_state_vol[s])  # ascending vol
        self._raw_to_sorted = {raw: i for i, raw in enumerate(order)}
        self._sorted_to_raw = {i: raw for i, raw in enumerate(order)}

        n = self._model.n_components
        labels = REGIME_LABEL_SCHEMES.get(n, [f"R{i}" for i in range(n)])
        infos = []
        for i, raw in enumerate(order):
            infos.append(RegimeInfo(
                regime_id=i,
                regime_name=labels[i],
                expected_return=per_state_ret[raw],
                expected_volatility=per_state_vol[raw],
                vol_rank=i / (n - 1) if n > 1 else 0.0,
            ))
        self._regime_infos = infos

    # -- filtered (no look-ahead) inference --------------------------------
    def _emission_logprob(self, X: np.ndarray) -> np.ndarray:
        return self._model._compute_log_likelihood(X)

    def _forward_pass(self, framelogprob: np.ndarray) -> np.ndarray:
        """Log-space forward algorithm. Returns filtered posteriors per bar.

        alpha_t depends only on observations 0..t, which is exactly why the
        regime at t does not change when future bars are appended.
        """
        T, n = framelogprob.shape
        log_startprob = np.log(self._model.startprob_ + 1e-300)
        log_transmat = np.log(self._model.transmat_ + 1e-300)
        log_alpha = np.empty((T, n))
        log_alpha[0] = log_startprob + framelogprob[0]
        for t in range(1, T):
            for j in range(n):
                log_alpha[t, j] = _logsumexp(log_alpha[t - 1] + log_transmat[:, j]) + framelogprob[t, j]
        # Normalise each row to a posterior distribution.
        log_norm = _logsumexp_rows(log_alpha)
        posterior = np.exp(log_alpha - log_norm[:, None])
        return posterior

    def filtered_posteriors(self, features: pd.DataFrame) -> np.ndarray:
        """Per-bar filtered posterior over sorted regimes (rows sum to 1)."""
        self._require_fitted()
        X = features[self._feature_cols].to_numpy(dtype=float)
        raw_post = self._forward_pass(self._emission_logprob(X))
        return self._reorder_columns(raw_post)

    def predict_regime_filtered(self, features: pd.DataFrame) -> RegimeState:
        """Filtered regime at the LAST bar, with stability filtering applied."""
        self._require_fitted()
        post = self.filtered_posteriors(features)
        last = post[-1]
        sorted_id = int(np.argmax(last))
        confirmed_id, is_confirmed, consec = self._update_stability(sorted_id)
        ts = features.index[-1] if len(features.index) else None
        eff_id = confirmed_id if confirmed_id is not None else sorted_id
        return RegimeState(
            label=self._label_for(eff_id),
            state_id=eff_id,
            probability=float(last[eff_id]),
            state_probabilities=last,
            timestamp=ts,
            is_confirmed=is_confirmed,
            consecutive_bars=consec,
        )

    def _reorder_columns(self, raw_post: np.ndarray) -> np.ndarray:
        out = np.empty_like(raw_post)
        for raw, srt in self._raw_to_sorted.items():
            out[:, srt] = raw_post[:, raw]
        return out

    # -- stability / flicker ----------------------------------------------
    def _update_stability(self, sorted_id: int):
        if self._last_sorted is not None and sorted_id != self._last_sorted:
            self._recent_changes.append(1)
        else:
            self._recent_changes.append(0)
        self._last_sorted = sorted_id

        if self._confirmed_sorted is None:
            self._confirmed_sorted = sorted_id
            self._consecutive = 1
            return self._confirmed_sorted, True, self._consecutive

        if sorted_id == self._confirmed_sorted:
            self._consecutive += 1
            self._pending_sorted, self._pending_count = None, 0
            return self._confirmed_sorted, True, self._consecutive

        # Different from confirmed: count persistence before switching.
        if sorted_id == self._pending_sorted:
            self._pending_count += 1
        else:
            self._pending_sorted, self._pending_count = sorted_id, 1

        if self._pending_count >= self.stability_bars:
            self._confirmed_sorted = sorted_id
            self._consecutive = self._pending_count
            self._pending_sorted, self._pending_count = None, 0
            return self._confirmed_sorted, True, self._consecutive

        # Still in transition: hold previous confirmed regime, flag unconfirmed.
        return self._confirmed_sorted, False, self._consecutive

    def get_regime_flicker_rate(self) -> float:
        if not self._recent_changes:
            return 0.0
        return float(sum(self._recent_changes))

    def is_flickering(self) -> bool:
        return self.get_regime_flicker_rate() > self.flicker_threshold

    def get_regime_stability(self) -> int:
        return self._consecutive

    def get_transition_matrix(self) -> np.ndarray:
        self._require_fitted()
        n = self._model.n_components
        out = np.zeros((n, n))
        for ri in range(n):
            for rj in range(n):
                out[self._raw_to_sorted[ri], self._raw_to_sorted[rj]] = self._model.transmat_[ri, rj]
        return out

    def reset_tracking(self) -> None:
        self._confirmed_sorted = None
        self._pending_sorted = None
        self._pending_count = 0
        self._consecutive = 0
        self._last_sorted = None
        self._recent_changes = deque(maxlen=self.flicker_window)

    # -- persistence -------------------------------------------------------
    def save(self, path: str | Path) -> None:
        self._require_fitted()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "model": self._model,
            "feature_cols": self._feature_cols,
            "raw_to_sorted": self._raw_to_sorted,
            "sorted_to_raw": self._sorted_to_raw,
            "regime_infos": self._regime_infos,
            "metrics": self._metrics,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_bytes(pickle.dumps(blob))

    def load(self, path: str | Path) -> None:
        blob = pickle.loads(Path(path).read_bytes())
        self._model = blob["model"]
        self._feature_cols = blob["feature_cols"]
        self._raw_to_sorted = blob["raw_to_sorted"]
        self._sorted_to_raw = blob["sorted_to_raw"]
        self._regime_infos = blob["regime_infos"]
        self._metrics = blob.get("metrics")
        self.reset_tracking()

    # -- helpers -----------------------------------------------------------
    def get_regime_info(self, sorted_id: int) -> RegimeInfo:
        return self._regime_infos[sorted_id]

    def _label_for(self, sorted_id: int) -> str:
        return self._regime_infos[sorted_id].regime_name

    def _require_fitted(self) -> None:
        if self._model is None:
            raise RuntimeError("HMMEngine is not fitted. Call fit() or load() first.")


# --------------------------------------------------------------------------
# Numerically stable log-sum-exp helpers
# --------------------------------------------------------------------------

def _logsumexp(v: np.ndarray) -> float:
    m = np.max(v)
    if not np.isfinite(m):
        return -np.inf
    return float(m + np.log(np.sum(np.exp(v - m))))


def _logsumexp_rows(a: np.ndarray) -> np.ndarray:
    m = np.max(a, axis=1, keepdims=True)
    return (m[:, 0] + np.log(np.sum(np.exp(a - m), axis=1)))
