from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.experiment_registry import read_experiment_records
from core.hmm_tuning import HMMTuningProfile, LIVE_TRADING_DISABLED
from core.hmm_validation import (
    HMMValidationConfig,
    append_hmm_validation_to_registry,
    build_naive_baseline_allocations,
    validate_hmm_regime_experiment,
    write_hmm_validation_artifacts,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, PAPER_ONLY, RESEARCH_ONLY


@pytest.fixture
def output_dirs() -> tuple[Path, Path]:
    root = Path("reports/hmm_validation_tests") / uuid.uuid4().hex
    report_dir = root / "reports"
    registry_dir = root / "registry"
    try:
        yield report_dir, registry_dir
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _returns() -> pd.Series:
    index = pd.date_range("2026-01-01", periods=80, freq="D")
    values = np.array([0.01] * 40 + [-0.01] * 40)
    return pd.Series(values, index=index, name="returns")


def _features(shift: float = 0.0) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=80, freq="D")
    return pd.DataFrame(
        {
            "logret_1": np.linspace(-0.5, 0.5, 80) + shift,
            "realized_vol_20": np.linspace(0.1, 0.3, 80),
        },
        index=index,
    )


def _config(**overrides) -> HMMValidationConfig:
    values = {
        "experiment_id": "BR-10E-HMM-SPY-001",
        "strategy_id": "hmm_spy_daily",
        "asset": "SPY",
        "dataset_id": "spy_daily_fixture",
        "timeframe": "1Day",
        "train_start": "2025-01-01",
        "train_end": "2025-12-31",
        "validation_start": "2026-01-01",
        "validation_end": "2026-03-21",
        "min_baseline_excess_sharpe": 0.0,
    }
    values.update(overrides)
    return HMMValidationConfig(**values)


def test_br10e_validates_tuned_hmm_against_naive_baselines() -> None:
    returns = _returns()
    tuned_allocations = pd.Series([1.0] * 40 + [0.0] * 40, index=returns.index)
    baselines = build_naive_baseline_allocations(returns)

    result = validate_hmm_regime_experiment(
        config=_config(),
        profile=HMMTuningProfile(asset="SPY", state_counts=(2, 3), feature_set=("logret_1", "realized_vol_20")),
        train_features=_features(),
        validation_features=_features(),
        validation_returns=returns,
        tuned_allocations=tuned_allocations,
        baseline_allocations=baselines,
    )

    assert result.tuned_metrics["bars"] == 80
    assert result.baseline_metrics["buy_hold"]["bars"] == 80
    assert result.baseline_comparison["beat_best_baseline"] is True
    assert result.drift_checks["status"] == "passed"
    assert result.review_report["status"] == HUMAN_REVIEW_REQUIRED
    assert result.live_trading_enabled is False
    assert result.broker_order_call_performed is False
    assert result.real_paper_order_submitted is False


def test_br10e_flags_feature_drift_for_human_review() -> None:
    returns = _returns()
    tuned_allocations = pd.Series(1.0, index=returns.index)

    result = validate_hmm_regime_experiment(
        config=_config(drift_z_threshold=1.0),
        profile=HMMTuningProfile(asset="SPY", state_counts=(2,), feature_set=("logret_1", "realized_vol_20")),
        train_features=_features(),
        validation_features=_features(shift=5.0),
        validation_returns=returns,
        tuned_allocations=tuned_allocations,
    )

    assert result.drift_checks["status"] == "drift_flagged"
    assert "logret_1" in result.drift_checks["flagged_features"]
    assert result.review_report["status"] == HUMAN_REVIEW_REQUIRED


def test_br10e_writes_paper_only_artifacts_and_registry_record(output_dirs: tuple[Path, Path]) -> None:
    report_dir, registry_dir = output_dirs
    returns = _returns()
    tuned_allocations = pd.Series([1.0] * 40 + [0.0] * 40, index=returns.index)
    result = validate_hmm_regime_experiment(
        config=_config(),
        profile=HMMTuningProfile(asset="SPY", state_counts=(2,), feature_set=("logret_1", "realized_vol_20")),
        train_features=_features(),
        validation_features=_features(),
        validation_returns=returns,
        tuned_allocations=tuned_allocations,
    )

    json_path, md_path = write_hmm_validation_artifacts(result, report_dir=report_dir)
    ledger = append_hmm_validation_to_registry(
        result,
        registry_dir=registry_dir,
        artifacts=(str(json_path), str(md_path)),
        now=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
    )
    records = read_experiment_records(registry_dir=registry_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert ledger.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["live_trading_status"] == LIVE_TRADING_DISABLED
    assert "Human review is required" in md_path.read_text(encoding="utf-8")
    assert records[0]["experiment_type"] == "hmm_regime_validation"
    assert records[0]["label"] == HUMAN_REVIEW_REQUIRED
    assert records[0]["research_only"] is True
    assert records[0]["paper_only"] is True
    assert records[0]["live_trading_enabled"] is False
    assert records[0]["broker_order_call_performed"] is False
    assert records[0]["real_paper_order_submitted"] is False
    assert RESEARCH_ONLY in records[0]["notes"]
    assert PAPER_ONLY in records[0]["notes"]


def test_br10e_rejects_live_trading_and_bad_allocations() -> None:
    with pytest.raises(ValueError, match="live trading"):
        _config(**{"live_trading_" + "enabled": True}).validate()

    returns = _returns()
    bad_allocations = pd.Series(2.0, index=returns.index)
    with pytest.raises(ValueError, match="between 0 and 1"):
        validate_hmm_regime_experiment(
            config=_config(),
            profile=HMMTuningProfile(asset="SPY", state_counts=(2,), feature_set=("logret_1", "realized_vol_20")),
            train_features=_features(),
            validation_returns=returns,
            tuned_allocations=bad_allocations,
        )
