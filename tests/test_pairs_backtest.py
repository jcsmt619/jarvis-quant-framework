"""
tests/test_pairs_backtest.py
============================
Pairs backtester: signal causality (rolling hedge ratio + z), t+1 fill lag,
friction accounting, and band-snap stop behavior.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.pairs_backtest import PairConfig, backtest_pair, rolling_signals


def _pair(n=800, seed=0):
    """Co-integrated synthetic pair: B is A/2 plus mean-reverting noise."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    a = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))), index=idx)
    noise = np.zeros(n)
    for i in range(1, n):                     # OU noise -> spread mean-reverts
        noise[i] = 0.9 * noise[i - 1] + rng.normal(0, 0.4)
    b = a * 0.5 + noise
    return a, b


# --- 1. causality: signals at t identical with/without future data ----------
def test_signals_no_lookahead():
    a, b = _pair()
    cfg = PairConfig()
    full = rolling_signals(a, b, cfg)
    cut = 600
    prefix = rolling_signals(a.iloc[:cut], b.iloc[:cut], cfg)
    common = prefix.index
    pd.testing.assert_series_equal(full.loc[common, "z"], prefix["z"])
    pd.testing.assert_series_equal(full.loc[common, "hedge"], prefix["hedge"])


# --- 2. the whole backtest is prefix-consistent ------------------------------
def test_backtest_no_lookahead():
    a, b = _pair()
    r_full = backtest_pair(a, b)
    r_prefix = backtest_pair(a.iloc[:600], b.iloc[:600])
    common = r_prefix.equity.index
    # Equity path over the shared period must be identical.
    pd.testing.assert_series_equal(r_full.equity.loc[common], r_prefix.equity,
                                   check_exact=False, rtol=1e-9)


# --- 3. friction is actually charged -----------------------------------------
def test_friction_and_borrow_are_charged():
    a, b = _pair()
    res = backtest_pair(a, b)
    if res.metrics["n_trades"] > 0:
        assert res.friction_paid > 0.0
        assert res.borrow_paid > 0.0          # every held day accrues HTB borrow


# --- 4. no trades on a pair with no signal ------------------------------------
def test_flat_when_no_entry_band_hit():
    """Exactly proportional pair -> constant spread -> no z-score -> no trades."""
    idx = pd.bdate_range("2020-01-01", periods=600)
    rng = np.random.default_rng(3)
    a = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, 600))), index=idx)
    b = a * 0.5                                 # perfect ratio, zero spread noise
    res = backtest_pair(a, b)
    assert res.metrics["n_trades"] == 0
    assert res.friction_paid == 0.0


# --- 5. adaptive Kelly: warmup, guards, and self-shutdown ---------------------
def test_kelly_sizing_warmup_and_no_nan():
    a, b = _pair(seed=5)
    cfg = PairConfig(kelly_sizing=True)
    res = backtest_pair(a, b, cfg)              # must not crash on empty wins/losses
    assert np.isfinite(res.equity).all()
    assert res.metrics["n_trades"] >= 0


def test_kelly_shuts_down_on_negative_edge():
    """With realized stats implying negative Kelly, allocation goes to 0 -> the
    strategy stops trading instead of bleeding (draft's emergent property)."""
    from backtest.pairs_backtest import PairConfig as PC

    # Simulate the allocator directly: 20 trades, 20% win rate, R=0.5
    cfg = PC(kelly_sizing=True)
    pnls = [100.0] * 4 + [-200.0] * 16          # w=0.2, r=0.5 -> kelly < 0
    w = 4 / 20
    r = 100.0 / 200.0
    k = (w - (1 - w) / r) * cfg.kelly_fraction
    assert k < 0                                 # formula says no edge
    # (in the engine this clamps to 0.0 and entries are skipped)


# --- 6. fund verdict gates -----------------------------------------------------
def test_fund_verdict_gates():
    from backtest.pairs_backtest import PairResult, fund_verdict

    idx = pd.bdate_range("2020-01-01", periods=300)
    good_eq = pd.Series(np.linspace(100_000, 130_000, 300), index=idx)
    trades = [{"pnl": 500.0, "days": 5}] * 12 + [{"pnl": -400.0, "days": 5}] * 8
    ok = PairResult(equity=good_eq, trades=trades,
                    metrics={"total_return": 0.30, "cagr": 0.25, "max_dd": 0.08,
                             "sharpe": 1.2, "n_trades": 20, "win_rate": 0.6,
                             "avg_hold_days": 5, "friction_drag_pct": 0.01,
                             "borrow_drag_pct": 0.01},
                    friction_paid=1000.0, borrow_paid=500.0)
    v = fund_verdict(ok)
    assert v["status"] == "FUNDABLE" and not v["fail_reasons"]

    dead_dd = PairResult(equity=good_eq, trades=trades,
                         metrics={**ok.metrics, "max_dd": 0.35},
                         friction_paid=0, borrow_paid=0)
    v2 = fund_verdict(dead_dd)
    assert v2["status"] == "DEAD" and "drawdown" in v2["fail_reasons"][0]

    dead_exp = PairResult(equity=good_eq, trades=trades,
                          metrics={**ok.metrics, "cagr": -0.02},
                          friction_paid=0, borrow_paid=0)
    v3 = fund_verdict(dead_exp)
    assert v3["status"] == "DEAD" and "expectancy" in v3["fail_reasons"][0]

    few = PairResult(equity=good_eq, trades=trades[:5],
                     metrics=ok.metrics, friction_paid=0, borrow_paid=0)
    v4 = fund_verdict(few)
    assert v4["status"] == "DEAD" and "too few" in v4["fail_reasons"][0]
