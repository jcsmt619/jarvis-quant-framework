from __future__ import annotations

import dataclasses
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.experiment_registry import (
    ExperimentRecord,
    append_experiment_record,
    build_experiment_record,
    read_experiment_records,
    validate_experiment_registry,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


def fixed_now() -> datetime:
    return datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def registry_dir() -> Path:
    path = Path("reports/experiment_registry_tests") / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def sample_record(**overrides) -> ExperimentRecord:
    values = {
        "experiment_id": "11D-BACKTEST-EEM-MEAN-REVERSION-001",
        "experiment_type": "backtest",
        "strategy_id": "EEM_MEAN_REVERSION",
        "engine": "wealth",
        "summary": "Research-only EEM mean reversion validation run.",
        "dataset_id": "eem_daily_fixture",
        "timeframe": "daily",
        "parameters": {"lookback": 20, "entry_z": -1.5},
        "metrics": {"total_return": 0.12, "max_drawdown": -0.04, "trades": 18},
        "artifacts": ("reports/backtests/eem_mean_reversion.json",),
        "notes": ("RESEARCH_ONLY", "LIVE TRADING: DISABLED"),
        "tags": ("11D", "backtest"),
        "now": fixed_now(),
    }
    values.update(overrides)
    return build_experiment_record(**values)


def test_11d_appends_and_reads_valid_backtest_record(registry_dir: Path) -> None:
    record = sample_record()

    ledger = append_experiment_record(record, registry_dir=registry_dir)
    records = read_experiment_records(registry_dir=registry_dir)

    assert ledger.exists()
    assert len(records) == 1
    assert records[0]["experiment_id"] == "11D-BACKTEST-EEM-MEAN-REVERSION-001"
    assert records[0]["experiment_type"] == "backtest"
    assert records[0]["label"] == RESEARCH_ONLY
    assert records[0]["research_only"] is True
    assert records[0]["paper_only"] is True
    assert records[0]["human_review_required"] is True
    assert records[0]["live_trading_enabled"] is False
    assert records[0]["broker_order_routing_enabled"] is False
    assert records[0]["broker_order_call_performed"] is False
    assert records[0]["real_paper_order_submitted"] is False
    assert records[0]["secrets_required"] is False


def test_11d_registry_is_append_only_jsonl(registry_dir: Path) -> None:
    first = sample_record(experiment_id="11D-BACKTEST-001")
    second = sample_record(
        experiment_id="11D-PAPER-DRILL-001",
        experiment_type="paper_drill",
        label=PAPER_ONLY,
        summary="Paper-only drill result with no broker routing.",
        tags=("11D", "paper_drill"),
    )

    append_experiment_record(first, registry_dir=registry_dir)
    append_experiment_record(second, registry_dir=registry_dir)

    lines = (registry_dir / "experiment_registry.jsonl").read_text(encoding="utf-8").splitlines()
    records = read_experiment_records(registry_dir=registry_dir)

    assert len(lines) == 2
    assert [record["experiment_id"] for record in records] == [
        "11D-BACKTEST-001",
        "11D-PAPER-DRILL-001",
    ]


def test_11d_records_strategy_evaluations_and_promotion_history(registry_dir: Path) -> None:
    evaluation = sample_record(
        experiment_id="11D-STRATEGY-EVAL-001",
        experiment_type="strategy_evaluation",
        label=MONITOR_ONLY,
        promotion_status="monitor_only",
        reviewed_by="human_reviewer",
        summary="Monitor-only strategy evaluation record.",
        metrics={"passed_gate": True, "paper_sessions": 30},
    )
    promotion = sample_record(
        experiment_id="11D-PROMOTION-HISTORY-001",
        experiment_type="promotion_history",
        label=HUMAN_REVIEW_REQUIRED,
        promotion_status="human_review_required",
        promotion_from="paper_only",
        promotion_to="monitor_only",
        reviewed_by="human_reviewer",
        summary="Promotion history entry requiring human review.",
        tags=("11D", "promotion_history"),
    )

    append_experiment_record(evaluation, registry_dir=registry_dir)
    append_experiment_record(promotion, registry_dir=registry_dir)
    records = read_experiment_records(registry_dir=registry_dir)

    assert records[0]["experiment_type"] == "strategy_evaluation"
    assert records[0]["promotion_status"] == "monitor_only"
    assert records[1]["experiment_type"] == "promotion_history"
    assert records[1]["promotion_from"] == "paper_only"
    assert records[1]["promotion_to"] == "monitor_only"
    assert records[1]["human_review_required"] is True


def test_11d_rejects_invalid_schema_and_existing_corruption(registry_dir: Path) -> None:
    missing_summary = dataclasses.replace(sample_record(), summary="")

    with pytest.raises(ValueError, match="summary"):
        append_experiment_record(missing_summary, registry_dir=registry_dir)

    ledger = registry_dir / "experiment_registry.jsonl"
    payload = dataclasses.asdict(sample_record())
    payload.pop("label")
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing keys"):
        validate_experiment_registry(registry_dir=registry_dir)


def test_11d_rejects_unsafe_labels_and_safety_flags() -> None:
    unsafe_label = dataclasses.replace(sample_record(), label="BUY" + "_NOW")
    live_record = dataclasses.replace(
        sample_record(),
        **{"live_trading_enabled": not sample_record().live_trading_enabled},
    )
    broker_record = dataclasses.replace(sample_record(), broker_order_routing_enabled=True)
    paper_order_record = dataclasses.replace(sample_record(), real_paper_order_submitted=True)
    secrets_record = dataclasses.replace(sample_record(), secrets_required=True)
    no_review_record = dataclasses.replace(sample_record(), human_review_required=False)

    with pytest.raises(ValueError, match="unsafe experiment label"):
        unsafe_label.validate()
    with pytest.raises(ValueError, match="live trading"):
        live_record.validate()
    with pytest.raises(ValueError, match="broker routing"):
        broker_record.validate()
    with pytest.raises(ValueError, match="real paper orders"):
        paper_order_record.validate()
    with pytest.raises(ValueError, match="secrets"):
        secrets_record.validate()
    with pytest.raises(ValueError, match="human review"):
        no_review_record.validate()
