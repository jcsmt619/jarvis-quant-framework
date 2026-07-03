"""
tests/test_intraday_pulse.py
============================
Offline mechanics: t+1 fills are real (a last-bar signal can't trade),
the sigma floor suppresses noise-minted signals, a constructed reversion
yields the hand-computable gross edge, and friction is monotone in the
half-spread assumption.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.intraday_pulse import (
    LOOKBACK,
    PER_LEG,
    round_trip_friction,
    simulate,
)


def _bars(closes, opens=None) -> pd.DataFrame:
    idx = pd.date_range("2026-06-29 13:30", periods=len(closes), freq="1min")
    closes = np.asarray(closes, dtype=float)
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    return pd.DataFrame({"open": opens, "close": closes}, index=idx)


def _oscillating_pair(n_cycles=6, amp=0.004):
    """B fixed at 100; A oscillates around 100 so the log-spread swings
    +/- amp with a period long enough to arm the rolling z."""
    n = LOOKBACK + n_cycles * 40 + 10
    t = np.arange(n)
    a = 100 * np.exp(amp * np.sin(2 * np.pi * t / 40)
                     + 0.0003 * np.sin(2 * np.pi * t / 7))
    b = np.full(n, 100.0)
    return _bars(a), _bars(b)


def test_reversion_pair_trades_and_gross_positive():
    a, b = _oscillating_pair()
    res = simulate(a, b)
    assert res["n_trades"] >= 3
    # A genuine oscillator harvested with reversion must be gross-positive.
    assert res["gross_per_trade_bps"] > 0
    assert set(res["ladder"]) == {1.0, 2.0, 5.0}


def test_sigma_floor_kills_noise_signals():
    """Near-identical series: spread sigma ~ 1e-7 -- below the floor, so
    z is NaN and NO trades can be minted from float noise."""
    rng = np.random.default_rng(0)
    n = LOOKBACK + 200
    base = 100 + np.zeros(n)
    a = _bars(base + rng.normal(0, 1e-5, n))
    b = _bars(base)
    assert simulate(a, b)["n_trades"] == 0


def test_t_plus_1_fill_last_bar_signal_cannot_trade():
    """A huge z on the FINAL bar has no next bar to fill on -> no entry."""
    a, b = _oscillating_pair(n_cycles=1)
    # Flatten everything after the first cycle so no earlier signals fire,
    # then spike the last close.
    a_flat = a.copy()
    a_flat.iloc[LOOKBACK + 5:, :] = 100.0
    a_flat.iloc[-1, :] = 108.0                      # massive spread move
    res = simulate(a_flat, _bars(np.full(len(a_flat), 100.0)))
    assert res["n_trades"] == 0                     # decided, never filled


def test_friction_monotone_in_half_spread():
    f1 = round_trip_friction(100.0, 100.0, 1.0)
    f2 = round_trip_friction(100.0, 100.0, 2.0)
    f5 = round_trip_friction(100.0, 100.0, 5.0)
    assert f1 < f2 < f5
    # 4 min-ticket commissions are always present.
    assert f1 >= 4 * 1.0
    a, b = _oscillating_pair()
    res = simulate(a, b)
    nets = [res["ladder"][hs]["net_total"] for hs in (1.0, 2.0, 5.0)]
    assert nets[0] > nets[1] > nets[2]              # pessimism costs money


def test_gross_edge_magnitude_sane():
    """amp=0.004 oscillator: entries near the extremes, exits near the
    mean -> per-trade gross must be within the geometry's bounds (0, 2*amp)
    in log terms, i.e. (0, 80] bps of the 2-leg notional / 2."""
    a, b = _oscillating_pair(amp=0.004)
    res = simulate(a, b)
    per_trade_log = res["gross_per_trade_bps"] / 1e4 * 2  # undo /(2*PER_LEG)
    assert 0 < per_trade_log <= 2 * 0.004 + 1e-6
