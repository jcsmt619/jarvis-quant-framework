"""
tests/test_triple_barrier.py
============================
Ground-truth barrier touches on constructed paths, the prefix-consistency
guarantee (a label never changes when data extends), causal vol, positional
vertical barriers, side-flipping, and the CPCV handshake.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.cpcv import CPCV
from backtest.triple_barrier import TripleBarrier


def _series(vals) -> pd.Series:
    idx = pd.bdate_range("2024-01-01", periods=len(vals))
    return pd.Series(np.asarray(vals, dtype=float), index=idx)


@pytest.fixture()
def tb() -> TripleBarrier:
    # vol_span tiny so the target settles fast on synthetic data
    return TripleBarrier(pt_mult=2.0, sl_mult=1.0, max_hold_bars=5, vol_span=10)


def test_ground_truth_touches(tb):
    """Constructed paths where the correct label is known by hand."""
    base = [100.0] * 30                       # settle vol on +/-1% wiggles
    wiggle = [100 * (1 + 0.01 * (-1) ** i) for i in range(30)]
    up = wiggle + [100, 108, 116, 100, 100, 100]     # blasts through PT
    dn = wiggle + [100, 92, 84, 100, 100, 100]       # crashes through SL
    fl = wiggle + [100, 100.1, 99.9, 100.1, 99.9, 100.05]  # nothing touched

    for vals, expected_touch, expected_bin in (
            (up, "pt", 1), (dn, "sl", -1), (fl, "time", 1)):
        px = _series(vals)
        t0 = px.index[30]
        out = tb.label(px, t_events=[t0])
        assert out.loc[t0, "touch"] == expected_touch
        assert out.loc[t0, "bin"] == expected_bin
        if expected_touch != "time":
            assert out.loc[t0, "t1"] < px.index[35]  # touched before vertical


def test_prefix_consistency(tb):
    """THE look-ahead guarantee: once an event's full window exists, its
    label NEVER changes as more data arrives."""
    rng = np.random.default_rng(3)
    full = _series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))))
    short = full.iloc[:200]
    lab_full = tb.label(full)
    lab_short = tb.label(short)
    pd.testing.assert_frame_equal(lab_full.loc[lab_short.index], lab_short)


def test_incomplete_windows_dropped(tb):
    """Events too close to the end are unknowable -> not labeled."""
    rng = np.random.default_rng(4)
    px = _series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 100))))
    out = tb.label(px)
    # nothing labeled within max_hold_bars of the end
    assert out.index.max() <= px.index[-1 - tb.max_hold_bars]


def test_vertical_barrier_is_positional(tb):
    """Touch never occurs more than max_hold_bars BARS after entry --
    across weekends included (the calendar-days bug regression)."""
    rng = np.random.default_rng(5)
    px = _series(100 * np.exp(np.cumsum(rng.normal(0, 0.001, 120))))
    out = tb.label(px)
    pos = px.index.searchsorted
    holds = pos(out["t1"].values) - pos(out.index.values)
    assert (holds <= tb.max_hold_bars).all()
    assert (holds >= 0).all()


def test_side_flips_labels(tb):
    """A short-side event labels the mirrored path identically."""
    wiggle = [100 * (1 + 0.01 * (-1) ** i) for i in range(30)]
    up = _series(wiggle + [100, 108, 116, 100, 100, 100])
    t0 = up.index[30]
    long_lab = tb.label(up, t_events=[t0])
    short_lab = tb.label(up, t_events=[t0],
                         side=pd.Series([-1.0], index=[t0]))
    assert long_lab.loc[t0, "touch"] == "pt"
    assert short_lab.loc[t0, "touch"] == "sl"    # same path, opposite side
    assert short_lab.loc[t0, "ret"] == pytest.approx(-long_lab.loc[t0, "ret"])


def test_min_ret_filters_thin_targets():
    tb = TripleBarrier(max_hold_bars=5, vol_span=10, min_ret=0.05)
    calm = _series([100 * (1 + 0.0001 * (-1) ** i) for i in range(60)])
    assert len(tb.label(calm)) == 0              # vol ~ 1bp << 5% floor


def test_cpcv_handshake(tb):
    """Labels' t1 feeds CPCV directly (index = EVENT index, so touch times
    map into event-row space) and the purge invariant holds -- for SPARSE
    events too, where passing the bar index would misalign the purge."""
    rng = np.random.default_rng(6)
    px = _series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 400))))
    labels = tb.label(px, t_events=px.index[::3])    # sparse events
    n = len(labels)
    # Touch time -> first event row at/after it (conservative span).
    t1_rows = np.asarray(labels.index.searchsorted(labels["t1"].values))
    cv = CPCV(n_groups=4, n_test_groups=1, embargo_pct=0.0)
    bounds = cv.group_bounds(n)
    for _, tg, train, test in cv.split(n, t1=labels["t1"], index=labels.index):
        a, b = bounds[tg[0]]
        label_end = min(int(t1_rows[a:b].max()), n - 1)
        for i in train:
            assert not (i <= label_end and t1_rows[i] >= a), \
                "train label interval overlaps test block"
