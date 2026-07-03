"""
core/hmm_engine.py
==================
HMM Regime Detection Engine (STEP 2 - AI Pathways Automated Trading Foundations).

The HMM is a VOLATILITY CLASSIFIER, not a price predictor. It clusters 14
standardized market features into latent regimes and reports, at each bar, the
FILTERED distribution P(state_t | obs_1:t) -- using a hand-rolled forward
algorithm so it never peeks at future data.

Faithful to the lesson spec:
  1. Gaussian HMM (covariance_type="full") with automatic model selection over
     n_components in {3,4,5,6,7} via BIC, n_init random restarts per candidate.
  2. Regimes labelled by ascending mean return for human readability; the
     strategy layer is free to sort by volatility independently.
  3. Regime inference uses the FORWARD ALGORITHM ONLY (filtered), never
     model.predict()/Viterbi (which revises the past using the future).
  4. Regime-stability confirmation + flicker detection.
  5. RegimeInfo / RegimeState metadata.

Look-ahead guarantee: predict_regime_filtered(X)[t] depends only on X[:t+1].
Appending future rows cannot change earlier filtered states. This is what
tests/test_look_ahead.py verifies.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

logger = logging.getLogger("hmm_engine")

_TINY = 1e-12


# ---------------------------------------------------------------------------
# Metadata dataclasses
# ---------------------------------------------------------------------------
@dataclass
class RegimeInfo:
    regime_id: int
    regime_name: str
    expected_return: float
    expected_volatility: float
    recommended_strategy_type: str
    max_leverage_allowed: float
    max_position_size_pct: float
    min_confidence_to_act: float


@dataclass
class RegimeState:
    label: str
    state_id: int
    probability: float
    state_probabilities: np.ndarray
    timestamp: datetime | None = None
    is_confirmed: bool = False
    consecutive_bars: int = 0


# Label schemes keyed by regime count, ordered by ASCENDING mean return.
_LABEL_SCHEMES: dict[int, list[str]] = {
    3: ["BEAR", "NEUTRAL", "BULL"],
    4: ["CRASH", "BEAR", "BULL", "EUPHORIA"],
    5: ["CRASH", "BEAR", "NEUTRAL", "BULL", "EUPHORIA"],
    6: ["CRASH", "STRONG_BEAR", "WEAK_BEAR", "WEAK_BULL", "STRONG_BULL", "EUPHORIA"],
    7: ["CRASH", "STRONG_BEAR", "WEAK_BEAR", "NEUTRAL", "WEAK_BULL", "STRONG_BULL", "EUPHORIA"],
}


class HMMRegimeEngine:
    def __init__(
        self,
        n_candidates: list[int] | None = None,
        n_init: int = 10,
        covariance_type: str = "full",
        min_train_bars: int = 504,
        stability_bars: int = 3,
        flicker_window: int = 20,
        flicker_threshold: int = 4,
        min_confidence: float = 0.55,
        n_iter: int = 100,
        random_state: int = 42,
    ):
        self.n_candidates = n_candidates or [3, 4, 5, 6, 7]
        self.n_init = n_init
        self.covariance_type = covariance_type
        self.min_train_bars = min_train_bars
        self.stability_bars = stability_bars
        self.flicker_window = flicker_window
        self.flicker_threshold = flicker_threshold
        self.min_confidence = min_confidence
        self.n_iter = n_iter
        self.random_state = random_state

        # Learned artefacts.
        self.model: GaussianHMM | None = None
        self.n_regimes: int | None = None
        self.bic: float | None = None
        self.bic_scores: dict[int, float] = {}
        self.training_date: datetime | None = None
        self.vol_sorted_ids: list[int] = []          # regime ids, low -> high vol
        self.regime_info: dict[int, RegimeInfo] = {}  # keyed by state_id

        # Live filtered-inference state.
        self._last_log_alpha: np.ndarray | None = None
        self._history: list[int] = []                 # confirmed-regime history
        self._raw_history: list[int] = []             # raw argmax history (flicker)
        self._active_regime: int | None = None
        self._pending_regime: int | None = None
        self._pending_count: int = 0
        self._consecutive: int = 0

    # ------------------------------------------------------------------
    # BIC helpers
    # ------------------------------------------------------------------
    def _n_params(self, k: int, d: int) -> int:
        """Free parameters for a full-covariance Gaussian HMM with k states, d dims."""
        start = k - 1
        trans = k * (k - 1)
        means = k * d
        covars = k * d * (d + 1) // 2
        return start + trans + means + covars

    def _bic(self, log_likelihood: float, k: int, d: int, n_samples: int) -> float:
        # BIC = -2 * logL + n_params * log(n_samples)
        return -2.0 * log_likelihood + self._n_params(k, d) * np.log(n_samples)

    def _fit_candidate(self, X: np.ndarray, k: int) -> tuple[GaussianHMM | None, float]:
        """Fit k-state HMM with n_init restarts; return (best_model, best_logL)."""
        best_model, best_ll = None, -np.inf
        for seed in range(self.n_init):
            model = GaussianHMM(
                n_components=k,
                covariance_type=self.covariance_type,
                n_iter=self.n_iter,
                random_state=self.random_state + seed,
            )
            try:
                model.fit(X)
                ll = model.score(X)
            except Exception as exc:  # convergence / singular covariance
                logger.debug("candidate k=%d seed=%d failed: %s", k, seed, exc)
                continue
            if np.isfinite(ll) and ll > best_ll:
                best_model, best_ll = model, ll
        return best_model, best_ll

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def train(self, features: pd.DataFrame, returns: pd.Series | None = None) -> "HMMRegimeEngine":
        X = np.asarray(features, dtype=float)
        if len(X) < self.min_train_bars:
            raise ValueError(f"Need >= {self.min_train_bars} bars to train; got {len(X)}")
        n_samples, d = X.shape

        best = None  # (bic, k, model, ll)
        for k in self.n_candidates:
            model, ll = self._fit_candidate(X, k)
            if model is None:
                logger.warning("No converging fit for k=%d; skipping", k)
                continue
            bic = self._bic(ll, k, d, n_samples)
            self.bic_scores[k] = bic
            logger.info("candidate k=%d  logL=%.2f  BIC=%.2f", k, ll, bic)
            if best is None or bic < best[0]:
                best = (bic, k, model, ll)

        if best is None:
            raise RuntimeError("HMM training failed for every candidate")

        self.bic, self.n_regimes, self.model, _ = best
        self.training_date = datetime.now(timezone.utc)
        logger.info(
            "Selected k=%d (lowest BIC=%.2f of %s)",
            self.n_regimes, self.bic, {kk: round(v, 1) for kk, v in self.bic_scores.items()},
        )

        self._build_regime_metadata(X, features.index, returns)
        # Reset live state so post-training inference starts clean.
        self.reset_state()
        return self

    def _build_regime_metadata(self, X: np.ndarray, index, returns: pd.Series | None) -> None:
        states = self._filtered_states(X)
        k = self.n_regimes

        # Per-regime realized return + volatility (for labelling + strategy ranking).
        if returns is not None:
            ret_aligned = pd.Series(returns).reindex(index).to_numpy(dtype=float)
        else:
            ret_aligned = np.full(len(states), np.nan)

        mean_ret = np.zeros(k)
        vol = np.zeros(k)
        downside = np.zeros(k)
        for sid in range(k):
            mask = states == sid
            if mask.any() and np.isfinite(ret_aligned[mask]).any():
                r = ret_aligned[mask]
                r = r[np.isfinite(r)]
                mean_ret[sid] = float(np.mean(r)) if r.size else 0.0
                vol[sid] = float(np.std(r)) if r.size else 0.0
                # Sortino-style: only NEGATIVE returns count as risk, so a
                # violent RALLY regime no longer ranks as "dangerous".
                downside[sid] = float(np.sqrt(np.mean(np.minimum(r, 0.0) ** 2))) if r.size else 0.0
            else:
                # Fall back to model means if no return series provided.
                mean_ret[sid] = float(self.model.means_[sid].mean())
                vol[sid] = float(np.sqrt(np.trace(self.model.covars_[sid]) / X.shape[1]))
                downside[sid] = vol[sid]

        # Labels: sort by ASCENDING mean return.
        order_by_return = list(np.argsort(mean_ret))
        scheme = _LABEL_SCHEMES.get(k, [f"REGIME_{i}" for i in range(k)])
        id_to_label = {sid: scheme[rank] for rank, sid in enumerate(order_by_return)}

        # Strategy ranking: sort by ASCENDING DOWNSIDE deviation (Sortino logic).
        # expected_volatility carries the downside number so the orchestrator's
        # volatility ranking is downside-consistent too.
        self.vol_sorted_ids = list(np.argsort(downside))

        self.regime_info = {}
        for rank, sid in enumerate(self.vol_sorted_ids):
            frac = rank / max(1, k - 1)  # 0 = calmest, 1 = most turbulent
            self.regime_info[sid] = RegimeInfo(
                regime_id=int(sid),
                regime_name=id_to_label[sid],
                expected_return=float(mean_ret[sid]),
                expected_volatility=float(downside[sid]),
                recommended_strategy_type=self._strategy_for(frac),
                max_leverage_allowed=float(round(1.25 * (1.0 - frac), 3)),
                max_position_size_pct=float(round(0.95 - 0.65 * frac, 3)),
                min_confidence_to_act=self.min_confidence,
            )

    @staticmethod
    def _strategy_for(vol_frac: float) -> str:
        if vol_frac <= 0.34:
            return "trend_following"
        if vol_frac <= 0.67:
            return "mean_reversion"
        return "defensive_cash"

    # ------------------------------------------------------------------
    # Emission + forward algorithm (FILTERED, no look-ahead)
    # ------------------------------------------------------------------
    def _emission_logprob(self, X: np.ndarray) -> np.ndarray:
        """Log emission probabilities, shape (T, K). Version-independent."""
        k = self.n_regimes
        X = np.atleast_2d(X)
        out = np.empty((X.shape[0], k))
        for sid in range(k):
            out[:, sid] = multivariate_normal.logpdf(
                X, mean=self.model.means_[sid], cov=self.model.covars_[sid], allow_singular=True,
            )
        return out

    def _forward_log_alpha(self, X: np.ndarray) -> np.ndarray:
        """
        Forward algorithm in log space, normalized per step.
        Returns filtered log P(state_t | obs_1:t), shape (T, K).

        alpha_t depends ONLY on obs_1:t -> strictly causal, no look-ahead.
        """
        if self.model is None:
            raise RuntimeError("Engine not trained")
        log_start = np.log(self.model.startprob_ + _TINY)
        log_trans = np.log(self.model.transmat_ + _TINY)
        log_emit = self._emission_logprob(X)
        T = log_emit.shape[0]

        log_alpha = np.empty_like(log_emit)
        log_alpha[0] = log_start + log_emit[0]
        log_alpha[0] -= logsumexp(log_alpha[0])
        for t in range(1, T):
            # For each destination j: logsumexp_i(alpha[t-1,i] + logtrans[i,j])
            log_alpha[t] = logsumexp(log_alpha[t - 1][:, None] + log_trans, axis=0) + log_emit[t]
            log_alpha[t] -= logsumexp(log_alpha[t])
        return log_alpha

    def _filtered_states(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self._forward_log_alpha(X), axis=1)

    def predict_regime_filtered(self, features_up_to_now) -> np.ndarray:
        """
        Compute P(state_t | observations_1:t) via the forward algorithm and
        return the most-likely filtered state at each t. Uses ONLY past/present.
        """
        X = np.asarray(features_up_to_now, dtype=float)
        return self._filtered_states(X)

    def predict_regime_proba(self, features_up_to_now) -> np.ndarray:
        """Filtered probability distribution over states, shape (T, K)."""
        X = np.asarray(features_up_to_now, dtype=float)
        return np.exp(self._forward_log_alpha(X))

    # ------------------------------------------------------------------
    # Live incremental update (cached forward pass) + stability/flicker
    # ------------------------------------------------------------------
    def reset_state(self) -> None:
        self._last_log_alpha = None
        self._history = []
        self._raw_history = []
        self._active_regime = None
        self._pending_regime = None
        self._pending_count = 0
        self._consecutive = 0

    def update(self, feature_row, timestamp: datetime | None = None) -> RegimeState:
        """
        Advance one bar using cached forward recursion (identical result to the
        batch forward pass) and apply the stability-confirmation filter.
        """
        if self.model is None:
            raise RuntimeError("Engine not trained")
        x = np.asarray(feature_row, dtype=float).reshape(1, -1)
        log_emit = self._emission_logprob(x)[0]
        log_trans = np.log(self.model.transmat_ + _TINY)

        if self._last_log_alpha is None:
            log_alpha = np.log(self.model.startprob_ + _TINY) + log_emit
        else:
            log_alpha = logsumexp(self._last_log_alpha[:, None] + log_trans, axis=0) + log_emit
        log_alpha -= logsumexp(log_alpha)
        self._last_log_alpha = log_alpha

        proba = np.exp(log_alpha)
        raw_state = int(np.argmax(proba))
        self._raw_history.append(raw_state)

        confirmed_changed = self._apply_stability(raw_state)
        info = self.regime_info.get(self._active_regime)
        label = info.regime_name if info else f"REGIME_{self._active_regime}"

        state = RegimeState(
            label=label,
            state_id=int(self._active_regime),
            probability=float(proba[self._active_regime]),
            state_probabilities=proba,
            timestamp=timestamp,
            is_confirmed=not self.is_flickering(),
            consecutive_bars=self._consecutive,
        )
        self._history.append(self._active_regime)

        if confirmed_changed:
            logger.warning("Regime CHANGE confirmed -> %s (id=%d)", label, self._active_regime)
        else:
            logger.info("Regime hold: %s (id=%d, %d bars)", label, self._active_regime, self._consecutive)
        return state

    def _apply_stability(self, raw_state: int) -> bool:
        """Return True iff a confirmed regime change happened this bar."""
        if self._active_regime is None:
            self._active_regime = raw_state
            self._pending_regime = raw_state
            self._pending_count = 1
            self._consecutive = 1
            return True

        if raw_state == self._active_regime:
            self._consecutive += 1
            self._pending_regime = raw_state
            self._pending_count = 0
            return False

        # Candidate different from the active regime -> require persistence.
        if raw_state == self._pending_regime:
            self._pending_count += 1
        else:
            self._pending_regime = raw_state
            self._pending_count = 1

        if self._pending_count >= self.stability_bars:
            self._active_regime = raw_state
            self._consecutive = self._pending_count
            self._pending_count = 0
            return True
        return False

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------
    def get_regime_stability(self) -> int:
        return self._consecutive

    def get_transition_matrix(self) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Engine not trained")
        return self.model.transmat_.copy()

    def detect_regime_change(self) -> bool:
        """True only if the last two confirmed regimes differ."""
        if len(self._history) < 2:
            return False
        return self._history[-1] != self._history[-2]

    def get_regime_flicker_rate(self) -> int:
        """Number of raw-state changes over the last `flicker_window` bars."""
        window = self._raw_history[-self.flicker_window:]
        return int(sum(1 for i in range(1, len(window)) if window[i] != window[i - 1]))

    def is_flickering(self) -> bool:
        return self.get_regime_flicker_rate() > self.flicker_threshold

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "metadata": {
                "n_regimes": self.n_regimes,
                "bic": self.bic,
                "bic_scores": self.bic_scores,
                "training_date": self.training_date,
                "labels": {sid: ri.regime_name for sid, ri in self.regime_info.items()},
                "vol_sorted_ids": self.vol_sorted_ids,
            },
            "regime_info": self.regime_info,
            "config": {
                "n_candidates": self.n_candidates,
                "stability_bars": self.stability_bars,
                "flicker_window": self.flicker_window,
                "flicker_threshold": self.flicker_threshold,
                "min_confidence": self.min_confidence,
            },
        }
        with open(path, "wb") as fh:
            pickle.dump(payload, fh)
        logger.info("Saved HMM engine to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "HMMRegimeEngine":
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        cfg = payload.get("config", {})
        engine = cls(
            n_candidates=cfg.get("n_candidates"),
            stability_bars=cfg.get("stability_bars", 3),
            flicker_window=cfg.get("flicker_window", 20),
            flicker_threshold=cfg.get("flicker_threshold", 4),
            min_confidence=cfg.get("min_confidence", 0.55),
        )
        engine.model = payload["model"]
        meta = payload["metadata"]
        engine.n_regimes = meta["n_regimes"]
        engine.bic = meta["bic"]
        engine.bic_scores = meta.get("bic_scores", {})
        engine.training_date = meta.get("training_date")
        engine.vol_sorted_ids = meta.get("vol_sorted_ids", [])
        engine.regime_info = payload["regime_info"]
        engine.reset_state()
        return engine
