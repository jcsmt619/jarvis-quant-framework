"""
tests/test_hmm.py
=================
Behavioural tests for the HMM regime engine and its feature inputs:
  * feature engineering shape / causality
  * BIC-based model selection
  * valid stochastic matrices (transmat + filtered proba)
  * regime-stability confirmation filter
  * flicker detection
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.hmm_engine import HMMRegimeEngine
from data.feature_engineering import FEATURE_COLUMNS, build_features, build_standardized_features

ROOT = Path(__file__).resolve().parent.parent
SPY_CSV = ROOT / "data" / "raw" / "spy.csv"


@pytest.fixture(scope="module")
def spy_frame():
    if not SPY_CSV.exists():
        pytest.skip("SPY data not available")
    df = pd.read_csv(SPY_CSV, parse_dates=["date"]).set_index("date")
    df.columns = [c.lower() for c in df.columns]
    return df


@pytest.fixture(scope="module")
def engine_and_feats(spy_frame):
    feats = build_standardized_features(spy_frame)
    returns = np.log(spy_frame["close"] / spy_frame["close"].shift(1)).reindex(feats.index)
    engine = HMMRegimeEngine(n_candidates=[3, 4], n_init=2, min_train_bars=300)
    engine.train(feats, returns=returns)
    return engine, feats


# --- feature engineering ---------------------------------------------------
def test_build_features_produces_14_columns(spy_frame):
    raw = build_features(spy_frame)
    assert list(raw.columns) == FEATURE_COLUMNS
    assert len(FEATURE_COLUMNS) == 16


def test_standardized_features_have_no_nan(spy_frame):
    std = build_standardized_features(spy_frame)
    assert not std.isna().any().any()
    assert len(std) > 0


def test_features_are_causal(spy_frame):
    """Standardized feature at an early index must not change when future bars are added."""
    short = build_standardized_features(spy_frame.iloc[:1000])
    long = build_standardized_features(spy_frame.iloc[:1200])
    common = short.index.intersection(long.index)
    assert len(common) > 100
    np.testing.assert_allclose(
        short.loc[common].to_numpy(), long.loc[common].to_numpy(), rtol=1e-9, atol=1e-9
    )


# --- model selection -------------------------------------------------------
def test_bic_selects_a_candidate(engine_and_feats):
    engine, _ = engine_and_feats
    assert engine.n_regimes in (3, 4)
    assert set(engine.bic_scores.keys()) <= {3, 4}
    # Selected model has the lowest BIC among candidates.
    assert engine.bic == min(engine.bic_scores.values())


def test_regime_metadata_complete(engine_and_feats):
    engine, _ = engine_and_feats
    assert len(engine.regime_info) == engine.n_regimes
    for info in engine.regime_info.values():
        assert 0.0 <= info.max_position_size_pct <= 1.0
        assert info.max_leverage_allowed >= 0.0
        assert info.recommended_strategy_type in {"trend_following", "mean_reversion", "defensive_cash"}


# --- valid probability structures -----------------------------------------
def test_transition_matrix_rows_sum_to_one(engine_and_feats):
    engine, _ = engine_and_feats
    tm = engine.get_transition_matrix()
    assert tm.shape == (engine.n_regimes, engine.n_regimes)
    np.testing.assert_allclose(tm.sum(axis=1), np.ones(engine.n_regimes), atol=1e-8)


def test_filtered_proba_is_a_distribution(engine_and_feats):
    engine, feats = engine_and_feats
    proba = engine.predict_regime_proba(feats.to_numpy()[:200])
    assert proba.shape == (200, engine.n_regimes)
    np.testing.assert_allclose(proba.sum(axis=1), np.ones(200), atol=1e-8)
    assert (proba >= 0).all()


# --- stability + flicker ---------------------------------------------------
def test_stability_filter_requires_persistence():
    engine = HMMRegimeEngine(stability_bars=3)
    # Fake a 3-regime model context.
    engine.n_regimes = 3
    engine.regime_info = {}
    engine.reset_state()

    # First bar sets the active regime.
    engine._apply_stability(0)
    assert engine._active_regime == 0

    # A single deviating bar must NOT flip the confirmed regime.
    changed = engine._apply_stability(1)
    assert changed is False
    assert engine._active_regime == 0

    # Needs `stability_bars` consecutive to confirm the switch.
    engine._apply_stability(1)
    changed = engine._apply_stability(1)
    assert changed is True
    assert engine._active_regime == 1


def test_flicker_detection():
    engine = HMMRegimeEngine(flicker_window=20, flicker_threshold=4)
    # Alternating raw states => many changes => flickering.
    engine._raw_history = [i % 2 for i in range(20)]
    assert engine.get_regime_flicker_rate() > 4
    assert engine.is_flickering() is True

    # Stable raw history => no flicker.
    engine._raw_history = [2] * 20
    assert engine.get_regime_flicker_rate() == 0
    assert engine.is_flickering() is False
