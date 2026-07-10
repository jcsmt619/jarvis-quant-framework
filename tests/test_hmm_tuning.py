from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.hmm_engine import HMMRegimeEngine, RegimeState
from core.hmm_tuning import (
    BLOCKED_BY_SAFETY_GATE,
    DEFAULT_HMM_FEATURE_SET,
    HMMCircuitBreakerConfig,
    HMMTuningProfile,
    LIVE_TRADING_DISABLED,
    MONITOR_ONLY,
    VOLATILITY_FEATURES,
    default_hmm_profile_registry,
    evaluate_hmm_gate,
)


def _features(rows: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    data = rng.normal(0.0, 1.0, size=(rows, len(DEFAULT_HMM_FEATURE_SET)))
    frame = pd.DataFrame(data, columns=list(DEFAULT_HMM_FEATURE_SET))
    frame.index = pd.date_range("2025-01-01", periods=rows, freq="D")
    return frame


def test_profile_selects_per_asset_feature_set_without_volatility_features():
    profile = HMMTuningProfile(
        asset="SPY",
        state_counts=(2, 3),
        feature_set=("logret_1", "realized_vol_20", "roc_10", "atr_norm_14"),
        include_volatility_features=False,
    )

    selected = profile.select_features(_features())

    assert list(selected.columns) == ["logret_1", "roc_10"]
    assert not set(selected.columns).intersection(VOLATILITY_FEATURES)


def test_profile_rejects_live_trading_and_invalid_features():
    with pytest.raises(ValueError, match="live trading disabled"):
        HMMTuningProfile(asset="SPY", **{"live_trading_" + "enabled": True}).validate()

    with pytest.raises(ValueError, match="unknown HMM features"):
        HMMTuningProfile(asset="SPY", feature_set=("not_a_feature",)).validate()

    with pytest.raises(ValueError, match="live trading disabled"):
        HMMCircuitBreakerConfig(allow_live_trading=True).validate()


def test_default_registry_returns_per_asset_profile_and_default_fallback():
    registry = default_hmm_profile_registry()

    soxl = registry.get("SOXL")
    fallback = registry.get("QQQ")

    assert soxl.asset == "SOXL"
    assert soxl.persistence_bars == 4
    assert fallback.asset == "QQQ"
    assert fallback.live_trading_enabled is False
    assert fallback.to_dict()["live_trading_status"] == LIVE_TRADING_DISABLED


def test_gate_blocks_low_confidence_low_persistence_and_flicker():
    profile = HMMTuningProfile(
        asset="SPY",
        confidence_threshold=0.70,
        persistence_bars=3,
        circuit_breaker=HMMCircuitBreakerConfig(max_flicker_rate=1, min_confidence=0.70),
    )
    state = RegimeState(
        label="REGIME_0",
        state_id=0,
        probability=0.60,
        state_probabilities=np.array([0.60, 0.40]),
        is_confirmed=True,
        consecutive_bars=1,
    )

    decision = evaluate_hmm_gate(profile, state, flicker_rate=3, volatility_rank=0.20, trained_bars=300)

    assert decision.allowed is False
    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.target_multiplier == 0.0
    assert "below_profile_confidence_threshold" in decision.reasons
    assert "below_profile_persistence" in decision.reasons
    assert "flicker_circuit_breaker" in decision.reasons
    assert decision.live_trading_status == LIVE_TRADING_DISABLED


def test_gate_allows_monitor_only_when_profile_thresholds_pass():
    profile = HMMTuningProfile(asset="SPY", confidence_threshold=0.60, persistence_bars=2)
    state = RegimeState(
        label="REGIME_0",
        state_id=0,
        probability=0.80,
        state_probabilities=np.array([0.80, 0.20]),
        is_confirmed=True,
        consecutive_bars=3,
    )

    decision = evaluate_hmm_gate(profile, state, flicker_rate=0, volatility_rank=0.20, trained_bars=300)

    assert decision.allowed is True
    assert decision.label == MONITOR_ONLY
    assert decision.target_multiplier == 1.0
    assert decision.reasons == ()


def test_engine_uses_profile_state_counts_features_and_persists():
    profile = HMMTuningProfile(
        asset="SPY",
        state_counts=(2,),
        feature_set=("logret_1", "realized_vol_20", "roc_10"),
        include_volatility_features=False,
        confidence_threshold=0.50,
        persistence_bars=2,
        min_train_bars=40,
        n_init=1,
        random_state=11,
    )
    features = _features()
    returns = pd.Series(np.random.default_rng(9).normal(0.0, 0.01, len(features)), index=features.index)

    engine = HMMRegimeEngine(tuning_profile=profile, n_iter=20)
    engine.train(features, returns=returns)

    assert engine.n_candidates == [2]
    assert engine.n_regimes == 2
    assert engine.feature_columns == ["logret_1", "roc_10"]
    assert engine.min_confidence == 0.50
    assert engine.stability_bars == 2

    engine.reset_state()
    state = engine.update(features.iloc[0])
    decision = engine.evaluate_gate(state)
    assert decision.profile_asset == "SPY"
    assert decision.live_trading_status == LIVE_TRADING_DISABLED

    path = Path("br10d_hmm_profile_test.pkl")
    try:
        engine.save(path)
        loaded = HMMRegimeEngine.load(path)

        assert loaded.tuning_profile is not None
        assert loaded.tuning_profile.asset == "SPY"
        assert loaded.feature_columns == ["logret_1", "roc_10"]
        assert loaded.training_bars == len(features)
    finally:
        if path.exists():
            path.unlink()
