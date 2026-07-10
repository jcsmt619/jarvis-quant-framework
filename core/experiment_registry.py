from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


EXPERIMENT_REGISTRY_FILE_NAME = "experiment_registry.jsonl"

ALLOWED_EXPERIMENT_TYPES = (
    "backtest",
    "hmm_regime_validation",
    "paper_drill",
    "strategy_evaluation",
    "promotion_history",
)
ALLOWED_PROMOTION_STATUSES = (
    "not_reviewed",
    "candidate",
    "paper_only",
    "monitor_only",
    "human_review_required",
    "blocked_by_safety_gate",
    "rejected",
)
SAFE_EXPERIMENT_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_EXPERIMENT_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)

JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    timestamp_utc: str
    experiment_type: str
    strategy_id: str
    engine: str
    label: str
    summary: str
    dataset_id: str
    timeframe: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    promotion_status: str = "not_reviewed"
    promotion_from: str | None = None
    promotion_to: str | None = None
    reviewed_by: str | None = None
    notes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    research_only: bool = True
    paper_only: bool = True
    monitor_only: bool = True
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False
    real_paper_order_submitted: bool = False
    secrets_required: bool = False

    def validate(self) -> None:
        required_text = {
            "experiment_id": self.experiment_id,
            "timestamp_utc": self.timestamp_utc,
            "experiment_type": self.experiment_type,
            "strategy_id": self.strategy_id,
            "engine": self.engine,
            "label": self.label,
            "summary": self.summary,
            "dataset_id": self.dataset_id,
            "timeframe": self.timeframe,
            "promotion_status": self.promotion_status,
        }
        for field_name, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"experiment record is missing {field_name}")

        try:
            parsed_timestamp = datetime.fromisoformat(self.timestamp_utc)
        except ValueError as exc:
            raise ValueError("timestamp_utc must be ISO-8601") from exc
        if parsed_timestamp.tzinfo is None:
            raise ValueError("timestamp_utc must include timezone information")

        if self.experiment_type not in ALLOWED_EXPERIMENT_TYPES:
            raise ValueError(f"unknown experiment type: {self.experiment_type}")
        if self.promotion_status not in ALLOWED_PROMOTION_STATUSES:
            raise ValueError(f"unknown promotion status: {self.promotion_status}")
        if self.label not in SAFE_EXPERIMENT_LABELS:
            raise ValueError(f"unsafe experiment label: {self.label}")
        if self.label in DISALLOWED_EXPERIMENT_LABELS:
            raise ValueError(f"disallowed experiment label: {self.label}")

        for field_name, value in {
            "parameters": self.parameters,
            "metrics": self.metrics,
        }.items():
            _validate_json_mapping(field_name, value)

        for field_name, values in {
            "artifacts": self.artifacts,
            "notes": self.notes,
            "tags": self.tags,
        }.items():
            _validate_string_tuple(field_name, values)

        for field_name in ("promotion_from", "promotion_to", "reviewed_by"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be non-empty when provided")

        if self.experiment_type == "promotion_history" and not self.promotion_to:
            raise ValueError("promotion_history records require promotion_to")
        if self.experiment_type != "promotion_history" and self.promotion_status != "not_reviewed":
            if not self.reviewed_by:
                raise ValueError("reviewed promotion decisions require reviewed_by")

        if not self.research_only or not self.paper_only:
            raise ValueError("experiment records must remain research-only and paper-only")
        if not self.human_review_required:
            raise ValueError("experiment records must preserve human review")
        if self.live_trading_enabled:
            raise ValueError("experiment registry cannot enable live trading")
        if self.broker_order_routing_enabled or self.broker_order_call_performed:
            raise ValueError("experiment registry cannot enable or perform broker routing")
        if self.real_paper_order_submitted:
            raise ValueError("experiment registry cannot submit real paper orders")
        if self.secrets_required:
            raise ValueError("experiment registry cannot require secrets")


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).isoformat()


def experiment_registry_path(
    registry_dir: Path = Path("reports/experiment_registry"),
) -> Path:
    return registry_dir / EXPERIMENT_REGISTRY_FILE_NAME


def build_experiment_record(
    *,
    experiment_id: str,
    experiment_type: str,
    strategy_id: str,
    engine: str,
    summary: str,
    dataset_id: str,
    timeframe: str,
    label: str = RESEARCH_ONLY,
    parameters: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    artifacts: tuple[str, ...] = (),
    promotion_status: str = "not_reviewed",
    promotion_from: str | None = None,
    promotion_to: str | None = None,
    reviewed_by: str | None = None,
    notes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    now: datetime | None = None,
) -> ExperimentRecord:
    record = ExperimentRecord(
        experiment_id=experiment_id,
        timestamp_utc=_timestamp(now),
        experiment_type=experiment_type,
        strategy_id=strategy_id,
        engine=engine,
        label=label,
        summary=summary,
        dataset_id=dataset_id,
        timeframe=timeframe,
        parameters=parameters or {},
        metrics=metrics or {},
        artifacts=artifacts,
        promotion_status=promotion_status,
        promotion_from=promotion_from,
        promotion_to=promotion_to,
        reviewed_by=reviewed_by,
        notes=notes,
        tags=tags,
    )
    record.validate()
    return record


def append_experiment_record(
    record: ExperimentRecord,
    *,
    registry_dir: Path = Path("reports/experiment_registry"),
) -> Path:
    record.validate()
    registry_dir.mkdir(parents=True, exist_ok=True)
    ledger = experiment_registry_path(registry_dir)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_record_payload(record), sort_keys=True) + "\n")
    return ledger


def read_experiment_records(
    *,
    registry_dir: Path = Path("reports/experiment_registry"),
) -> list[dict[str, Any]]:
    ledger = experiment_registry_path(registry_dir)
    if not ledger.exists():
        return []

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"experiment registry line {line_number} is not valid JSON") from exc
        record = experiment_record_from_dict(payload)
        record.validate()
        records.append(_record_payload(record))
    return records


def validate_experiment_registry(
    *,
    registry_dir: Path = Path("reports/experiment_registry"),
) -> None:
    read_experiment_records(registry_dir=registry_dir)


def experiment_record_from_dict(payload: dict[str, Any]) -> ExperimentRecord:
    if not isinstance(payload, dict):
        raise ValueError("experiment registry payload must be an object")

    expected_keys = set(ExperimentRecord.__dataclass_fields__)
    payload_keys = set(payload)
    missing = expected_keys - payload_keys
    extra = payload_keys - expected_keys
    if missing:
        raise ValueError(f"experiment registry payload missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"experiment registry payload has unknown keys: {sorted(extra)}")

    normalized = dict(payload)
    for field_name in ("artifacts", "notes", "tags"):
        value = normalized[field_name]
        if isinstance(value, list):
            normalized[field_name] = tuple(value)

    record = ExperimentRecord(**normalized)
    record.validate()
    return record


def _record_payload(record: ExperimentRecord) -> dict[str, Any]:
    payload = asdict(record)
    for field_name in ("artifacts", "notes", "tags"):
        payload[field_name] = list(payload[field_name])
    return payload


def _validate_string_tuple(field_name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field_name} values must be non-empty strings")


def _validate_json_mapping(field_name: str, value: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        _validate_json_value(f"{field_name}.{key}", item)


def _validate_json_value(field_name: str, value: Any) -> None:
    if isinstance(value, JSON_SCALAR_TYPES):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(f"{field_name}[{index}]", item)
        return
    if isinstance(value, dict):
        _validate_json_mapping(field_name, value)
        return
    raise ValueError(f"{field_name} must be JSON-serializable")
