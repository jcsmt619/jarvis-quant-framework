"""
tests/test_threshold_grid.py
============================
The honest coach's contract: a grid over noise must not emit a tuning
recommendation. DSR stamp present, plateau detection works, and the
all-losers case says "nothing to tune".
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis.intraday_pulse import threshold_grid
from tests.test_intraday_pulse import _bars, _oscillating_pair


def test_grid_on_genuine_oscillator_stamps_winner():
    a, b = _oscillating_pair(n_cycles=10, amp=0.006)   # big, real reversion
    g = threshold_grid(a, b)
    assert g["n_configs"] == 21
    assert "best" in g
    assert 0.0 <= g["dsr"] <= 1.0                      # stamp present
    assert isinstance(g["plateau"], bool)
    # A genuine wide oscillator should be profitable across neighboring
    # thresholds -- plateau, not isolated peak.
    if g["best"]["net_total"] > 0:
        assert g["plateau"]


def test_grid_on_noise_never_recommends():
    """Pure noise pair: whatever config 'wins' must either lose net or
    carry a DSR far below the 95% bar -- the coach cannot manufacture a
    deployable setting from noise."""
    rng = np.random.default_rng(11)
    n = 800
    a = _bars(100 * np.exp(np.cumsum(rng.normal(0, 0.0008, n))))
    b = _bars(100 * np.exp(np.cumsum(rng.normal(0, 0.0008, n))))
    g = threshold_grid(a, b)
    if "best" not in g:                                # too few trades: fine
        return
    assert g["best"]["net_total"] <= 0 or g["dsr"] < 0.95


def test_grid_handles_no_trades():
    flat_a, flat_b = _bars(np.full(200, 100.0)), _bars(np.full(200, 100.0))
    g = threshold_grid(flat_a, flat_b)
    assert "best" not in g
    assert "verdict" in g
