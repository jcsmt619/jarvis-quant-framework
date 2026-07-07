from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.human_review_queue import (
    DEFAULT_HUMAN_REVIEW_QUEUE_DIR,
    HUMAN_REVIEW_QUEUE_JSON,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR = Path("reports/operator_acknowledgment_ledger")
OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON = "operator_acknowledgment_ledger.json"
OPERATOR_ACKNOWLEDGMENT_LEDGER_MARKDOWN = "operator_acknowledgment_ledger.md"

LEDGER_OPEN = "OPEN_OPERATOR_ACKNOWLEDGMENT_LEDGER"
LEDGER_NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"
LEDGER_BLOCKED_BY_SAFETY_GATE = "BLOCKED_BY_SAFETY_GATE"

ACKNOWLEDGED = "ACKNOWLEDGED"
REJECTED = "REJECTED"
DEFERRED = "DEFERRED"
NOTED = "NOTED"
PENDING_OPERATOR_REVIEW = "PENDING_OPERATOR_REVIEW"

SAFE_ACKNOWLEDGMENT_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
ALLOWED_REVIEW_STATUSES = (
    ACKNOWLEDGED,
    REJECTED,
    DEFERRED,
    NOTED,
    PENDING_OPERATOR_REVIEW,
)
DISALLOWED_ACKNOWLEDGMENT_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)
UNSAFE_TRUE_FIELDS = (
    "acknowledgment_enables_live_trading",
    "automatic_action_enabled",
    "broker_call_used",
    "broker_order_call_performed",
    "broker_order_call_requested",
    "broker_order_routing_enabled",
    "broker_order_routing_requested",
    "broker_routing_used",
    "credential_file_used",
    "live_trading_approval_granted",
    "live_trading_enabled",
    "order_execution_enabled",
    "order_execution_used",
    "prohibited_trade_labels_present",
    "real_paper_order_submitted",
    "real_paper_wrapper_attempted",
    "real_paper_wrapper_connected",
    "secrets_required",
)
SECRET_FILE_NAMES = {".env"}
SECRET_PATH_MARKERS = (
    "credential",
    "credentials",
    "oauth",
    "password",
    "private_key",
    "secret",
    "secrets",
    "token",
)
REVIEW_ITEM_SECTIONS = (
    "required_human_review_items",
    "missing_artifacts",
    "stale_artifacts",
    "skipped_steps",
    "blocked_workflows",
    "safety_findings",
    "retention_review_items",
    "next_operator_actions",
)


