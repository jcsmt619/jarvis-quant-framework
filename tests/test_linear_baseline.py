"""
tests/test_linear_baseline.py
=============================
Temporal hygiene of the audit tool itself: the C-search must be
TimeSeriesSplit (not stratified shuffling), the boundary purge must hold,
skill must be measured against the majority base rate, a genuine linear
signal must be found, and pure noise must score ~zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

from analysis.linear_baseline import LinearBaseline


def _frame(n: int, seed: int) -> tuple[pd.DataFrame, np.random.Generator]:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    X = pd.DataFrame({"signal": rng.normal(0, 1, n),
                      "noise_a": rng.normal(0, 1, n),
                      "noise_b": rng.normal(0, 1, n)}, index=idx)
    return X, rng


def test_hyperparameter_cv_is_temporal():
    """The draft's central false claim: cv must be TimeSeriesSplit."""
    pipe = LinearBaseline().pipeline()
    assert isinstance(pipe.named_steps["clf"].cv, TimeSeriesSplit)


def test_boundary_purge_and_embargo():
    """Train samples whose label interval reaches the test window (or sit
    inside the embargo) are excluded from fitting."""
    X, rng = _frame(500, 0)
    y = pd.Series(rng.integers(0, 2, 500), index=X.index)
    h = 10
    t1 = pd.Series(X.index[np.minimum(np.arange(500) + h, 499)], index=X.index)
    lb = LinearBaseline(embargo_bars=5)
    res = lb.audit(X, y, t1=t1)
    # cutoff = 400; labels spanning h bars + 5 embargo bars must be purged.
    assert res["n_purged"] >= h                  # at least the overlapping tail
    assert res["n_train"] == 400 - res["n_purged"]


def test_finds_genuine_linear_signal():
    X, rng = _frame(800, 1)
    y = pd.Series((X["signal"] + rng.normal(0, 0.5, 800) > 0).astype(int),
                  index=X.index)
    res = LinearBaseline().audit(X, y)
    assert res["auc"] > 0.80                     # strong, learnable signal
    assert res["skill"] > 0.10
    assert res["drivers"].iloc[0]["feature"] == "signal"   # right driver on top


def test_pure_noise_scores_zero_skill():
    X, rng = _frame(800, 2)
    y = pd.Series(rng.integers(0, 2, 800), index=X.index)
    res = LinearBaseline().audit(X, y)
    assert abs(res["skill"]) < 0.08              # no manufactured edge
    assert 0.40 < res["auc"] < 0.60


def test_missing_class_in_test_window_does_not_crash():
    """Multiclass AUC degrades to NaN, never raises, when the test window
    lacks a class."""
    X, rng = _frame(500, 3)
    y = pd.Series(rng.choice([-1, 0, 1], 500), index=X.index)
    y.iloc[400:] = rng.choice([-1, 1], 100)      # class 0 absent from test
    res = LinearBaseline().audit(X, y)
    assert np.isnan(res["auc"]) or 0.0 <= res["auc"] <= 1.0
    assert res["majority_baseline"] > 0          # rest of the audit intact
