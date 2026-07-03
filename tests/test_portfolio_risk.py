"""
tests/test_portfolio_risk.py
============================
Covers the portfolio-level risk manager that sits ABOVE the per-strategy managers:
aggregate exposure, cross-strategy single-symbol aggregation, total leverage,
portfolio drawdown, and the hierarchy (both layers must approve).
"""

from __future__ import annotations

import pytest

from core.risk_manager import (
    PortfolioRiskLimits,
    PortfolioRiskManager,
    PortfolioState,
    RiskLimits,
    RiskManager,
    TradeSignal,
)


def _state(equity=100000.0, positions=None, **kw):
    return PortfolioState(equity=equity, cash=equity, buying_power=equity * 3,
                          positions=positions or {}, **kw)


# --- aggregate exposure ----------------------------------------------------
def test_aggregate_exposure_rejects_second_strategy():
    prm = PortfolioRiskManager(PortfolioRiskLimits(
        max_aggregate_exposure=0.80, max_single_symbol=1.0, max_portfolio_leverage=10.0))
    # Strategy_A already holds 30%; Strategy_B wants +60% -> 90% > 80%.
    state = _state(positions={"AAA": {"notional": 30000.0, "direction": 1}})
    sig = TradeSignal(symbol="BBB", direction=1, target_notional=60000.0)
    d = prm.validate_signal(sig, "Strategy_B", state)
    assert d.approved is False
    assert "aggregate" in d.rejection_reason.lower()
    assert prm.blocked_log[-1]["strategy"] == "Strategy_B"


# --- single-symbol aggregation across strategies ---------------------------
def test_symbol_aggregation_reduces_size():
    prm = PortfolioRiskManager(PortfolioRiskLimits(
        max_aggregate_exposure=5.0, max_single_symbol=0.15, max_portfolio_leverage=10.0))
    # Strategy_A long SPY 10%; Strategy_B wants +8% -> 18% > 15% -> reduce to 5%.
    state = _state(positions={"SPY": {"notional": 10000.0, "direction": 1}})
    sig = TradeSignal(symbol="SPY", direction=1, target_notional=8000.0)
    d = prm.validate_signal(sig, "Strategy_B", state)
    assert d.approved is True
    assert d.modified_signal.target_notional == pytest.approx(5000.0)   # 15% - 10%
    assert any("single-symbol cap" in m for m in d.modifications)


# --- total leverage --------------------------------------------------------
def test_total_leverage_rejects_second_strategy():
    prm = PortfolioRiskManager(PortfolioRiskLimits(
        max_aggregate_exposure=10.0, max_single_symbol=10.0, max_portfolio_leverage=1.25))
    # Strategy_A at 1.25x; Strategy_B adds 0.5x -> 1.75x > 1.25x.
    state = _state(positions={"AAA": {"notional": 125000.0, "direction": 1}})
    sig = TradeSignal(symbol="BBB", direction=1, target_notional=50000.0)
    d = prm.validate_signal(sig, "Strategy_B", state)
    assert d.approved is False
    assert "leverage" in d.rejection_reason.lower()


# --- portfolio drawdown ----------------------------------------------------
def test_portfolio_dd_triggers(tmp_path):
    prm = PortfolioRiskManager(
        PortfolioRiskLimits(max_aggregate_exposure=10.0, max_single_symbol=10.0,
                            max_portfolio_leverage=10.0,
                            daily_dd_reduce=0.02, daily_dd_zero=0.03, peak_dd_halt=0.10),
        lock_file=tmp_path / "pl.lock",
    )
    sig = TradeSignal(symbol="X", direction=1, target_notional=10000.0)

    # 2.5% daily DD -> halve
    d = prm.validate_signal(sig, "S", _state(daily_drawdown=0.025))
    assert d.approved and d.modified_signal.target_notional == pytest.approx(5000.0)

    # 3.5% daily DD -> block
    d = prm.validate_signal(sig, "S", _state(daily_drawdown=0.035))
    assert not d.approved

    # 12% peak DD -> halt + lock
    d = prm.validate_signal(sig, "S", _state(drawdown=0.12))
    assert not d.approved
    assert prm.kill_switch_engaged() is True


# --- hierarchy: per-strategy risk still fires ------------------------------
def test_per_strategy_risk_not_bypassed(tmp_path):
    strat_rm = RiskManager(RiskLimits(), lock_file=tmp_path / "s.lock")
    prm = PortfolioRiskManager(
        PortfolioRiskLimits(max_aggregate_exposure=0.80, max_single_symbol=1.0, max_portfolio_leverage=10.0),
        lock_file=tmp_path / "p.lock",
    )

    # 1) A signal with NO stop-loss is rejected by the PER-STRATEGY manager.
    no_stop = TradeSignal(symbol="X", direction=1, price=100.0, atr=2.0, stop_loss=None,
                          regime="confirmed_low_vol", confirmed_breakout=True, win_rate=0.6,
                          asset_class="crypto")
    strat_decision = strat_rm.validate_signal(no_stop, _state())
    assert strat_decision.approved is False   # per-strategy layer fires -> never reaches portfolio

    # 2) A signal the strategy APPROVES can still be VETOED by the portfolio manager.
    ok = TradeSignal(symbol="Y", direction=1, price=100.0, atr=2.0, stop_loss=95.0,
                     regime="confirmed_low_vol", confirmed_breakout=True, win_rate=0.6,
                     asset_class="crypto")
    sd = strat_rm.validate_signal(ok, _state())
    assert sd.approved is True
    # Portfolio book already near the 80% aggregate cap -> portfolio adds a veto.
    pstate = _state(positions={"AAA": {"notional": 75000.0, "direction": 1}})
    pd = prm.validate_signal(sd.modified_signal or ok, "Strategy_A", pstate)
    assert pd.approved is False
    assert "aggregate" in pd.rejection_reason.lower()
