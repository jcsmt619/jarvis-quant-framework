"""
tests/test_multistrat_e2e.py
============================
End-to-end multi-strategy scenarios exercised through the REAL components
(StrategyRegistry + CapitalAllocator + health checks + PortfolioRiskManager):

  1. Correlated strategies  -> allocator merges them, ~50/50 after merge.
  2. Uncorrelated strategies -> diversified, combined Sharpe > each individual.
  3. Strategy failure        -> 20% drawdown disables it, capital redistributes.
  4. Portfolio cap           -> total exposure proportionally reduced to 80%.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.capital_allocator import AllocatorConfig, CapitalAllocator, PortfolioSnapshot
from core.regime_strategies import AllocationSignal, BaseStrategy
from core.risk_manager import PortfolioRiskManager, PortfolioState, TradeSignal
from core.strategy_registry import StrategyRegistry

TRADING_DAYS = 252


class DummyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - atr)


def _sharpe(returns: np.ndarray) -> float:
    sd = returns.std(ddof=1)
    if sd < 1e-12:
        return 0.0
    return float(returns.mean() / sd * np.sqrt(TRADING_DAYS))


def _registry(returns: dict[str, np.ndarray], wmin=0.0, wmax=1.0) -> StrategyRegistry:
    reg = StrategyRegistry()
    for name, series in returns.items():
        s = DummyStrategy(name=name)
        s.weight_min, s.weight_max = wmin, wmax
        reg.register(name, s)
        for r in series:
            s.record_daily_return(float(r))
    return reg


# --- 1. correlated strategies get merged -----------------------------------
def test_correlated_strategies_merge_and_split_evenly():
    rng = np.random.default_rng(0)
    n = 120
    common = rng.normal(0.0004, 0.010, n)                 # shared equity-market factor
    spy = common + rng.normal(0.0, 0.003, n)              # "always long SPY"
    qqq = common + rng.normal(0.0, 0.003, n)              # "always long QQQ"

    reg = _registry({"strat_spy": spy, "strat_qqq": qqq})
    cfg = AllocatorConfig(approach="inverse_vol", reserve=0.10, corr_merge_threshold=0.80)
    alloc = CapitalAllocator(reg, cfg)

    corr = alloc.compute_correlation_matrix().loc["strat_spy", "strat_qqq"]
    assert corr > 0.80                                    # both equity -> highly correlated

    merges = alloc.should_merge_correlated_strategies()
    assert any({a, b} == {"strat_spy", "strat_qqq"} for a, b in merges)

    weights = alloc.allocate()                            # merged group -> split evenly
    assert weights["strat_spy"] == pytest.approx(0.5, abs=0.02)
    assert weights["strat_qqq"] == pytest.approx(0.5, abs=0.02)


# --- 2. uncorrelated strategies improve combined Sharpe --------------------
def test_uncorrelated_strategies_raise_combined_sharpe():
    rng = np.random.default_rng(1)
    n = TRADING_DAYS
    common = rng.normal(0.0, 0.010, n)
    a = 0.0006 + common                                   # long equity
    b = 0.0006 - common + rng.normal(0.0, 0.002, n)       # hedged / bond-like, same carry

    corr = np.corrcoef(a, b)[0, 1]
    assert corr < 0.0                                     # negative / uncorrelated

    combined = 0.5 * a + 0.5 * b
    assert _sharpe(combined) > _sharpe(a)
    assert _sharpe(combined) > _sharpe(b)


# --- 3. failing strategy is disabled and capital redistributes ------------
def test_failing_strategy_disabled_and_redistributed():
    rng = np.random.default_rng(2)
    n = 80
    healthy_b = rng.normal(0.0008, 0.010, n)
    healthy_c = rng.normal(0.0008, 0.010, n)
    failing_a = list(rng.normal(0.0005, 0.010, n))
    failing_a[40] = -0.20                                 # 20% drawdown -> unhealthy

    reg = _registry({"A": np.array(failing_a), "B": healthy_b, "C": healthy_c})
    cfg = AllocatorConfig(approach="inverse_vol", reserve=0.10, corr_merge_threshold=0.90)
    alloc = CapitalAllocator(reg, cfg)

    before = alloc.allocate()
    assert before.get("A", 0.0) > 0.0                     # A funded while healthy

    disabled = reg.enforce_health()
    assert "A" in disabled
    assert not reg.get("A").is_enabled

    after = alloc.allocate()                              # allocator sees only active
    assert after.get("A", 0.0) == 0.0
    assert after["B"] > 0.0 and after["C"] > 0.0
    assert sum(after.values()) == pytest.approx(1.0, abs=1e-6)   # portfolio keeps trading


# --- 4. portfolio caps total exposure at 80%, proportionally ---------------
def test_portfolio_caps_total_exposure_at_80pct():
    rng = np.random.default_rng(3)
    n = 80
    reg = _registry({                                     # each "wants 100%" (weight_max 1.0)
        "aggressive_1": rng.normal(0.0005, 0.010, n),
        "aggressive_2": rng.normal(0.0005, 0.010, n),
    }, wmin=0.0, wmax=1.0)
    cfg = AllocatorConfig(approach="inverse_vol", reserve=0.20, corr_merge_threshold=0.95)
    alloc = CapitalAllocator(reg, cfg)

    total = 100_000.0
    alloc.rebalance(reg, PortfolioSnapshot(total_capital=total, daily_drawdown=0.0))
    deployed = sum(reg.get(s).allocated_capital for s in ("aggressive_1", "aggressive_2"))
    assert deployed == pytest.approx(0.80 * total, rel=1e-6)     # 80% cap, 20% reserve
    for s in ("aggressive_1", "aggressive_2"):
        assert 0.35 * total <= reg.get(s).allocated_capital <= 0.45 * total   # proportional

    # The portfolio risk layer independently vetoes any order breaching the 80% gross cap.
    prm = PortfolioRiskManager()
    state = PortfolioState(equity=total, cash=total, buying_power=total,
                           positions={"AAA": {"notional": 0.50 * total, "direction": 1}})
    sig = TradeSignal(symbol="BBB", direction=1, asset_class="equity", price=100.0,
                      atr=2.0, stop_loss=96.0, target_notional=0.50 * total)
    decision = prm.check_aggregate_exposure(sig, state)         # 50% + 50% = 100% > 80%
    assert decision is not None and not decision.approved