@dataclass(frozen=True)
class OperatorAcknowledgmentLedgerInput:
    ledger_id: str
    ledger_date: str
    generated_at_utc: str
    human_review_queue_path: Path = DEFAULT_HUMAN_REVIEW_QUEUE_DIR / HUMAN_REVIEW_QUEUE_JSON
    operator_acknowledgments_path: Path | None = None

    def validate(self) -> None:
        for field_name in ("ledger_id", "ledger_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"operator acknowledgment ledger requires {field_name}")
        _parse_iso_date("ledger_date", self.ledger_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        _validate_ledger_path(self.human_review_queue_path)
        if self.operator_acknowledgments_path is not None:
            _validate_ledger_path(self.operator_acknowledgments_path)


def build_default_operator_acknowledgment_ledger_input(
    *,
    ledger_date: date | None = None,
    now: datetime | None = None,
    operator_acknowledgments_path: Path | None = None,
) -> OperatorAcknowledgmentLedgerInput:
    generated = now or datetime.now(tz=UTC)
    day = ledger_date or generated.date()
    return OperatorAcknowledgmentLedgerInput(
        ledger_id=f"21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-{day.isoformat()}",
        ledger_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        operator_acknowledgments_path=operator_acknowledgments_path,
    )


def build_operator_acknowledgment_ledger_payload(
    ledger_input: OperatorAcknowledgmentLedgerInput,
) -> dict[str, Any]:
    ledger_input.validate()
    queue_payload = _read_json_object(ledger_input.human_review_queue_path)
    source_queue = _source_queue_status(ledger_input.human_review_queue_path, queue_payload)
    queue_items = _queue_review_items(queue_payload or {})
    acknowledgment_records = _acknowledgment_records(ledger_input.operator_acknowledgments_path)
    acknowledgments_by_id = {item["review_item_id"]: item for item in acknowledgment_records}
    ledger_entries = [
        _ledger_entry(item, acknowledgments_by_id.get(item["review_item_id"]))
        for item in queue_items
    ]
    unmatched_acknowledgments = [
        item for item in acknowledgment_records if item["review_item_id"] not in {entry["review_item_id"] for entry in ledger_entries}
    ]
    blocked_workflow_references = _blocked_workflow_references(queue_items, ledger_entries)
    ledger_state = _ledger_state(source_queue, ledger_entries, unmatched_acknowledgments)

    payload = {
        "phase": "21B",
        "workflow": "Operator Acknowledgment Ledger",
        "ledger_id": ledger_input.ledger_id,
        "ledger_date": ledger_input.ledger_date,
        "generated_at_utc": ledger_input.generated_at_utc,
        "ledger_state": ledger_state,
        "source_queue": source_queue,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_ACKNOWLEDGMENT_LABELS),
        "allowed_review_statuses": list(ALLOWED_REVIEW_STATUSES),
        "summary": {
            "source_review_item_count": len(queue_items),
            "ledger_entry_count": len(ledger_entries),
            "acknowledged_count": _count_status(ledger_entries, ACKNOWLEDGED),
            "rejected_count": _count_status(ledger_entries, REJECTED),
            "deferred_count": _count_status(ledger_entries, DEFERRED),
            "noted_count": _count_status(ledger_entries, NOTED),
            "pending_operator_review_count": _count_status(ledger_entries, PENDING_OPERATOR_REVIEW),
            "blocked_workflow_reference_count": len(blocked_workflow_references),
            "unmatched_acknowledgment_count": len(unmatched_acknowledgments),
            "label_counts": _count_by([*ledger_entries, *unmatched_acknowledgments, source_queue], "label"),
        },
        "ledger_entries": ledger_entries,
        "blocked_workflow_references": blocked_workflow_references,
        "unmatched_acknowledgments": unmatched_acknowledgments,
    }
    _validate_json_value("operator_acknowledgment_ledger_payload", payload)
    return _normalize_json_value(payload)


def write_operator_acknowledgment_ledger(
    ledger_input: OperatorAcknowledgmentLedgerInput,
    *,
    out_dir: Path = DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR,
) -> tuple[Path, Path]:
    payload = build_operator_acknowledgment_ledger_payload(ledger_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON
    markdown_path = out_dir / OPERATOR_ACKNOWLEDGMENT_LEDGER_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_operator_acknowledgment_ledger_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_operator_acknowledgment_ledger_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("operator_acknowledgment_ledger_payload", payload)
    lines = [
        "# 21B Operator Acknowledgment Ledger",
        "",
        f"Ledger ID: {payload['ledger_id']}",
        f"Ledger Date: {payload['ledger_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Ledger State: {payload['ledger_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "Operator acknowledgments, rejections, deferrals, and notes are records only.",
        "Acknowledgments do not enable live trading, broker routing, broker calls, order execution, or automatic actions.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Source review items", payload["summary"]["source_review_item_count"]),
        _summary_line("Ledger entries", payload["summary"]["ledger_entry_count"]),
        _summary_line("Acknowledged", payload["summary"]["acknowledged_count"]),
        _summary_line("Rejected", payload["summary"]["rejected_count"]),
        _summary_line("Deferred", payload["summary"]["deferred_count"]),
        _summary_line("Noted", payload["summary"]["noted_count"]),
        _summary_line("Pending operator review", payload["summary"]["pending_operator_review_count"]),
        _summary_line("Blocked workflow references", payload["summary"]["blocked_workflow_reference_count"]),
        _summary_line("Unmatched acknowledgments", payload["summary"]["unmatched_acknowledgment_count"]),
        "",
    ]
    lines.extend(_section("Ledger Entries", payload["ledger_entries"]))
    lines.extend(_section("Blocked Workflow References", payload["blocked_workflow_references"]))
    lines.extend(_section("Unmatched Acknowledgments", payload["unmatched_acknowledgments"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY operator acknowledgment ledger generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED entries remain review records.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_queue_status(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "queue_id": None,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "21A Human Review Queue JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "generated_at_utc": None,
            "queue_state": None,
        }
    _validate_json_value("human_review_queue", payload)
    return {
        "queue_id": payload.get("queue_id"),
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": "present",
        "summary": "21A Human Review Queue supplied to 21B.",
        "path": path.as_posix(),
        "generated_at_utc": payload.get("generated_at_utc"),
        "queue_state": payload.get("queue_state"),
    }


def _queue_review_items(queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    queue_id = queue_payload.get("queue_id")
    queue_generated_at_utc = queue_payload.get("generated_at_utc")
    for section in REVIEW_ITEM_SECTIONS:
        values = queue_payload.get(section, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            value = dict(item)
            review_item_id = _review_item_id(value)
            entry = {
                "review_item_id": review_item_id,
                "source_section": section,
                "source_queue_id": queue_id,
                "source_queue_generated_at_utc": queue_generated_at_utc,
                "source_timestamp": value.get("generated_at_utc") or queue_generated_at_utc,
                "label": value.get("label", HUMAN_REVIEW_REQUIRED),
                "source_status": value.get("status", "recorded"),
                "summary": value.get("summary", "21A review item recorded."),
                "workflow_id": value.get("workflow_id"),
                "artifact_id": value.get("artifact_id"),
                "blocked_workflow_reference": _blocked_workflow_reference(section, value),
            }
            _validate_json_value("queue_review_item", entry)
            items.append(_normalize_json_value(entry))
    return _dedupe_by_id(items, "review_item_id")


def _acknowledgment_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    value = _read_json_value(path)
    if value is None:
        return []
    records = value.get("acknowledgments", []) if isinstance(value, dict) else value
    if not isinstance(records, list):
        raise ValueError("operator acknowledgments must be a list or an object with acknowledgments")
    output = []
    for record in records:
        if not isinstance(record, dict):
            continue
        _validate_json_value("operator_acknowledgment", record)
        review_item_id = record.get("review_item_id")
        if not isinstance(review_item_id, str) or not review_item_id.strip():
            raise ValueError("operator acknowledgment requires review_item_id")
        status = record.get("review_status", PENDING_OPERATOR_REVIEW)
        if status not in ALLOWED_REVIEW_STATUSES or status == PENDING_OPERATOR_REVIEW:
            raise ValueError(f"invalid operator acknowledgment review_status: {status}")
        acknowledged_at_utc = record.get("acknowledged_at_utc") or record.get("timestamp_utc")
        if not isinstance(acknowledged_at_utc, str) or not acknowledged_at_utc.strip():
            raise ValueError("operator acknowledgment requires acknowledged_at_utc")
        _parse_iso_datetime("acknowledged_at_utc", acknowledged_at_utc)
        item = {
            "review_item_id": review_item_id,
            "review_status": status,
            "acknowledged_at_utc": acknowledged_at_utc,
            "operator_note": record.get("operator_note", ""),
            "operator_id": record.get("operator_id", "operator"),
            "label": record.get("label", HUMAN_REVIEW_REQUIRED),
            "blocked_workflow_references": record.get("blocked_workflow_references", []),
            "automatic_action_enabled": False,
            "acknowledgment_enables_live_trading": False,
        }
        _validate_json_value("operator_acknowledgment_record", item)
        output.append(_normalize_json_value(item))
    return _dedupe_by_id(output, "review_item_id")


def _ledger_entry(queue_item: dict[str, Any], acknowledgment: dict[str, Any] | None) -> dict[str, Any]:
    review_item_id = queue_item["review_item_id"]
    status = acknowledgment["review_status"] if acknowledgment else PENDING_OPERATOR_REVIEW
    value = {
        "ledger_entry_id": f"21B-{review_item_id}",
        "review_item_id": review_item_id,
        "review_status": status,
        "label": queue_item.get("label", HUMAN_REVIEW_REQUIRED),
        "safety_labels": [queue_item.get("label", HUMAN_REVIEW_REQUIRED)],
        "source_section": queue_item["source_section"],
        "source_queue_id": queue_item.get("source_queue_id"),
        "source_queue_generated_at_utc": queue_item.get("source_queue_generated_at_utc"),
        "source_timestamp": queue_item.get("source_timestamp"),
        "source_status": queue_item.get("source_status"),
        "summary": queue_item.get("summary"),
        "workflow_id": queue_item.get("workflow_id"),
        "artifact_id": queue_item.get("artifact_id"),
        "blocked_workflow_reference": queue_item.get("blocked_workflow_reference"),
        "acknowledged_at_utc": acknowledgment.get("acknowledged_at_utc") if acknowledgment else None,
        "operator_id": acknowledgment.get("operator_id") if acknowledgment else None,
        "operator_note": acknowledgment.get("operator_note", "") if acknowledgment else "",
        "operator_note_present": bool(acknowledgment and acknowledgment.get("operator_note")),
        "automatic_action_enabled": False,
        "acknowledgment_enables_live_trading": False,
        "broker_order_call_performed": False,
        "broker_order_routing_enabled": False,
        "broker_routing_used": False,
        "broker_call_used": False,
        "order_execution_used": False,
        "live_trading_enabled": False,
        "live_trading_approval_granted": False,
    }
    _validate_json_value("operator_acknowledgment_ledger_entry", value)
    return _normalize_json_value(value)


def _blocked_workflow_references(
    queue_items: list[dict[str, Any]],
    ledger_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry_status_by_id = {entry["review_item_id"]: entry["review_status"] for entry in ledger_entries}
    refs = []
    for item in queue_items:
        reference = item.get("blocked_workflow_reference")
        if not reference:
            continue
        refs.append(
            {
                "review_item_id": item["review_item_id"],
                "workflow_id": reference,
                "label": BLOCKED_BY_SAFETY_GATE,
                "review_status": entry_status_by_id.get(item["review_item_id"], PENDING_OPERATOR_REVIEW),
                "status": "blocked",
                "summary": "Blocked workflow reference remains blocked after operator acknowledgment ledger generation.",
                "automatic_action_enabled": False,
            }
        )
    return _dedupe_by_id(refs, "review_item_id")


def _ledger_state(
    source_queue: dict[str, Any],
    ledger_entries: list[dict[str, Any]],
    unmatched_acknowledgments: list[dict[str, Any]],
) -> str:
    if source_queue["label"] == BLOCKED_BY_SAFETY_GATE or source_queue["status"] != "present":
        return LEDGER_BLOCKED_BY_SAFETY_GATE
    if unmatched_acknowledgments or any(item["review_status"] == PENDING_OPERATOR_REVIEW for item in ledger_entries):
        return LEDGER_NEEDS_OPERATOR_REVIEW
    return LEDGER_OPEN


def _review_item_id(item: dict[str, Any]) -> str:
    value = (
        item.get("review_item_id")
        or item.get("action_id")
        or item.get("workflow_id")
        or item.get("artifact_id")
        or item.get("step_id")
        or item.get("finding_id")
        or item.get("status")
        or "review_item"
    )
    return str(value)


def _blocked_workflow_reference(section: str, item: dict[str, Any]) -> str | None:
    if section == "blocked_workflows" or item.get("label") == BLOCKED_BY_SAFETY_GATE:
        return str(item.get("workflow_id") or item.get("review_item_id") or item.get("finding_id") or "blocked_workflow")
    return None


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "operator_acknowledgments_are_records_only": True,
        "acknowledgment_enables_live_trading": False,
        "automatic_action_enabled": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_routing_enabled": False,
        "broker_routing_used": False,
        "broker_call_used": False,
        "order_execution_used": False,
        "live_trading_enabled": False,
        "live_trading_approval_granted": False,
        "secrets_required": False,
        "credential_file_used": False,
        "prohibited_trade_labels_present": False,
        "status": "LIVE TRADING: DISABLED",
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_ledger_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = item.get("ledger_entry_id") or item.get("review_item_id") or item.get("workflow_id") or "item"
        label = item.get("label", "n/a")
        status = item.get("review_status") or item.get("status") or "recorded"
        summary = item.get("summary") or item.get("operator_note") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
    lines.append("")
    return lines


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _count_status(items: list[dict[str, Any]], status: str) -> int:
    return len([item for item in items if item.get("review_status") == status])


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _dedupe_by_id(items: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        value = dict(item)
        value.setdefault(id_key, "item")
        _validate_json_value(id_key, value)
        by_id[str(value[id_key])] = _normalize_json_value(value)
    return sorted(by_id.values(), key=lambda item: str(item.get(id_key, "item")))


def _validate_ledger_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("operator acknowledgment ledger cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("operator acknowledgment ledger cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("operator acknowledgment ledger paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("operator acknowledgment ledger paths cannot traverse parent directories")


def _parse_iso_datetime(field_name: str, value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")


def _parse_iso_date(field_name: str, value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _validate_json_value(field_name: str, value: Any) -> None:
    if isinstance(value, dict):
        label = value.get("label")
        if label is not None and label not in SAFE_ACKNOWLEDGMENT_LABELS:
            raise ValueError(f"unsafe operator acknowledgment ledger label: {label}")
        review_status = value.get("review_status")
        if review_status is not None and review_status not in ALLOWED_REVIEW_STATUSES:
            raise ValueError(f"unsafe operator acknowledgment review_status: {review_status}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"operator acknowledgment ledger cannot set {unsafe_field}")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{field_name} keys must be non-empty strings")
            _validate_json_value(f"{field_name}.{key}", item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _validate_json_value(field_name, item)
        return
    if isinstance(value, str):
        if value in DISALLOWED_ACKNOWLEDGMENT_LABELS:
            raise ValueError(f"disallowed operator acknowledgment text: {value}")
        return
    if isinstance(value, (int, float, bool, type(None))):
        return
    raise ValueError(f"{field_name} must contain JSON-serializable values")


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    return value
