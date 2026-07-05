"""
edge_hunting/config_loader.py
=============================
Load and validate experiment configs from YAML files.

Enforces the schema defined in docs/EXPERIMENT_CONFIG_SCHEMA.md:
  * asset_class must be ``stocks_etfs``
  * symbols must be non-empty and not crypto/forex
  * features must be a subset of FEATURE_COLUMNS
  * dates must be ordered
  * fees/slippage must be non-negative
  * train_window >= 126, fill_delay >= 1
  * gate thresholds within hard ceilings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from data.feature_engineering import FEATURE_COLUMNS

# Tickers that are NOT stocks/ETFs (rejected by the schema).
_CRYPTO_FOREX_DENYLIST = {
    "BTCUSD", "BTC-USD", "ETHUSD", "ETH-USD", "SOLUSD", "SOL-USD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",
    "XAUUSD", "XAGUSD",
}


class ConfigError(ValueError):
    """Raised when an experiment config fails validation."""


@dataclass
class ExperimentConfig:
    """Parsed and validated experiment configuration."""

    raw: dict[str, Any]
    strategy_name: str
    strategy_module: str
    strategy_class: str
    asset_class: str
    symbols: list[str]
    timeframe: str
    start_date: str
    end_date: str
    features_used: list[str]
    standardization_window: int
    entry_rules: dict
    exit_rules: dict
    position_sizing: dict
    fees: dict
    train_test_split: dict
    walk_forward: dict
    benchmark: dict
    robustness: dict
    validation_gate: dict
    config_path: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], config_path: str = "") -> "ExperimentConfig":
        _validate(raw)
        return cls(
            raw=raw,
            strategy_name=raw["strategy_name"],
            strategy_module=raw["strategy_module"],
            strategy_class=raw["strategy_class"],
            asset_class=raw["asset_class"],
            symbols=raw["symbols"],
            timeframe=raw["timeframe"],
            start_date=raw["start_date"],
            end_date=raw["end_date"],
            features_used=raw["features_used"],
            standardization_window=raw.get("standardization_window", 252),
            entry_rules=raw["entry_rules"],
            exit_rules=raw["exit_rules"],
            position_sizing=raw["position_sizing"],
            fees=raw["fees"],
            train_test_split=raw["train_test_split"],
            walk_forward=raw["walk_forward"],
            benchmark=raw["benchmark"],
            robustness=raw["robustness"],
            validation_gate=raw["validation_gate"],
            config_path=config_path,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.from_dict(raw, config_path=str(path))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
_REQUIRED_FIELDS = [
    "strategy_name", "strategy_module", "strategy_class", "asset_class",
    "symbols", "timeframe", "start_date", "end_date", "features_used",
    "entry_rules", "exit_rules", "position_sizing", "fees",
    "train_test_split", "walk_forward", "benchmark", "robustness",
    "validation_gate",
]


def _validate(raw: dict[str, Any]) -> None:
    """Raise ``ConfigError`` if the config violates the schema."""
    # 1. Required fields present
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ConfigError(f"missing required fields: {missing}")

    # 2. asset_class
    if raw["asset_class"] != "stocks_etfs":
        raise ConfigError(
            f"asset_class must be 'stocks_etfs', got '{raw['asset_class']}'"
        )

    # 3. symbols non-empty + not crypto/forex
    syms = raw["symbols"]
    if not isinstance(syms, list) or not syms:
        raise ConfigError("symbols must be a non-empty list")
    for s in syms:
        if not isinstance(s, str) or not s.strip():
            raise ConfigError(f"invalid symbol: {s!r}")
        if s.upper() in _CRYPTO_FOREX_DENYLIST:
            raise ConfigError(
                f"symbol '{s}' is crypto/forex; pipeline is stocks/ETFs only"
            )

    # 4. dates ordered
    if raw["start_date"] >= raw["end_date"]:
        raise ConfigError(
            f"start_date ({raw['start_date']}) must be before end_date ({raw['end_date']})"
        )

    # 5. features subset of FEATURE_COLUMNS
    feats = raw["features_used"]
    if not isinstance(feats, list) or not feats:
        raise ConfigError("features_used must be a non-empty list")
    invalid = [f for f in feats if f not in FEATURE_COLUMNS]
    if invalid:
        raise ConfigError(
            f"features_used contains unknown features: {invalid}; "
            f"valid: {FEATURE_COLUMNS}"
        )

    # 6. fees non-negative
    fees = raw["fees"]
    if fees.get("slippage_bps", 0) < 0:
        raise ConfigError("fees.slippage_bps must be >= 0")
    if fees.get("commission_per_trade", 0) < 0:
        raise ConfigError("fees.commission_per_trade must be >= 0")

    # 7. train_window >= 126, fill_delay >= 1
    tts = raw["train_test_split"]
    if tts.get("train_window", 0) < 126:
        raise ConfigError("train_test_split.train_window must be >= 126")
    if tts.get("fill_delay", 0) < 1:
        raise ConfigError("train_test_split.fill_delay must be >= 1 (no same-bar execution)")

    # 8. deflated_sharpe n_trials >= 1
    ds = raw.get("robustness", {}).get("deflated_sharpe", {})
    if ds.get("n_trials", 1) < 1:
        raise ConfigError("robustness.deflated_sharpe.n_trials must be >= 1")

    # 9. gate thresholds within hard ceilings
    gate = raw["validation_gate"]
    if gate.get("min_oos_sharpe", 0) <= 0:
        raise ConfigError("validation_gate.min_oos_sharpe must be > 0")
    if gate.get("max_max_drawdown", 0) > 0.50:
        raise ConfigError("validation_gate.max_max_drawdown must be <= 0.50")
    if gate.get("min_dsr", 0) < 0.50:
        raise ConfigError("validation_gate.min_dsr must be >= 0.50")
    if gate.get("min_cpcv_pct_positive", 0) < 0.50:
        raise ConfigError("validation_gate.min_cpcv_pct_positive must be >= 0.50")