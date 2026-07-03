"""
backtest/stress_test.py
=======================
Adversarial stress tests for the allocation strategy. The point is NOT to make
the strategy look good -- it is to find where it breaks.

  a. Crash injection : inject -5% to -15% gaps at random points, Monte Carlo.
  b. Gap risk        : overnight gaps of 2-5x ATR at random points.
  c. Regime misclassification : shuffle the vol rankings the strategy trusts and
     confirm the risk management still contains the damage.

Each test perturbs the PRICE PATH (or the strategy's regime trust) and re-runs
the walk-forward backtester, then reports the distribution of outcomes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.backtester import WalkForwardBacktester
from backtest.performance import _max_drawdown, _sharpe, compute_metrics


def _apply_price_shocks(df: pd.DataFrame, shock_idx: np.ndarray, shock_mult: np.ndarray) -> pd.DataFrame:
    """Multiply the OHLC path from each shock point onward by the shock factor."""
    out = df.copy()
    cols = [c for c in ["open", "high", "low", "close"] if c in out.columns]
    factor = np.ones(len(out))
    for i, m in zip(shock_idx, shock_mult):
        factor[i:] *= m
    for c in cols:
        out[c] = out[c].to_numpy() * factor
    return out


def crash_injection(df: pd.DataFrame, backtester: WalkForwardBacktester, symbol: str,
                    n_sims: int = 100, n_gaps: int = 10, seed: int = 0) -> dict:
    """Inject `n_gaps` gaps of -5%..-15% at random points, `n_sims` Monte Carlo runs."""
    n = len(df)
    finals, dds = [], []
    for s in range(n_sims):
        rng = np.random.default_rng(seed + s)
        idx = rng.integers(low=252, high=n, size=n_gaps)
        mult = 1.0 - rng.uniform(0.05, 0.15, size=n_gaps)
        shocked = _apply_price_shocks(df, idx, mult)
        try:
            res = backtester.run(shocked, symbol=symbol)
        except Exception:
            continue
        m = compute_metrics(res.equity, res.returns, res.trades)
        finals.append(m["total_return"])
        dds.append(m["max_drawdown"])
    return _summarize("crash_injection", finals, dds, n_sims)


def gap_risk(df: pd.DataFrame, backtester: WalkForwardBacktester, symbol: str,
             n_sims: int = 100, n_gaps: int = 10, seed: int = 1000) -> dict:
    """Overnight gaps of 2-5x ATR (up or down) at random points."""
    n = len(df)
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().bfill().to_numpy()
    px = close.to_numpy()

    finals, dds = [], []
    for s in range(n_sims):
        rng = np.random.default_rng(seed + s)
        idx = rng.integers(low=252, high=n, size=n_gaps)
        gap_atr = rng.uniform(2.0, 5.0, size=n_gaps) * rng.choice([-1.0, 1.0], size=n_gaps)
        mult = np.ones(n_gaps)
        for j, (i, g) in enumerate(zip(idx, gap_atr)):
            mult[j] = 1.0 + (g * atr[i]) / px[i]
        shocked = _apply_price_shocks(df, idx, mult)
        try:
            res = backtester.run(shocked, symbol=symbol)
        except Exception:
            continue
        m = compute_metrics(res.equity, res.returns, res.trades)
        finals.append(m["total_return"])
        dds.append(m["max_drawdown"])
    return _summarize("gap_risk", finals, dds, n_sims)


def regime_misclassification(df: pd.DataFrame, backtester: WalkForwardBacktester, symbol: str,
                             n_sims: int = 20, seed: int = 2000) -> dict:
    """
    Corrupt the strategy's regime trust: run the backtester but with the vol
    rankings randomly SHUFFLED, so the allocation reacts to the wrong regime.
    Risk management (rebalance bands, caps) should still contain the damage.
    Baseline (correct) vs shuffled max drawdowns are compared.
    """
    base = backtester.run(df, symbol=symbol)
    base_dd = compute_metrics(base.equity, base.returns, base.trades)["max_drawdown"]

    shuffled_dds, shuffled_rets = [], []
    original = WalkForwardBacktester.run
    for s in range(n_sims):
        rng = np.random.default_rng(seed + s)

        def shuffled_run(self, d, symbol="ASSET", _rng=rng, _orig=original):
            res = _orig(self, d, symbol=symbol)
            # Corrupt the recorded allocations by remapping vol-rank fractions.
            for m in res.regime_history:
                m["vol_rank_frac"] = float(_rng.random())
            return res

        try:
            res = original(backtester, df, symbol=symbol)
            # Re-simulate with corrupted allocations: perturb target then re-run sim.
            corrupt_target = res.target.copy()
            mask = ~np.isnan(corrupt_target)
            corrupt_target[mask] = rng.choice([0.0, 0.6, 0.95, 1.25], size=mask.sum())
            sim = backtester._simulate(res.close, corrupt_target)
            eq = sim["equity"]
            dd, _ = _max_drawdown(eq)
            shuffled_dds.append(dd)
            shuffled_rets.append(float(eq[-1] / eq[0] - 1.0))
        except Exception:
            continue

    return {
        "test": "regime_misclassification",
        "baseline_max_dd": float(base_dd),
        "shuffled_max_dd_mean": float(np.mean(shuffled_dds)) if shuffled_dds else 0.0,
        "shuffled_max_dd_worst": float(np.min(shuffled_dds)) if shuffled_dds else 0.0,
        "shuffled_return_mean": float(np.mean(shuffled_rets)) if shuffled_rets else 0.0,
        "contained": bool(shuffled_dds and np.min(shuffled_dds) > -0.35),
        "sims": len(shuffled_dds),
    }


def _summarize(name: str, finals: list, dds: list, n_sims: int) -> dict:
    if not finals:
        return {"test": name, "sims": 0}
    finals, dds = np.array(finals), np.array(dds)
    return {
        "test": name,
        "sims": len(finals),
        "return_mean": float(finals.mean()),
        "return_p05": float(np.percentile(finals, 5)),
        "return_worst": float(finals.min()),
        "max_dd_mean": float(dds.mean()),
        "max_dd_worst": float(dds.min()),
    }
