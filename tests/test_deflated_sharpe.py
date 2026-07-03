"""
tests/test_deflated_sharpe.py
=============================
PSR/DSR math: known anchor values, deflation monotonicity in trial count,
fat-tail penalty direction, and the pure-luck detector.
"""

from __future__ import annotations

import numpy as np
import pytest

from backtest.deflated_sharpe import (
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe,
    sharpe_stats,
)


def test_psr_anchor_values():
    # SR exactly at the benchmark -> 50/50 regardless of moments.
    assert probabilistic_sharpe(0.10, 500, 0.0, 3.0, 0.10) == pytest.approx(0.5)
    # Positive SR vs zero benchmark -> > 50%, increasing with T.
    p_short = probabilistic_sharpe(0.10, 100, 0.0, 3.0, 0.0)
    p_long = probabilistic_sharpe(0.10, 1000, 0.0, 3.0, 0.0)
    assert 0.5 < p_short < p_long < 1.0


def test_fat_tails_penalize_psr():
    """Negative skew and excess kurtosis must reduce confidence in the same SR."""
    clean = probabilistic_sharpe(0.10, 500, 0.0, 3.0, 0.0)
    ugly = probabilistic_sharpe(0.10, 500, -1.0, 8.0, 0.0)
    assert ugly < clean


def test_expected_max_sharpe_grows_with_trials():
    v = 0.002
    e1 = expected_max_sharpe(1, v)
    e10 = expected_max_sharpe(10, v)
    e300 = expected_max_sharpe(300, v)
    assert e1 == 0.0
    assert 0.0 < e10 < e300               # more searching -> higher luck ceiling


def test_dsr_deflates_with_trial_count():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0008, 0.01, 750)     # genuine modest edge
    d1 = deflated_sharpe(r, n_trials=1)
    d100 = deflated_sharpe(r, n_trials=100)
    d1000 = deflated_sharpe(r, n_trials=1000)
    assert d1["dsr"] > d100["dsr"] > d1000["dsr"]


def test_pure_luck_is_caught():
    """Best-of-200 pure-noise strategies: raw Sharpe looks great, DSR must not."""
    rng = np.random.default_rng(1)
    trials = [rng.normal(0.0, 0.01, 500) for _ in range(200)]
    sharpes = [sharpe_stats(t)["sr"] for t in trials]
    best = trials[int(np.argmax(sharpes))]
    res = deflated_sharpe(best, n_trials=200, trial_sharpes=sharpes)
    assert res["sr_annual"] > 1.0          # the fluke looks impressive raw...
    assert res["psr"] > 0.90               # ...and even beats zero convincingly...
    assert res["dsr"] < 0.60               # ...but NOT the best-of-200 luck ceiling
    assert "search" in res["verdict"] or "WEAK" in res["verdict"]
