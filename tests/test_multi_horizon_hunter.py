"""
tests/test_multi_horizon_hunter.py
==================================
Multi-horizon hunter: tail labels must be NaN (never fake 0s), boundary purge
must remove overlapping labels, and target values must be exactly right.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.multi_horizon_hunter import MultiHorizonCausalHunter


def _df(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-01", periods=n)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, n))), index=idx)
    return pd.DataFrame({"close": close})


# --- 1. tail labels are NaN, not fake zeros ---------------------------------
def test_tail_labels_are_nan_not_zero():
    df = _df()
    hunter = MultiHorizonCausalHunter(horizons=[1, 3, 5])
    t = hunter.generate_causal_targets(df)
    for h in (1, 3, 5):
        col = t[f"target_tplus_{h}"]
        assert col.iloc[-h:].isna().all()          # no future -> no label
        assert col.iloc[:-h].notna().all()


# --- 2. target values are exactly right --------------------------------------
def test_target_values_correct():
    idx = pd.bdate_range("2021-01-01", periods=6)
    df = pd.DataFrame({"close": [100.0, 101.0, 99.0, 102.0, 101.0, 103.0]}, index=idx)
    t = MultiHorizonCausalHunter(horizons=[1]).generate_causal_targets(df)["target_tplus_1"]
    assert list(t.iloc[:-1]) == [1.0, 0.0, 1.0, 0.0, 1.0]   # up,down,up,down,up
    assert np.isnan(t.iloc[-1])


# --- 3. boundary purge removes overlapping labels ----------------------------
def test_boundary_purge_applied():
    df = _df(400)
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(size=(400, 4)), index=df.index,
                     columns=list("abcd"))
    hunter = MultiHorizonCausalHunter(horizons=[5], train_split=0.80)
    res = hunter.evaluate_feature_space(X, hunter.generate_causal_targets(df))
    r = res["target_tplus_5"]
    # 395 usable samples; split=316; purge=5 -> train 311, test 79
    assert r["purged"] == 5
    assert r["n_train"] == int(395 * 0.80) - 5
    assert r["n_train"] + 5 + r["n_test"] == 395


# --- 4. random features produce ~zero alpha (sanity of the yardstick) --------
def test_random_features_no_alpha():
    df = _df(600, seed=2)
    rng = np.random.default_rng(3)
    X = pd.DataFrame(rng.normal(size=(600, 8)), index=df.index,
                     columns=[f"f{i}" for i in range(8)])
    hunter = MultiHorizonCausalHunter(horizons=[1])
    res = hunter.evaluate_feature_space(X, hunter.generate_causal_targets(df))
    r = res["target_tplus_1"]
    assert r["test_accuracy"] <= r["majority_baseline"] + 0.06   # pure noise stays ~baseline
    assert len(r["rankings"]) == 8
