"""
tests/test_multistrat_backtest.py
=================================
Covers multi-strategy backtest mode: weighted-sum portfolio returns, allocator
weighting, the correlation report, and health-driven strategy disabling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.multistrat import MultiStrategyBacktester
from core.capital_allocator import AllocatorConfig, CapitalAllocator
from core.regime_strategies import AllocationSignal, BaseStrategy
from core.strategy_registry import StrategyRegistry


class DummyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - atr)


def _registry(names, wmin=0.0, wmax=1.0):
    reg = StrategyRegistry()
    for n in names:
        s = DummyStrategy(name=n)
        s.weight_min, s.weight_max = wmin, wmax
        reg.register(n, s)
    return reg


def _idx(periods):
    return pd.bdate_range("2020-01-01", periods=periods)


# --- 1. portfolio return matches weighted sum ------------------------------
def test_portfolio_return_matches_weighted_sum():
    reg = _registry(["a", "b"])
    idx = _idx(25)
    returns = {"a": pd.Series(0.01, index=idx), "b": pd.Series(-0.005, index=idx)}
    cfg = AllocatorConfig(approach="equal_weight", reserve=0.0, corr_merge_threshold=0.99)
    mb = MultiStrategyBacktester(reg, CapitalAllocator(reg, cfg), enforce_health=False)
    res = mb.run(returns)
    expected = 0.5 * 0.01 + 0.5 * (-0.005)   # equal weight, no reserve
    assert np.allclose(res.portfolio_returns, expected, atol=1e-9)


# --- 2. allocator weights (inverse vol favors low vol) ---------------------
def test_allocator_weights_favor_low_vol():
    reg = _registry(["low", "high"])
    idx = _idx(90)
    rng = np.random.default_rng(0)
    returns = {
        "low": pd.Series(rng.normal(0, 0.005, 90), index=idx),
        "high": pd.Series(rng.normal(0, 0.02, 90), index=idx),
    }
    cfg = AllocatorConfig(approach="inverse_vol", reserve=0.0, corr_merge_threshold=0.99)
    mb = MultiStrategyBacktester(reg, CapitalAllocator(reg, cfg), enforce_health=False)
    res = mb.run(returns)
    assert res.weight_history["low"].iloc[-1] > res.weight_history["high"].iloc[-1]


# --- 3. correlation report -------------------------------------------------
def test_correlation_report():
    reg = _registry(["a", "b", "c"])
    idx = _idx(90)
    rng = np.random.default_rng(1)
    base = rng.normal(0, 0.01, 90)
    returns = {
        "a": pd.Series(base, index=idx),
        "b": pd.Series(base, index=idx),                     # identical -> corr 1.0
        "c": pd.Series(rng.normal(0, 0.01, 90), index=idx),  # independent
    }
    cfg = AllocatorConfig(approach="equal_weight", reserve=0.0, corr_merge_threshold=0.99)
    mb = MultiStrategyBacktester(reg, CapitalAllocator(reg, cfg), corr_window=30, corr_threshold=0.8)
    res = mb.run(returns)
    assert res.correlation_matrix.loc["a", "b"] == pytest.approx(1.0, abs=1e-6)
    assert abs(res.correlation_matrix.loc["a", "c"]) < 0.5
    assert res.pair_over_threshold_pct["a~b"] == pytest.approx(1.0, abs=1e-6)


# --- 4. health-driven disabling --------------------------------------------
def test_health_disables_strategy_in_backtest():
    reg = _registry(["ok1", "ok2", "bad"])
    idx = _idx(40)
    rng = np.random.default_rng(2)
    bad_vals = list(rng.normal(0.0, 0.005, 40))
    bad_vals[2] = -0.25   # instant >15% drawdown -> unhealthy
    returns = {
        "ok1": pd.Series(rng.normal(0.001, 0.005, 40), index=idx),
        "ok2": pd.Series(rng.normal(0.001, 0.005, 40), index=idx),
        "bad": pd.Series(bad_vals, index=idx),
    }
    cfg = AllocatorConfig(approach="equal_weight", reserve=0.0, corr_merge_threshold=0.99)
    mb = MultiStrategyBacktester(reg, CapitalAllocator(reg, cfg))
    res = mb.run(returns)
    assert len(res.disabled_periods["bad"]) > 0          # auto-disabled at a rebalance
    assert res.weight_history["bad"].iloc[-1] == 0.0     # gets no capital afterward
    assert not reg.get("bad").is_enabled
