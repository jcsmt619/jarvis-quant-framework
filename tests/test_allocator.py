"""
tests/test_allocator.py
=======================
Covers the capital allocator: equal-weight, inverse-vol, correlation merging,
constraint clipping, the cash reserve, and the portfolio kill switch.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.capital_allocator import (
    AllocatorConfig,
    CapitalAllocator,
    PortfolioSnapshot,
)
from core.regime_strategies import AllocationSignal, BaseStrategy
from core.strategy_registry import StrategyRegistry


class DummyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - atr)


def _make(reg, name, returns, wmin=0.0, wmax=1.0, enabled=True):
    s = DummyStrategy(name=name)
    s.weight_min, s.weight_max = wmin, wmax
    if not enabled:
        s.on_disable()
    for r in returns:
        s.record_daily_return(float(r))
    reg.register(name, s)
    return s


def _noise(seed, vol=0.01, n=80):
    return list(np.random.default_rng(seed).normal(0.0, vol, n))


# --- equal weight ----------------------------------------------------------
def test_equal_weight_three_strategies():
    reg = StrategyRegistry()
    for i, n in enumerate(["a", "b", "c"]):
        _make(reg, n, _noise(i))
    alloc = CapitalAllocator(reg, AllocatorConfig(approach="equal_weight", corr_merge_threshold=0.99))
    w = alloc.allocate()
    for n in ["a", "b", "c"]:
        assert w[n] == pytest.approx(1 / 3, abs=0.01)
    assert sum(w.values()) == pytest.approx(1.0)


# --- inverse volatility ----------------------------------------------------
def test_inverse_vol_lower_vol_gets_more():
    reg = StrategyRegistry()
    _make(reg, "low", _noise(1, vol=0.005))
    _make(reg, "high", _noise(2, vol=0.02))
    alloc = CapitalAllocator(reg, AllocatorConfig(approach="inverse_vol", corr_merge_threshold=0.99))
    w = alloc.allocate()
    assert w["low"] > w["high"]
    assert sum(w.values()) == pytest.approx(1.0)


def test_risk_parity_runs_and_favors_low_vol():
    reg = StrategyRegistry()
    _make(reg, "low", _noise(11, vol=0.004))
    _make(reg, "high", _noise(12, vol=0.02))
    alloc = CapitalAllocator(reg, AllocatorConfig(approach="risk_parity", corr_merge_threshold=0.99))
    w = alloc.allocate()
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["low"] > w["high"]


# --- correlation merge -----------------------------------------------------
def test_correlated_pair_is_merged():
    reg = StrategyRegistry()
    shared = _noise(3)
    _make(reg, "a", shared)
    _make(reg, "b", shared)          # identical -> corr = 1.0
    _make(reg, "c", _noise(4))
    alloc = CapitalAllocator(reg, AllocatorConfig(approach="inverse_vol", corr_merge_threshold=0.80))
    merges = alloc.should_merge_correlated_strategies()
    assert ("a", "b") in merges
    # Merged group's weight is split evenly -> a and b get identical weight.
    w = alloc.allocate()
    assert w["a"] == pytest.approx(w["b"], abs=1e-9)


# --- constraints -----------------------------------------------------------
def test_constraints_clip_min_and_max():
    reg = StrategyRegistry()
    _make(reg, "low", _noise(5, vol=0.002), wmin=0.0, wmax=0.40)   # would exceed -> cap 0.40
    _make(reg, "mid", _noise(6, vol=0.01))
    _make(reg, "high", _noise(7, vol=0.02), wmin=0.20, wmax=1.0)   # would be tiny -> floor 0.20
    alloc = CapitalAllocator(reg, AllocatorConfig(approach="inverse_vol", corr_merge_threshold=0.99))
    w = alloc.allocate()
    assert w["low"] == pytest.approx(0.40, abs=1e-3)
    assert w["high"] >= 0.20 - 1e-6
    assert sum(w.values()) == pytest.approx(1.0)


# --- reserve + kill switch -------------------------------------------------
def _two_strat_allocator():
    reg = StrategyRegistry()
    _make(reg, "a", _noise(8))
    _make(reg, "b", _noise(9))
    cfg = AllocatorConfig(approach="equal_weight", reserve=0.10,
                          daily_dd_halve=0.02, daily_dd_zero=0.03, corr_merge_threshold=0.99)
    return reg, CapitalAllocator(reg, cfg, total_capital=100000.0)


def test_reserve_is_held_as_cash():
    reg, alloc = _two_strat_allocator()
    alloc.rebalance(reg, PortfolioSnapshot(total_capital=100000.0, daily_drawdown=0.0))
    allocated = sum(s.allocated_capital for s in reg.all().values())
    assert allocated == pytest.approx(90000.0, abs=1.0)      # 10% reserve untouched


def test_kill_switch_halves_then_zeros():
    reg, alloc = _two_strat_allocator()
    alloc.rebalance(reg, PortfolioSnapshot(total_capital=100000.0, daily_drawdown=0.0))

    alloc.rebalance(reg, PortfolioSnapshot(total_capital=100000.0, daily_drawdown=0.025))
    assert sum(s.allocated_capital for s in reg.all().values()) == pytest.approx(45000.0, abs=1.0)

    alloc.rebalance(reg, PortfolioSnapshot(total_capital=100000.0, daily_drawdown=0.035))
    assert sum(s.allocated_capital for s in reg.all().values()) == pytest.approx(0.0, abs=1e-6)


def test_rebalance_returns_allocation_changes():
    reg, alloc = _two_strat_allocator()
    changes = alloc.rebalance(reg, PortfolioSnapshot(total_capital=100000.0, daily_drawdown=0.0))
    assert {c.strategy_name for c in changes} == {"a", "b"}
    for c in changes:
        assert c.new_capital == pytest.approx(45000.0, abs=1.0)
        assert c.reason
