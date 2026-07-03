"""
tests/test_multistrat_integration.py
====================================
End-to-end wiring of the multi-strategy live engine (dry-run): per-strategy risk
-> portfolio risk -> executor, health-driven disabling propagating to the
allocator, allocator cadence, and the portfolio layer overriding a per-strategy
approval. No broker, no real orders.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.capital_allocator import AllocatorConfig, CapitalAllocator
from core.regime_strategies import AllocationSignal, BaseStrategy
from core.risk_manager import PortfolioRiskManager, RiskManager, TradeSignal
from core.strategy_registry import StrategyRegistry
from execution.multistrat_engine import BarContext, MultiStratLiveEngine

UTC = timezone.utc


class DummyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - atr)


def _good_signals(strategy, bars, regime):
    sym = strategy.symbols[0]
    price, atr = 100.0, 2.0
    return [TradeSignal(
        symbol=sym, direction=1, asset_class="equity", price=price, atr=atr,
        stop_loss=price - 2.0 * atr, regime="confirmed_low_vol", confirmed_breakout=True,
        win_rate=0.55, bid_ask_spread=0.0005, sector=sym)]


def _no_signals(strategy, bars, regime):
    return []


def _make_engine(tmp_path, signal_source, use_pr=True, names_syms=None):
    names_syms = names_syms or {"alpha": "AAA", "beta": "BBB"}
    reg = StrategyRegistry()
    for name, sym in names_syms.items():
        s = DummyStrategy(name=name)
        s.symbols = [sym]
        s.weight_min, s.weight_max = 0.0, 1.0
        reg.register(name, s)
    cfg = AllocatorConfig(approach="equal_weight", reserve=0.10, corr_merge_threshold=0.99)
    alloc = CapitalAllocator(reg, cfg)
    rms = {n: RiskManager(initial_capital=100000.0, lock_file=tmp_path / f"{n}.lock") for n in reg.all()}
    pr = PortfolioRiskManager(lock_file=tmp_path / "port.lock") if use_pr else None
    eng = MultiStratLiveEngine(reg, alloc, pr, rms, signal_source=signal_source, initial_capital=100000.0)
    return reg, alloc, eng


# --- 1. end-to-end dry run with 2 strategies -------------------------------
def test_end_to_end_dry_run_two_strategies(tmp_path):
    reg, alloc, eng = _make_engine(tmp_path, _good_signals)
    eng.initialize(datetime(2025, 1, 6, tzinfo=UTC))
    ctx = BarContext(datetime(2025, 1, 7, tzinfo=UTC), {}, {"risk_on": True, "label": "BULL"})
    records = eng.on_bar(ctx)
    assert any(r.approved for r in records)
    assert len(eng.executor.submitted) >= 1
    ds = eng.build_dashboard_state(ctx)
    assert len(ds.strategy_rows) == 2
    assert ds.cash_reserve_pct == pytest.approx(10.0)


# --- 2. strategy disabling mid-session propagates to allocator -------------
def test_disable_propagates_to_allocator(tmp_path):
    reg, alloc, eng = _make_engine(tmp_path, _no_signals)
    eng.initialize(datetime(2025, 1, 6, tzinfo=UTC))
    assert reg.get("alpha").allocated_capital > 0.0   # initial pass gave it capital

    reg.get("alpha").record_daily_return(-0.5)         # 50% DD -> unhealthy
    eng.on_bar(BarContext(datetime(2025, 1, 7, tzinfo=UTC), {}, {"risk_on": True}))
    assert not reg.get("alpha").is_enabled
    assert "alpha" in eng.disabled

    eng.force_rebalance(datetime(2025, 1, 20, tzinfo=UTC))
    assert reg.get("alpha").allocated_capital == 0.0   # excluded on next allocator pass
    assert reg.get("beta").allocated_capital > 0.0


# --- 3. allocator rebalance triggers on schedule ---------------------------
def test_allocator_rebalance_cadence(tmp_path):
    reg, alloc, eng = _make_engine(tmp_path, _no_signals)
    eng.initialize(datetime(2025, 1, 6, tzinfo=UTC))   # ISO week 2

    assert eng._maybe_rebalance(datetime(2025, 1, 8, tzinfo=UTC)) is None       # same week
    changes = eng._maybe_rebalance(datetime(2025, 1, 13, tzinfo=UTC))            # new week
    assert changes is not None

    from monitoring.alerts import AlertType
    assert any(a.alert_type == AlertType.ALLOCATOR_REBALANCE for a in eng.alerts.history)


# --- 4. portfolio risk overrides per-strategy approval ---------------------
def test_portfolio_risk_overrides_strategy_approval(tmp_path):
    reg, alloc, eng = _make_engine(tmp_path, _good_signals)
    eng.initialize(datetime(2025, 1, 6, tzinfo=UTC))

    # Pre-load gross exposure just under the 80% aggregate cap so any new order breaches it.
    eng.seed_position("XXX", notional=79000, direction=1)

    sig = _good_signals(reg.get("alpha"), {}, {"risk_on": True})[0]
    state = eng.portfolio_state()
    strat_dec = reg.get("alpha").risk_manager.validate_signal(sig, state)
    assert strat_dec.approved                                    # per-strategy says YES

    rec = eng._process_signal("alpha", reg.get("alpha"), sig)
    assert rec.stage == "blocked_portfolio"                      # portfolio vetoes
    assert not rec.approved
    assert len(eng.executor.submitted) == 0


# --- 5. --no-portfolio-risk debug bypass -----------------------------------
def test_no_portfolio_risk_bypass(tmp_path):
    reg, alloc, eng = _make_engine(tmp_path, _good_signals, use_pr=False)
    eng.initialize(datetime(2025, 1, 6, tzinfo=UTC))
    eng.seed_position("XXX", notional=79000, direction=1)        # would be blocked WITH portfolio risk
    rec = eng._process_signal("alpha", reg.get("alpha"), _good_signals(reg.get("alpha"), {}, {})[0])
    assert rec.stage == "submitted"
    assert rec.approved
