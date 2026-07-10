"""
core/hmm_tuning.py
==================
Research-only HMM tuning profiles and safety gates for BR-10D.

This module only configures and gates HMM regime research. It does not route
orders, enable live trading, or emit trade instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

RESEARCH_ONLY = "RESEARCH_ONLY"
PAPER_ONLY = "PAPER_ONLY"
MONITOR_ONLY = "MONITOR_ONLY"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
BLOCKED_BY_SAFETY_GATE = "BLOCKED_BY_SAFETY_GATE"
LIVE_TRADING_DISABLED = "LIVE TRADING: DISABLED"

DEFAULT_HMM_FEATURE_SET: tuple[str, ...] = (
    "logret_1",
    "logret_5",
    "logret_20",
    "realized_vol_20",
    "vol_ratio_5_20",
    "downside_dev_20",
    "vol_asymmetry_20",
    "volume_z_50",
    "volume_trend_10",
    "adx_14",
    "sma_slope_50",
    "rsi_z_14",
    "dist_from_sma_200",
    "roc_10",
    "roc_20",
    "atr_norm_14",
)

VOLATILITY_FEATURES: frozenset[str] = frozenset(
    {
        "realized_vol_20",
        "vol_ratio_5_20",
        "downside_dev_20",
        "vol_asymmetry_20",
        "atr_norm_14",
    }
)


@dataclass(frozen=True)
class HMMCircuitBreakerConfig:
    max_flicker_rate: int = 4
    min_confidence: float = 0.55
    min_persistence_bars: int = 3
    min_training_bars: int = 252
    halt_on_high_volatility_rank: float = 0.90
    allow_live_trading: bool = False

    def validate(self) -> "HMMCircuitBreakerConfig":
        if self.max_flicker_rate < 0:
            raise ValueError("max_flicker_rate must be >= 0")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if self.min_persistence_bars < 1:
            raise ValueError("min_persistence_bars must be >= 1")
        if self.min_training_bars < 1:
            raise ValueError("min_training_bars must be >= 1")
        if not 0.0 <= self.halt_on_high_volatility_rank <= 1.0:
            raise ValueError("halt_on_high_volatility_rank must be between 0 and 1")
        if self.allow_live_trading:
            raise ValueError("BR-10D HMM profiles must keep live trading disabled")
        return self


@dataclass(frozen=True)
class HMMTuningProfile:
    asset: str
    state_counts: tuple[int, ...] = (3, 4, 5)
    feature_set: tuple[str, ...] = DEFAULT_HMM_FEATURE_SET
    include_volatility_features: bool = True
    confidence_threshold: float = 0.55
    persistence_bars: int = 3
    min_train_bars: int = 252
    n_init: int = 4
    random_state: int = 42
    circuit_breaker: HMMCircuitBreakerConfig = field(default_factory=HMMCircuitBreakerConfig)
    labels: tuple[str, ...] = (RESEARCH_ONLY, PAPER_ONLY, MONITOR_ONLY, HUMAN_REVIEW_REQUIRED)
    live_trading_enabled: bool = False

    def validate(self) -> "HMMTuningProfile":
        if not self.asset or not self.asset.strip():
            raise ValueError("asset is required")
        if not self.state_counts:
            raise ValueError("state_counts must not be empty")
        if any(k < 2 for k in self.state_counts):
            raise ValueError("state_counts must be >= 2")
        if len(set(self.state_counts)) != len(self.state_counts):
            raise ValueError("state_counts must not contain duplicates")
        if not self.feature_set:
            raise ValueError("feature_set must not be empty")
        unknown = set(self.feature_set) - set(DEFAULT_HMM_FEATURE_SET)
        if unknown:
            raise ValueError(f"unknown HMM features: {sorted(unknown)}")
        if not self.include_volatility_features and set(self.feature_set).issubset(VOLATILITY_FEATURES):
            raise ValueError("feature_set cannot become empty after disabling volatility features")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if self.persistence_bars < 1:
            raise ValueError("persistence_bars must be >= 1")
        if self.min_train_bars < 1:
            raise ValueError("min_train_bars must be >= 1")
        if self.n_init < 1:
            raise ValueError("n_init must be >= 1")
        if self.live_trading_enabled:
            raise ValueError("BR-10D HMM profiles must keep live trading disabled")
        if RESEARCH_ONLY not in self.labels or PAPER_ONLY not in self.labels:
            raise ValueError("profiles must include RESEARCH_ONLY and PAPER_ONLY labels")
        self.circuit_breaker.validate()
        return self

    @property
    def active_features(self) -> tuple[str, ...]:
        if self.include_volatility_features:
            return self.feature_set
        return tuple(name for name in self.feature_set if name not in VOLATILITY_FEATURES)

    def select_features(self, features: pd.DataFrame) -> pd.DataFrame:
        self.validate()
        missing = [name for name in self.active_features if name not in features.columns]
        if missing:
            raise ValueError(f"missing HMM profile features for {self.asset}: {missing}")
        return features.loc[:, list(self.active_features)].copy()

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "state_counts": list(self.state_counts),
            "feature_set": list(self.feature_set),
            "active_features": list(self.active_features),
            "include_volatility_features": self.include_volatility_features,
            "confidence_threshold": self.confidence_threshold,
            "persistence_bars": self.persistence_bars,
            "min_train_bars": self.min_train_bars,
            "n_init": self.n_init,
            "random_state": self.random_state,
            "circuit_breaker": {
                "max_flicker_rate": self.circuit_breaker.max_flicker_rate,
                "min_confidence": self.circuit_breaker.min_confidence,
                "min_persistence_bars": self.circuit_breaker.min_persistence_bars,
                "min_training_bars": self.circuit_breaker.min_training_bars,
                "halt_on_high_volatility_rank": self.circuit_breaker.halt_on_high_volatility_rank,
                "allow_live_trading": self.circuit_breaker.allow_live_trading,
            },
            "labels": list(self.labels),
            "live_trading_enabled": self.live_trading_enabled,
            "live_trading_status": LIVE_TRADING_DISABLED,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HMMTuningProfile":
        breaker_payload = payload.get("circuit_breaker", {})
        profile = cls(
            asset=str(payload["asset"]),
            state_counts=tuple(int(k) for k in payload.get("state_counts", (3, 4, 5))),
            feature_set=tuple(payload.get("feature_set", DEFAULT_HMM_FEATURE_SET)),
            include_volatility_features=bool(payload.get("include_volatility_features", True)),
            confidence_threshold=float(payload.get("confidence_threshold", 0.55)),
            persistence_bars=int(payload.get("persistence_bars", 3)),
            min_train_bars=int(payload.get("min_train_bars", 252)),
            n_init=int(payload.get("n_init", 4)),
            random_state=int(payload.get("random_state", 42)),
            circuit_breaker=HMMCircuitBreakerConfig(
                max_flicker_rate=int(breaker_payload.get("max_flicker_rate", 4)),
                min_confidence=float(breaker_payload.get("min_confidence", 0.55)),
                min_persistence_bars=int(breaker_payload.get("min_persistence_bars", 3)),
                min_training_bars=int(breaker_payload.get("min_training_bars", 252)),
                halt_on_high_volatility_rank=float(
                    breaker_payload.get("halt_on_high_volatility_rank", 0.90)
                ),
                allow_live_trading=bool(breaker_payload.get("allow_live_trading", False)),
            ),
            labels=tuple(payload.get("labels", (RESEARCH_ONLY, PAPER_ONLY, MONITOR_ONLY, HUMAN_REVIEW_REQUIRED))),
            live_trading_enabled=bool(payload.get("live_trading_enabled", False)),
        )
        return profile.validate()


@dataclass(frozen=True)
class HMMGateDecision:
    allowed: bool
    label: str
    reasons: tuple[str, ...]
    target_multiplier: float
    profile_asset: str
    state_id: int | None
    confidence: float
    persistence_bars: int
    flicker_rate: int
    live_trading_status: str = LIVE_TRADING_DISABLED

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "label": self.label,
            "reasons": list(self.reasons),
            "target_multiplier": self.target_multiplier,
            "profile_asset": self.profile_asset,
            "state_id": self.state_id,
            "confidence": self.confidence,
            "persistence_bars": self.persistence_bars,
            "flicker_rate": self.flicker_rate,
            "live_trading_status": self.live_trading_status,
        }


class HMMProfileRegistry:
    def __init__(self, profiles: list[HMMTuningProfile] | tuple[HMMTuningProfile, ...]):
        self._profiles = {profile.asset.upper(): profile.validate() for profile in profiles}

    def get(self, asset: str) -> HMMTuningProfile:
        key = asset.upper()
        if key in self._profiles:
            return self._profiles[key]
        if "DEFAULT" in self._profiles:
            base = self._profiles["DEFAULT"]
            return HMMTuningProfile.from_dict({**base.to_dict(), "asset": asset.upper()})
        raise KeyError(f"no HMM tuning profile for asset {asset}")

    def to_dict(self) -> dict[str, Any]:
        return {asset: profile.to_dict() for asset, profile in sorted(self._profiles.items())}


def default_hmm_profile_registry() -> HMMProfileRegistry:
    return HMMProfileRegistry(
        [
            HMMTuningProfile(asset="DEFAULT"),
            HMMTuningProfile(
                asset="SPY",
                state_counts=(3, 4, 5),
                confidence_threshold=0.58,
                persistence_bars=3,
            ),
            HMMTuningProfile(
                asset="SOXL",
                state_counts=(3, 4, 5, 6),
                confidence_threshold=0.62,
                persistence_bars=4,
                circuit_breaker=HMMCircuitBreakerConfig(
                    max_flicker_rate=3,
                    min_confidence=0.62,
                    min_persistence_bars=4,
                    halt_on_high_volatility_rank=0.75,
                ),
            ),
        ]
    )


def evaluate_hmm_gate(
    profile: HMMTuningProfile,
    state: Any,
    *,
    flicker_rate: int,
    volatility_rank: float | None = None,
    trained_bars: int | None = None,
    timestamp: datetime | None = None,
) -> HMMGateDecision:
    del timestamp
    profile.validate()
    reasons: list[str] = []
    confidence = float(getattr(state, "probability", 0.0))
    persistence = int(getattr(state, "consecutive_bars", 0))
    state_id = getattr(state, "state_id", None)

    if trained_bars is not None and trained_bars < profile.circuit_breaker.min_training_bars:
        reasons.append("insufficient_training_bars")
    if confidence < profile.confidence_threshold:
        reasons.append("below_profile_confidence_threshold")
    if confidence < profile.circuit_breaker.min_confidence:
        reasons.append("below_circuit_breaker_confidence")
    if persistence < profile.persistence_bars:
        reasons.append("below_profile_persistence")
    if persistence < profile.circuit_breaker.min_persistence_bars:
        reasons.append("below_circuit_breaker_persistence")
    if flicker_rate > profile.circuit_breaker.max_flicker_rate:
        reasons.append("flicker_circuit_breaker")
    if volatility_rank is not None and np.isfinite(volatility_rank):
        if float(volatility_rank) >= profile.circuit_breaker.halt_on_high_volatility_rank:
            reasons.append("high_volatility_rank_circuit_breaker")

    allowed = not reasons
    return HMMGateDecision(
        allowed=allowed,
        label=MONITOR_ONLY if allowed else BLOCKED_BY_SAFETY_GATE,
        reasons=tuple(reasons),
        target_multiplier=1.0 if allowed else 0.0,
        profile_asset=profile.asset,
        state_id=int(state_id) if state_id is not None else None,
        confidence=confidence,
        persistence_bars=persistence,
        flicker_rate=int(flicker_rate),
    )
