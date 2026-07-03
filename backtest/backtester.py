"""
backtest/backtester.py
======================
ALLOCATION-BASED walk-forward backtester (STEP 4).

For each rolling window it (a) trains the HMM on the in-sample slice with BIC
model selection, (b) freezes the model, then (c) walks the out-of-sample slice
bar by bar using the FILTERED forward algorithm (no look-ahead), converting the
detected volatility regime into a target allocation and rebalancing when the
allocation drifts more than the threshold.

Windows (defaults, overridable):
    In-Sample     : 252 trading days (HMM training + selection)
    Out-of-Sample : 126 trading days (blind evaluation)
    Step          : 126 trading days (no overlap by default)

Allocation accounting (exactly as specified):
    equity        = cash + shares * price
    target_shares = int(equity * target_allocation / price)
    delta         = target_shares - shares
    cash         -= delta * fill_price      # fill_price includes slippage
    shares        = target_shares
Leverage > 1 simply drives cash negative (margin); equity stays correct.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.hmm_engine import HMMRegimeEngine
from core.regime_strategies import LETF_STOP_MULTIPLIER, StrategyOrchestrator
from utils.runner_exit import RunnerManager
from data.feature_engineering import build_features, log_returns, standardize_features
from strategies.vol_allocation import AllocationSettings

logger = logging.getLogger("backtester")


@dataclass
class BacktestResult:
    symbol: str
    index: pd.DatetimeIndex
    equity: np.ndarray
    returns: np.ndarray
    close: np.ndarray
    sma200: np.ndarray
    target: np.ndarray
    regime_history: list[dict]
    trades: list[dict]
    initial_capital: float
    n_windows: int
    params: dict = field(default_factory=dict)


class WalkForwardBacktester:
    def __init__(
        self,
        train_window: int = 252,
        test_window: int = 126,
        step_size: int = 126,
        slippage: float = 0.0005,
        rebalance_threshold: float = 0.10,
        fill_delay: int = 1,
        commission: float = 0.0,
        initial_capital: float = 100000.0,
        allocation_settings: AllocationSettings | None = None,
        n_candidates: list[int] | None = None,
        n_init: int = 4,
        random_state: int = 42,
        letf_stop_multiplier: float = LETF_STOP_MULTIPLIER,
        runner_mode: bool = False,
        runner_trigger_r: float = 1.5,
        runner_trail_atr: float = 2.0,
        satellite_cap: float | None = None,   # None -> orchestrator default (0.10)
        tail_monitor=None,                    # risk.tail_monitor.TailRiskMonitor
        tail_vix: "pd.Series | None" = None,  # VIX close indexed by date
        ensemble_seeds: list[int] | None = None,  # seed-ensemble brain (fixed k=3)
    ):
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.slippage = slippage
        self.rebalance_threshold = rebalance_threshold
        self.fill_delay = fill_delay
        self.commission = commission
        self.initial_capital = initial_capital
        self.settings = allocation_settings or AllocationSettings()
        self.n_candidates = n_candidates or [3, 4, 5]
        self.n_init = n_init
        self.random_state = random_state
        self.letf_stop_multiplier = letf_stop_multiplier
        # Runner Mode: bank 50% at +trigger_r R, breakeven stop, ATR-trail the rest.
        # Only ever TIGHTENS risk after entry (stop ratchets up, size only shrinks).
        self.runner_mode = runner_mode
        self.runner_trigger_r = runner_trigger_r
        self.runner_trail_atr = runner_trail_atr
        self.satellite_cap = satellite_cap
        # Proactive tail-risk overlay: clamp targets by the VIX-conditioned gross
        # cap. Causal: the cap at bar j uses bar j's VIX close, and fill_delay
        # already defers execution to the next bar (same convention as signals).
        self.tail_monitor = tail_monitor
        self.tail_vix = tail_vix
        # Seed-ensemble mode: fit one engine per seed (fixed 3 states so rank
        # spaces are congruent), align states by ASCENDING downside volatility
        # from each engine's own metadata (NO Viterbi -- alignment comes from
        # regime_info, not decoding), and average the FILTERED probabilities
        # across seeds in rank space. Cures the fit-lottery the robustness
        # battery exposed. None -> single-engine behavior, unchanged.
        self.ensemble_seeds = ensemble_seeds

    # ------------------------------------------------------------------
    # Core allocation simulator (shared by strategy + benchmarks)
    # ------------------------------------------------------------------
    def _simulate(self, prices: np.ndarray, targets: np.ndarray, meta: list | None = None) -> dict:
        """
        Simulate the exact allocation accounting over aligned price/target arrays.
        `targets` are already fill-delay-shifted by the caller. NaN target => hold.
        Returns equity array + trade log (one entry per closed holding segment).
        """
        n = len(prices)
        cash = self.initial_capital
        shares = 0
        equity = np.empty(n)
        trades: list[dict] = []

        seg_entry_price: float | None = None
        seg_entry_idx: int | None = None
        seg_meta = None

        for t in range(n):
            price = prices[t]
            eq_pre = cash + shares * price
            cur_alloc = (shares * price) / eq_pre if eq_pre != 0 else 0.0
            tgt = targets[t]

            if not np.isnan(tgt) and abs(tgt - cur_alloc) > self.rebalance_threshold:
                # Close the current holding segment (mark realized P&L).
                if seg_entry_price is not None and shares != 0:
                    pnl = shares * (price - seg_entry_price) - self.commission
                    notional = abs(shares) * seg_entry_price
                    trades.append({
                        "entry_idx": seg_entry_idx, "exit_idx": t,
                        "hold_bars": t - (seg_entry_idx or t),
                        "pnl": float(pnl),
                        "return_pct": float(pnl / notional) if notional else 0.0,
                        "meta": seg_meta,
                    })

                target_shares = int(eq_pre * tgt / price)
                delta = target_shares - shares
                sign = 1 if delta > 0 else (-1 if delta < 0 else 0)
                fill_price = price * (1 + self.slippage * sign)
                cash -= delta * fill_price
                shares = target_shares
                seg_entry_price = price
                seg_entry_idx = t
                seg_meta = meta[t] if meta is not None else None

            equity[t] = cash + shares * price

        # Close any residual open segment at the last price.
        if seg_entry_price is not None and shares != 0:
            price = prices[-1]
            pnl = shares * (price - seg_entry_price) - self.commission
            notional = abs(shares) * seg_entry_price
            trades.append({
                "entry_idx": seg_entry_idx, "exit_idx": n - 1,
                "hold_bars": (n - 1) - (seg_entry_idx or n - 1),
                "pnl": float(pnl),
                "return_pct": float(pnl / notional) if notional else 0.0,
                "meta": seg_meta,
            })
        return {"equity": equity, "trades": trades}

    @staticmethod
    def _shift_targets(targets: np.ndarray, delay: int) -> np.ndarray:
        if delay <= 0:
            return targets.copy()
        shifted = np.full_like(targets, np.nan)
        shifted[delay:] = targets[:-delay]
        return shifted

    # ------------------------------------------------------------------
    # Walk-forward
    # ------------------------------------------------------------------
    def run(self, df: pd.DataFrame, symbol: str = "ASSET") -> BacktestResult:
        data = df.copy()
        data.columns = [c.lower() for c in data.columns]

        feats_raw = build_features(data)
        feats_std = standardize_features(feats_raw, 252)
        valid = feats_std.replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) < self.train_window + self.test_window:
            raise ValueError(
                f"Not enough usable bars ({len(valid)}) for train+test "
                f"({self.train_window}+{self.test_window})"
            )

        close = data["close"].reindex(valid.index)
        sma200 = data["close"].rolling(200).mean().reindex(valid.index)
        ema50 = data["close"].ewm(span=50, adjust=False).mean().reindex(valid.index)
        _prev = data["close"].shift(1)
        _tr = pd.concat([
            (data["high"] - data["low"]),
            (data["high"] - _prev).abs(),
            (data["low"] - _prev).abs(),
        ], axis=1).max(axis=1)
        atr = _tr.ewm(alpha=1.0 / 14.0, adjust=False).mean().reindex(valid.index)
        ret_label = log_returns(data["close"]).reindex(valid.index)

        n = len(valid)
        feat_matrix = valid.to_numpy()
        target = np.full(n, np.nan)
        regime_meta: list[dict | None] = [None] * n
        covered = np.zeros(n, dtype=bool)
        # Runner state persists ACROSS windows: an open position spans window seams.
        runner = RunnerManager(trigger_r=self.runner_trigger_r,
                               trail_atr_mult=self.runner_trail_atr)
        # Tail overlay: align VIX to the traded calendar (ffill weekends/halts).
        vix_arr = None
        if self.tail_monitor is not None and self.tail_vix is not None:
            vix_arr = self.tail_vix.reindex(valid.index).ffill().to_numpy(dtype=float)

        w = 0
        n_windows = 0
        while w + self.train_window < n:
            is_start, is_end = w, w + self.train_window
            oos_start, oos_end = is_end, min(is_end + self.test_window, n)
            if oos_start >= oos_end:
                break

            # --- fit the brain: single engine, or a seed-ensemble of engines ---
            engines: list[HMMRegimeEngine] = []
            if self.ensemble_seeds:
                for s in self.ensemble_seeds:
                    e = HMMRegimeEngine(
                        n_candidates=[3], n_init=2,          # congruent rank spaces
                        min_train_bars=self.train_window, random_state=s,
                    )
                    try:
                        e.train(valid.iloc[is_start:is_end], returns=ret_label.iloc[is_start:is_end])
                        engines.append(e)
                    except Exception:                        # shield failed seeds
                        continue
                if not engines:
                    logger.warning("window @%d: ALL ensemble seeds failed", w)
                    w += self.step_size
                    continue
                engine = engines[0]                          # anchor for orchestrator ids
            else:
                engine = HMMRegimeEngine(
                    n_candidates=self.n_candidates, n_init=self.n_init,
                    min_train_bars=self.train_window, random_state=self.random_state,
                )
                try:
                    engine.train(valid.iloc[is_start:is_end], returns=ret_label.iloc[is_start:is_end])
                except Exception as exc:
                    logger.warning("window @%d training failed: %s", w, exc)
                    w += self.step_size
                    continue
                engines = [engine]

            # STEP 3 allocation blueprint: map regimes (ranked by volatility) to
            # a target exposure + mandatory ATR stop via the orchestrator.
            orch = StrategyOrchestrator(
                engine.regime_info,
                min_confidence=self.settings.min_confidence,
                rebalance_threshold=self.rebalance_threshold,
                uncertainty_mult=self.settings.uncertainty_size_mult,
                symbol=symbol,
                letf_stop_multiplier=self.letf_stop_multiplier,
                **({"satellite_cap": self.satellite_cap} if self.satellite_cap is not None else {}),
            )

            # Seed the filtered state with the in-sample history, then walk OOS.
            for e in engines:
                e.reset_state()
                for row in feat_matrix[is_start:is_end]:
                    e.update(row)

            # Ensemble stability tracking (mirrors engine defaults 3/20/5).
            ens_rank_hist: list[int] = []
            ens_consec, ens_last_rank = 0, -1

            for j in range(oos_start, oos_end):
                if self.ensemble_seeds:
                    # Average FILTERED probabilities across seeds in rank space
                    # (each engine's states sorted by ITS OWN ascending downside
                    # vol via vol_sorted_ids -- deterministic, no decoding).
                    k = 3
                    rank_probs = np.zeros(k)
                    for e in engines:
                        st_e = e.update(feat_matrix[j])
                        for rank, sid in enumerate(e.vol_sorted_ids):
                            rank_probs[rank] += st_e.state_probabilities[sid]
                    rank_probs /= len(engines)
                    ens_rank = int(np.argmax(rank_probs))
                    prob_j = float(rank_probs[ens_rank])
                    state_id_j = engine.vol_sorted_ids[ens_rank]   # anchor engine's id space
                    ens_consec = ens_consec + 1 if ens_rank == ens_last_rank else 1
                    ens_last_rank = ens_rank
                    ens_rank_hist.append(ens_rank)
                    changes = sum(1 for a, b in zip(ens_rank_hist[-20:], ens_rank_hist[-19:]) if a != b)
                    flickering_j = changes > 5
                else:
                    st = engine.update(feat_matrix[j])
                    state_id_j, prob_j = st.state_id, st.probability
                    flickering_j = engine.is_flickering()

                price_j = float(close.iloc[j])
                ema_j = float(ema50.iloc[j]) if not np.isnan(ema50.iloc[j]) else price_j
                atr_j = float(atr.iloc[j]) if not np.isnan(atr.iloc[j]) else 0.0
                active = float(target[j - 1]) if j > 0 and not np.isnan(target[j - 1]) else 0.0
                decision = orch.get_signal(
                    state_id_j, price_j, ema_j, atr_j,
                    prob_j, flickering_j, active_allocation=active,
                )
                tgt = decision.target_exposure
                # Mandatory stop: flatten to cash when price closes below the stop.
                stopped = atr_j > 0 and price_j < decision.stop_price
                if stopped:
                    tgt = 0.0

                banked = False
                if self.runner_mode:
                    was_flat = active <= 1e-9
                    if was_flat and tgt > 0 and not stopped:
                        # New trade: anchor R at the entry bar's regime stop.
                        runner.open_trade(price_j, decision.stop_price)
                    if not was_flat and runner.active:
                        act = runner.update(price_j, atr_j)
                        banked = act.banked_this_bar
                        if act.exited:
                            tgt = 0.0            # runner stop (>= breakeven once banked)
                        else:
                            tgt *= act.size_multiplier
                    if tgt <= 1e-9:
                        runner.close_trade()

                # PROACTIVE TAIL RISK: VIX-conditioned gross cap clamps ANY target.
                tail_cap = None
                if vix_arr is not None and np.isfinite(vix_arr[j]):
                    self.tail_monitor.update(float(vix_arr[j]))
                    tail_cap = self.tail_monitor.cap
                    tgt = self.tail_monitor.clamp_target(tgt)

                target[j] = tgt
                confirmed_j = (ens_consec >= 3) if self.ensemble_seeds else bool(st.is_confirmed)
                label_j = engine.regime_info[state_id_j].regime_name if self.ensemble_seeds else st.label
                regime_meta[j] = {
                    "date": valid.index[j], "regime_id": state_id_j, "label": label_j,
                    "vol_rank_frac": orch.vol_rank_fraction(state_id_j),
                    "probability": float(prob_j), "confirmed": confirmed_j,
                    "allocation": float(tgt), "strategy": decision.strategy, "stopped": bool(stopped),
                    "runner_banked": bool(banked),
                    "tail_cap": tail_cap,
                }
                covered[j] = True

            n_windows += 1
            w += self.step_size

        if not covered.any():
            raise RuntimeError("No out-of-sample bars were evaluated")

        first = int(np.argmax(covered))  # first covered bar
        sl = slice(first, n)
        cov_close = close.to_numpy()[sl]
        cov_target = self._shift_targets(target, self.fill_delay)[sl]
        cov_meta = regime_meta[first:n]
        cov_index = valid.index[sl]
        cov_sma = sma200.to_numpy()[sl]

        sim = self._simulate(cov_close, cov_target, cov_meta)
        equity = sim["equity"]
        returns = np.concatenate([[0.0], np.diff(equity) / equity[:-1]])

        regime_history = [m for m in cov_meta if m is not None]

        return BacktestResult(
            symbol=symbol, index=cov_index, equity=equity, returns=returns,
            close=cov_close, sma200=cov_sma, target=cov_target,
            regime_history=regime_history, trades=sim["trades"],
            initial_capital=self.initial_capital, n_windows=n_windows,
            params={
                "train_window": self.train_window, "test_window": self.test_window,
                "step_size": self.step_size, "slippage": self.slippage,
                "rebalance_threshold": self.rebalance_threshold, "fill_delay": self.fill_delay,
            },
        )

    # ------------------------------------------------------------------
    # Benchmarks (evaluated over the SAME covered region)
    # ------------------------------------------------------------------
    def benchmark_buy_hold(self, close: np.ndarray) -> np.ndarray:
        targets = self._shift_targets(np.ones(len(close)), self.fill_delay)
        return self._simulate(close, targets)["equity"]

    def benchmark_sma200(self, close: np.ndarray, sma200: np.ndarray) -> np.ndarray:
        raw = np.where(np.isnan(sma200), 0.0, (close > sma200).astype(float))
        targets = self._shift_targets(raw, self.fill_delay)
        return self._simulate(close, targets)["equity"]

    def benchmark_random(self, close: np.ndarray, seeds: int = 100) -> dict:
        """Random allocation changes under the SAME risk rules; return mean/std stats."""
        choices = np.array([0.0, 0.60, 0.95, self.settings.max_leverage])
        finals, sharpes = [], []
        for seed in range(seeds):
            rng = np.random.default_rng(seed)
            raw = np.empty(len(close))
            cur = 0.60
            for t in range(len(close)):
                if rng.random() < 0.05:  # occasionally change target
                    cur = float(rng.choice(choices))
                raw[t] = cur
            eq = self._simulate(close, self._shift_targets(raw, self.fill_delay))["equity"]
            finals.append(eq[-1] / eq[0] - 1.0)
            dr = np.diff(eq) / eq[:-1]
            sharpes.append((dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0)
        return {
            "return_mean": float(np.mean(finals)), "return_std": float(np.std(finals)),
            "sharpe_mean": float(np.mean(sharpes)), "sharpe_std": float(np.std(sharpes)),
            "seeds": seeds,
        }
