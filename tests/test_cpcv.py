"""
tests/test_cpcv.py
==================
The invariants that make CPCV worth trusting: combinatorial counts, the
zero-overlap purge guarantee, the non-adjacent-groups regression (the
merged-span bug), embargo enforcement, and lawful path stitching.
"""

from __future__ import annotations

import numpy as np
import pytest

from backtest.cpcv import CPCV


HORIZON = 10
N_SAMPLES = 600


@pytest.fixture()
def cv() -> CPCV:
    return CPCV(n_groups=6, n_test_groups=2, embargo_pct=0.01)


def _t1(n: int, h: int = HORIZON) -> np.ndarray:
    return np.minimum(np.arange(n) + h, n - 1)


def test_combinatorial_counts(cv):
    splits = list(cv.split(N_SAMPLES, t1=_t1(N_SAMPLES)))
    assert len(splits) == 15                       # C(6,2)
    assert cv.n_paths == 5                         # k*C(N,k)/N
    # Each group is a test group in exactly C(N-1, k-1) = 5 splits.
    counts = {g: 0 for g in range(6)}
    for _, test_groups, _, _ in splits:
        for g in test_groups:
            counts[g] += 1
    assert all(c == 5 for c in counts.values())


def test_purge_zero_label_overlap(cv):
    """THE invariant: no surviving train sample's label interval
    [i, t1_i] may overlap any test block's label window."""
    t1 = _t1(N_SAMPLES)
    bounds = cv.group_bounds(N_SAMPLES)
    for _, test_groups, train, test in cv.split(N_SAMPLES, t1=t1):
        assert len(np.intersect1d(train, test)) == 0
        for g in test_groups:
            a, b = bounds[g]
            label_end = t1[a:b].max()
            for i in train:
                # overlap iff i <= label_end and t1[i] >= a
                assert not (i <= label_end and t1[i] >= a), \
                    f"train {i} (label ->{t1[i]}) overlaps test block [{a},{label_end}]"


def test_non_adjacent_groups_not_nuked(cv):
    """Regression for the merged-span bug: test groups {0, 5} must NOT
    purge the middle groups 1-4 -- most of the timeline stays trainable."""
    for _, test_groups, train, _ in cv.split(N_SAMPLES, t1=_t1(N_SAMPLES)):
        if set(test_groups) == {0, 5}:
            # 4 train groups of 100 bars; purge+embargo trims edges only.
            assert len(train) > 0.85 * 400
            break
    else:
        pytest.fail("split {0,5} not generated")


def test_embargo_bars_after_each_block(cv):
    t1 = _t1(N_SAMPLES)
    embargo = int(N_SAMPLES * cv.embargo_pct)
    bounds = cv.group_bounds(N_SAMPLES)
    for _, test_groups, train, _ in cv.split(N_SAMPLES, t1=t1):
        for g in test_groups:
            a, b = bounds[g]
            label_end = t1[a:b].max()
            forbidden = set(range(label_end + 1, label_end + embargo + 1))
            assert forbidden.isdisjoint(train)


def test_path_stitching_is_lawful(cv):
    """Each path covers every group exactly once, uses only splits where
    that group was in test, and no (group, split) slot is reused."""
    list(cv.split(N_SAMPLES, t1=_t1(N_SAMPLES)))   # exercises generator
    test_membership = {}
    from itertools import combinations
    for sid, tg in enumerate(combinations(range(6), 2)):
        test_membership[sid] = set(tg)
    paths = cv.backtest_paths()
    assert len(paths) == 5
    used = set()
    for path in paths:
        groups = [g for g, _ in path]
        assert sorted(groups) == list(range(6))    # full timeline, once each
        for g, sid in path:
            assert g in test_membership[sid]       # only genuine OOS slots
            assert (g, sid) not in used            # never reused across paths
            used.add((g, sid))


def test_point_labels_default():
    """t1=None -> point labels: only the test blocks + embargo are excluded."""
    cv = CPCV(n_groups=4, n_test_groups=1, embargo_pct=0.0)
    for _, tg, train, test in cv.split(400):
        assert len(train) + len(test) == 400
