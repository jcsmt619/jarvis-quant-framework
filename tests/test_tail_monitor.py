"""
tests/test_tail_monitor.py
==========================
Proactive tail-risk monitor: level thresholds (incl. exact boundaries), cap
monotonicity, order clipping/rejection, and the RiskManager veto integration.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.risk_manager import PortfolioState, RiskLimits, RiskManager, TradeSignal
from risk.tail_monitor import TailRiskLimits, TailRiskMonitor, vix_proxy_from_returns


def _mon() -> TailRiskMonitor:
    return TailRiskMonitor(TailRiskLimits())


# --- 1. levels + boundaries -------------------------------------------------
def test_levels_and_exact_boundaries():
    m = _mon()
    assert m.cap_for(12.0) == (0, float("inf"))
    assert m.cap_for(25.0) == (0, float("inf"))   # spec is "> 25": exactly 25 = NORMAL
    assert m.cap_for(25.01) == (1, 0.80)
    assert m.cap_for(35.0) == (1, 0.80)
    assert m.cap_for(35.01) == (2, 0.50)
    assert m.cap_for(50.0) == (2, 0.50)
    assert m.cap_for(50.01) == (3, 0.00)
    assert m.cap_for(80.0) == (3, 0.00)


def test_cap_is_monotone_in_vix():
    m = _mon()
    caps = [m.cap_for(v)[1] for v in np.linspace(5, 90, 200)]
    assert all(a >= b for a, b in zip(caps, caps[1:]))   # higher vix never loosens


# --- 2. update() transitions + clamp_target ---------------------------------
def test_update_transitions_and_clamp():
    m = _mon()
    assert m.update(18.0) == float("inf")
    assert m.clamp_target(1.25) == 1.25                  # NORMAL: untouched (even leveraged)
    assert m.update(28.0) == 0.80                        # CAUTION
    assert m.clamp_target(1.25) == 0.80
    assert m.update(42.0) == 0.50                        # DANGER
    assert m.clamp_target(0.30) == 0.30                  # below cap: untouched
    assert m.update(55.0) == 0.00                        # CRISIS -> cash
    assert m.clamp_target(0.95) == 0.00
    assert [e["to"] for e in m.events] == ["CAUTION", "DANGER", "CRISIS"]


# --- 3. order-flow veto: clip then block ------------------------------------
def _state(gross: float) -> PortfolioState:
    return PortfolioState(equity=100000.0, cash=100000.0, buying_power=100000.0,
                          positions={"XXX": {"notional": gross, "direction": 1}})


def _sig(notional: float) -> TradeSignal:
    return TradeSignal(symbol="SPY", direction=1, asset_class="equity", price=100.0,
                       atr=2.0, stop_loss=96.0, target_notional=notional)


def test_validate_signal_clips_then_blocks():
    m = _mon()
    m.update(28.0)                                        # cap 80% -> $80k max gross
    ok = m.validate_signal(_sig(10000.0), _state(gross=50000.0))
    assert ok is None                                     # 60k <= 80k: no issue
    clipped = m.validate_signal(_sig(50000.0), _state(gross=50000.0))
    assert clipped.approved and clipped.modified_signal.target_notional == pytest.approx(30000.0)
    blocked = m.validate_signal(_sig(10000.0), _state(gross=80000.0))
    assert blocked is not None and not blocked.approved   # cap reached -> veto


# --- 4. RiskManager graft: tail cap is the FINAL word ------------------------
def test_riskmanager_tail_veto_overrides_approval(tmp_path):
    m = _mon()
    m.update(60.0)                                        # CRISIS: cap 0 -> cash only
    rm = RiskManager(limits=RiskLimits(), initial_capital=100000.0,
                     lock_file=tmp_path / "halt.lock", tail_monitor=m)
    sig = TradeSignal(symbol="SPY", direction=1, asset_class="equity", price=100.0,
                      atr=2.0, stop_loss=96.0, regime="confirmed_low_vol",
                      confirmed_breakout=True, win_rate=0.60, bid_ask_spread=0.001)
    state = PortfolioState(equity=100000.0, cash=100000.0, buying_power=100000.0)
    decision = rm.validate_signal(sig, state)
    assert not decision.approved                          # buy signal vetoed outright
    assert "TAIL RISK CRISIS" in decision.rejection_reason

    m.update(15.0)                                        # back to NORMAL
    assert rm.validate_signal(sig, state).approved        # same signal now passes


# --- 5. vol proxy for VIX-less assets ----------------------------------------
def test_vix_proxy_scales_with_realized_vol():
    rng = np.random.default_rng(0)
    calm = vix_proxy_from_returns(rng.normal(0, 0.006, 60))    # ~9.5 annualized
    wild = vix_proxy_from_returns(rng.normal(0, 0.035, 60))    # ~55 annualized
    assert calm < 25 < wild
