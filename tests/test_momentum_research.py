"""
tests/test_momentum_research.py
===============================
Offline mechanics: ranking picks the real winner, the skip-month actually
skips (reversal contamination regression), the benchmark is return-based
not price-level-based (the draft's bug), and turnover costs only bite
when the book changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.momentum_research import momentum_backtest


def _monthly(cols: dict) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    idx = pd.date_range("2018-01-31", periods=n, freq="ME")
    return pd.DataFrame(cols, index=idx)


def test_picks_persistent_winner():
    n = 30
    up = 100 * (1.05 ** np.arange(n))              # steady climber
    flat = np.full(n, 100.0)
    df = _monthly({"UP": up, "F1": flat, "F2": flat, "F3": flat})
    res = momentum_backtest(df, top_n=1, cost_bps=0.0)
    picked = [w[0] for _, w, _ in res["picks"]]
    assert set(picked) == {"UP"}
    assert res["strategy"]["total"] > res["benchmark"]["total"]


def test_skip_month_ignores_last_month_spike():
    """A stock that only spiked in the LATEST month must not out-rank a
    steady climber under 6-1 momentum (it would under 6-0)."""
    n = 12
    steady = 100 * (1.04 ** np.arange(n))
    spike = np.full(n, 100.0)
    spike[-1] = 160.0                              # last-month pop only
    df = _monthly({"STEADY": steady, "SPIKE": spike,
                   "F1": np.full(n, 100.0), "F2": np.full(n, 100.0)})
    res = momentum_backtest(df, lookback=6, skip=1, top_n=1, cost_bps=0.0)
    last_picks = res["picks"][-1][1]
    assert last_picks == ["STEADY"]                # spike skipped


def test_benchmark_is_return_based_not_price_based():
    """Draft regression: a $1000 stock and a $10 stock with IDENTICAL
    returns -> the equal-weight benchmark must equal that return, not be
    dominated by the big price level."""
    n = 20
    growth = 1.01 ** np.arange(n)
    df = _monthly({"BIG": 1000 * growth, "SMALL": 10 * growth,
                   "B2": 1000 * growth, "S2": 10 * growth})
    res = momentum_backtest(df, top_n=2, cost_bps=0.0)
    # every month's benchmark return is exactly 1% -> total compounds at 1%
    expected = 1.01 ** res["n_decisions"] - 1
    assert res["benchmark"]["total"] == pytest.approx(expected, rel=1e-9)


def test_turnover_cost_only_when_book_changes():
    n = 30
    up = 100 * (1.05 ** np.arange(n))
    flat = np.full(n, 100.0)
    df = _monthly({"UP": up, "F1": flat, "F2": flat, "F3": flat})
    free = momentum_backtest(df, top_n=1, cost_bps=0.0)
    costed = momentum_backtest(df, top_n=1, cost_bps=50.0)
    # Same single winner every month: only the FIRST decision pays.
    first_gap = free["picks"][0][2] - costed["picks"][0][2]
    assert first_gap == pytest.approx(2 * 50 / 1e4)
    later_gaps = [f[2] - c[2] for f, c in
                  zip(free["picks"][1:], costed["picks"][1:])]
    assert all(abs(g) < 1e-12 for g in later_gaps)


def test_psr_reported_and_bounded():
    rng = np.random.default_rng(0)
    n = 60
    cols = {f"T{i}": 100 * np.exp(np.cumsum(rng.normal(0.005, 0.05, n)))
            for i in range(8)}
    res = momentum_backtest(_monthly(cols))
    assert 0.0 <= res["psr_active"] <= 1.0
    assert res["n_decisions"] > 30
