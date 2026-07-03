"""
tests/test_runner_exit.py
=========================
Runner Mode state machine: bank at +1.5R, breakeven stop, 2x ATR trail --
verifying every action only TIGHTENS risk (stop never loosens, size only shrinks).
"""

from __future__ import annotations

import pytest

from utils.runner_exit import RunnerManager


def _mgr():
    m = RunnerManager(trigger_r=1.5, bank_fraction=0.5, trail_atr_mult=2.0)
    assert m.open_trade(entry_price=100.0, initial_stop=96.0)   # R = 4.0
    return m


def test_pre_trigger_full_size_and_initial_stop():
    m = _mgr()
    act = m.update(price=103.0, atr=2.0)      # +0.75R: below trigger
    assert act.size_multiplier == 1.0
    assert act.stop_level == 96.0             # initial stop untouched
    assert not act.banked_this_bar and not act.exited


def test_bank_fires_at_trigger_with_breakeven_stop():
    m = _mgr()
    act = m.update(price=106.0, atr=2.0)      # +1.5R exactly
    assert act.banked_this_bar
    assert act.size_multiplier == 0.5         # 50% banked
    assert act.stop_level >= 100.0            # breakeven or better (2xATR trail = 102)
    assert not act.exited


def test_trail_ratchets_up_never_down():
    m = _mgr()
    m.update(price=106.0, atr=2.0)            # bank; stop -> max(100, 102) = 102
    a1 = m.update(price=112.0, atr=2.0)       # trail -> 108
    assert a1.stop_level == pytest.approx(108.0)
    a2 = m.update(price=109.0, atr=2.0)       # price dips: trail candidate 105 < 108
    assert a2.stop_level == pytest.approx(108.0)   # NEVER loosens
    assert not a2.exited


def test_runner_exit_on_stop_breach_is_risk_free():
    m = _mgr()
    m.update(price=106.0, atr=2.0)            # banked, stop >= breakeven
    act = m.update(price=99.0, atr=2.0)       # breach
    assert act.exited and act.size_multiplier == 0.0
    # Once banked, the trade can no longer lose: exit stop >= entry.
    assert act.stop_level >= 100.0
    assert not m.active                       # state reset for next trade


def test_invalid_stop_refuses_to_arm():
    m = RunnerManager()
    assert not m.open_trade(entry_price=100.0, initial_stop=101.0)  # stop above price
    act = m.update(price=120.0, atr=2.0)
    assert act.size_multiplier == 1.0 and not act.exited            # inert


def test_uncapped_upside_runs_beyond_old_cap():
    """A strong trend is ridden far past the old ~1.35R harvest point."""
    m = _mgr()
    m.update(price=106.0, atr=2.0)                    # bank at +1.5R
    price = 106.0
    for _ in range(20):                               # trend marches up
        price += 2.0
        act = m.update(price=price, atr=2.0)
        assert not act.exited                         # trail never catches a clean trend
    # +46 points on R=4 => the runner half is at +11.5R, far beyond 1.88R max.
    assert (price - 100.0) / 4.0 > 10.0


# --- short-side mirror ------------------------------------------------------
def test_short_runner_mirrors_long():
    m = RunnerManager(trigger_r=1.5, bank_fraction=0.5, trail_atr_mult=2.0)
    assert m.open_trade(entry_price=100.0, initial_stop=104.0, direction=-1)  # R = 4
    a0 = m.update(price=97.0, atr=2.0)                # +0.75R: pre-trigger
    assert a0.size_multiplier == 1.0 and a0.stop_level == 104.0
    a1 = m.update(price=94.0, atr=2.0)                # +1.5R: bank
    assert a1.banked_this_bar and a1.size_multiplier == 0.5
    assert a1.stop_level <= 100.0                     # breakeven or better (trail=98)
    a2 = m.update(price=90.0, atr=2.0)                # trail -> 94
    assert a2.stop_level == pytest.approx(94.0)
    a3 = m.update(price=92.0, atr=2.0)                # bounce: candidate 96 > 94
    assert a3.stop_level == pytest.approx(94.0)       # NEVER loosens for shorts either
    a4 = m.update(price=95.0, atr=2.0)                # breach above stop
    assert a4.exited and a4.size_multiplier == 0.0


def test_short_invalid_stop_refuses_to_arm():
    m = RunnerManager()
    assert not m.open_trade(entry_price=100.0, initial_stop=99.0, direction=-1)  # stop on profit side
