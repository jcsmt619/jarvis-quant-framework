"""
tests/test_risk_manager.py
==========================
Verifies the STEP 5 risk layer: Kelly sizing caps, the three escalating circuit
breakers, daily reset, and the hard kill-switch lock file.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from core.risk_manager import (
    PortfolioState,
    RiskAction,
    RiskLimits,
    RiskManager,
    TradeSignal,
)


def _rm(tmp_path, **kw):
    limits = RiskLimits(**kw)
    return RiskManager(limits=limits, initial_capital=100000.0, lock_file=tmp_path / "halt.lock")


# --- Kelly sizing ----------------------------------------------------------
def test_kelly_warmup_returns_zero(tmp_path):
    rm = _rm(tmp_path, min_trades=20)
    for _ in range(5):
        rm.record_trade_pnl(100.0)
    assert rm.kelly_fraction_value() == 0.0  # not enough trades


def test_kelly_fraction_capped_at_concentration(tmp_path):
    rm = _rm(tmp_path, min_trades=10, max_position_pct=0.75, kelly_fraction=1.0)
    # High win rate + big payoff -> raw Kelly ~0.89, must clamp to the 0.75 cap.
    for _ in range(90):
        rm.record_trade_pnl(500.0)
    for _ in range(10):
        rm.record_trade_pnl(-50.0)
    assert rm.kelly_fraction_value() == pytest.approx(0.75)


def test_leverage_only_unlocks_when_accelerating(tmp_path):
    rm = _rm(tmp_path, min_trades=10, max_position_pct=0.75, max_leverage=4.0, kelly_fraction=1.0)
    for _ in range(90):
        rm.record_trade_pnl(500.0)
    for _ in range(10):
        rm.record_trade_pnl(-50.0)
    assert rm.target_leverage(accelerating=False) == pytest.approx(0.75)
    assert rm.target_leverage(accelerating=True) == pytest.approx(4.0)


# --- circuit breakers ------------------------------------------------------
def test_daily_dd_reduce_then_halt(tmp_path):
    rm = _rm(tmp_path)
    day = datetime(2025, 1, 2, 9, 30)
    assert rm.update(day, 100000.0) == RiskAction.NORMAL
    # -5% intraday -> reduce 50%
    assert rm.update(day.replace(hour=11), 95000.0) == RiskAction.REDUCE_50
    assert rm.size_multiplier(RiskAction.REDUCE_50) == 0.5
    # -7% intraday -> close all + halt for the day
    assert rm.update(day.replace(hour=13), 93000.0) == RiskAction.CLOSE_ALL_HALT_DAY
    # stays halted for the remainder of the day even if it recovers
    assert rm.update(day.replace(hour=15), 99000.0) == RiskAction.CLOSE_ALL_HALT_DAY


def test_new_day_resets_daily_breaker(tmp_path):
    rm = _rm(tmp_path)
    d1 = datetime(2025, 1, 2, 10)
    rm.update(d1, 100000.0)
    rm.update(d1.replace(hour=13), 93000.0)  # halt day 1
    assert rm.halted_today is True
    d2 = datetime(2025, 1, 3, 10)
    action = rm.update(d2, 93000.0)  # new day resets daily open
    assert rm.halted_today is False
    assert action == RiskAction.NORMAL


def test_peak_dd_writes_lock_and_kill_switch(tmp_path):
    rm = _rm(tmp_path, peak_dd_lock=0.25)
    rm.update(datetime(2025, 1, 2), 120000.0)   # new peak
    action = rm.update(datetime(2025, 1, 10), 85000.0)  # ~29% below peak
    assert action == RiskAction.CLOSE_ALL_HALT_HARD
    assert rm.hard_halted is True
    assert rm.lock_file.exists()
    # A fresh manager must refuse to trade while the lock exists.
    fresh = RiskManager(lock_file=rm.lock_file)
    assert fresh.kill_switch_engaged() is True


def test_clear_lock(tmp_path):
    rm = _rm(tmp_path, peak_dd_lock=0.25)
    rm.update(datetime(2025, 1, 2), 120000.0)
    rm.update(datetime(2025, 1, 10), 80000.0)
    assert rm.lock_file.exists()
    rm.clear_lock()
    assert not rm.lock_file.exists()
    assert rm.hard_halted is False


# --- weekly breaker + settings + validate_signal --------------------------
def test_weekly_breaker_halts(tmp_path):
    rm = _rm(tmp_path, weekly_dd_halt=0.15, daily_dd_halt=0.99)  # isolate weekly
    mon = datetime(2025, 3, 3, 10)  # Monday
    assert rm.update(mon, 100000.0) == RiskAction.NORMAL
    # Same ISO week, later day, -16% from week open -> weekly halt.
    wed = datetime(2025, 3, 5, 10)
    assert rm.update(wed, 84000.0) == RiskAction.CLOSE_ALL_HALT_WEEK
    assert rm.halted_week is True


def test_from_settings_loads_yaml():
    # settings.yaml carries the course-aligned "Survival First" values
    # (drift fix ordered 2026-07-02): no gross leverage, half Kelly,
    # 1.5% per-trade risk cap, LETFs flat (they're internally 3x already).
    limits = RiskLimits.from_settings()
    assert limits.max_total_exposure == 1.0
    assert limits.max_concurrent == 5
    assert limits.letf_max_leverage == 1.0
    assert limits.kelly_fraction == 0.5
    assert limits.risk_per_trade == 0.015
    assert limits.peak_dd_lock == 0.25


def _state(**kw):
    base = dict(equity=100000.0, cash=100000.0, buying_power=300000.0,
                positions={}, circuit_breaker_status="normal")
    base.update(kw)
    return PortfolioState(**base)


def _sig(**kw):
    base = dict(symbol="BTC-USD", direction=1, asset_class="crypto", price=100.0,
                atr=2.0, stop_loss=95.0, regime="confirmed_low_vol",
                confirmed_breakout=True, win_rate=0.55, bid_ask_spread=0.001)
    base.update(kw)
    return TradeSignal(**base)


def test_validate_rejects_missing_stop(tmp_path):
    rm = _rm(tmp_path)
    d = rm.validate_signal(_sig(stop_loss=None), _state())
    assert d.approved is False
    assert "stop" in d.rejection_reason.lower()


def test_validate_rejects_wide_spread(tmp_path):
    rm = _rm(tmp_path, max_spread=0.01)
    d = rm.validate_signal(_sig(bid_ask_spread=0.02), _state())
    assert d.approved is False
    assert "spread" in d.rejection_reason.lower()


def test_validate_uncertain_regime_goes_to_cash(tmp_path):
    rm = _rm(tmp_path)
    d = rm.validate_signal(_sig(regime="uncertain"), _state())
    assert d.approved is False
    assert "cash" in d.rejection_reason.lower()


def test_validate_leverage_matrix(tmp_path):
    rm = _rm(tmp_path)
    crypto = rm.validate_signal(_sig(asset_class="crypto"), _state())
    letf = rm.validate_signal(_sig(asset_class="letf"), _state())
    assert crypto.approved and crypto.modified_signal.leverage == pytest.approx(3.0)
    assert letf.approved and letf.modified_signal.leverage == pytest.approx(4.0)
    # Position clipped to the 75% single-position cap.
    assert crypto.modified_signal.target_notional == pytest.approx(75000.0)


def test_validate_max_concurrent(tmp_path):
    rm = _rm(tmp_path, max_concurrent=3)
    positions = {f"P{i}": {"notional": 1000.0} for i in range(3)}
    d = rm.validate_signal(_sig(symbol="NEW"), _state(positions=positions))
    assert d.approved is False
    assert "concurrent" in d.rejection_reason.lower()


def test_validate_low_win_rate_forces_flat_leverage(tmp_path):
    rm = _rm(tmp_path)
    d = rm.validate_signal(_sig(win_rate=0.30), _state())
    assert d.approved is True
    assert d.modified_signal.leverage == pytest.approx(1.0)


def test_correlation_reject_and_reduce(tmp_path):
    rm = _rm(tmp_path, corr_threshold=0.85, corr_reduce=0.25)
    rets = np.linspace(-0.01, 0.02, 40)
    held = {"SOXL": {"notional": 1000.0, "returns": rets, "sector": "semis"}}
    # Highly correlated, DIFFERENT sector -> reject.
    reject = rm.validate_signal(_sig(symbol="BTC-USD", sector="crypto", returns=rets),
                                _state(positions=held))
    assert reject.approved is False and "corr" in reject.rejection_reason.lower()
    # Highly correlated, SAME sector -> allowed but size reduced.
    keep = rm.validate_signal(_sig(symbol="TQQQ", asset_class="letf", sector="semis", returns=rets),
                              _state(positions=held))
    assert keep.approved is True
    assert any("correlated" in m for m in keep.modifications)
