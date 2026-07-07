from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from automation.safety_scanner import SafetyScanResult
from core.research_evidence_pack import (
    build_default_research_evidence_pack_input,
    build_research_evidence_pack_payload,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_DECISION_JOURNAL_DIR = Path("reports/decision_journal")
DECISION_JOURNAL_JSON = "decision_journal.json"
DECISION_JOURNAL_MARKDOWN = "decision_journal.md"

SAFE_DECISION_JOURNAL_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_DECISION_JOURNAL_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)
UNSAFE_TRUE_FIELDS = (
    "live_trading_enabled",
    "broker_order_routing_enabled",
    "broker_order_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_routing_used",
    "broker_call_used",
    "order_execution_used",
    "secrets_required",
    "credential_file_used",
    "prohibited_trade_labels_present",
)
SORT_KEYS = (
    "decision_id",
    "action_id",
    "reference_id",
    "workflow_id",
    "note_id",
    "finding_id",
    "id",
    "summary",
)


@dataclass(frozen=True)
class DecisionJournalInput:
    journal_id: str
    journal_date: str
    generated_at_utc: str
    decision_records: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    blocked_outcomes: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    follow_up_actions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    evidence_pack_references: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    safety_scan_result: SafetyScanResult | None = None
    safety_scanner_status: dict[str, Any] | None = None
    operator_notes: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("journal_id", "journal_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"decision journal requires {field_name}")
        _parse_iso_date("journal_date", self.journal_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if self.safety_scanner_status is not None:
            _validate_json_value("safety_scanner_status", self.safety_scanner_status)
        for field_name in (
            "decision_records",
            "blocked_outcomes",
            "follow_up_actions",
            "evidence_pack_references",
            "operator_notes",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be a tuple")
            for item in values:
                _validate_json_value(field_name, item)


def build_default_decision_journal_input(
    *,
    journal_date: date | None = None,
    now: datetime | None = None,
) -> DecisionJournalInput:
    generated = now or datetime.now(tz=UTC)
    day = journal_date or generated.date()
    evidence_pack = build_research_evidence_pack_payload(
        build_default_research_evidence_pack_input(evidence_date=day, now=generated)
    )
    return DecisionJournalInput(
        journal_id=f"16B-DECISION-JOURNAL-{day.isoformat()}",
        journal_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        decision_records=(
            {
                "decision_id": "16B-DEFAULT-HUMAN-REVIEW-OUTCOME",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "recorded_for_review",
                "workflow_id": "record_human_review_outcome",
                "summary": "Human review outcome placeholder recorded without changing execution state.",
                "evidence_reference_id": evidence_pack["pack_id"],
            },
        ),
        blocked_outcomes=(
            {
                "decision_id": "16B-LIVE-TRADING-BLOCK",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "workflow_id": "live_trading",
                "summary": "Live trading remains disabled and cannot be enabled by this journal.",
            },
        ),
        follow_up_actions=(
            {
                "action_id": "16B-DEFAULT-FOLLOW-UP",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review the evidence pack and record operator notes before the next research phase.",
            },
        ),
        evidence_pack_references=(
            {
                "reference_id": evidence_pack["pack_id"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "referenced",
                "path_hint": str(DEFAULT_DECISION_JOURNAL_DIR.parent / "research_evidence_pack"),
                "summary": "16A research evidence pack reference for audit continuity.",
            },
        ),
        safety_scanner_status=evidence_pack["evidence"]["safety_scanner_status"],
        operator_notes=(
            {
                "note_id": "16B-DEFAULT-OPERATOR-NOTE",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Decision journal is research-only and preserves audit history only.",
            },
        ),
    )


def build_decision_journal_payload(journal_input: DecisionJournalInput) -> dict[str, Any]:
    journal_input.validate()

    allowed_workflows = _allowed_review_workflows()
    blocked_workflows = _blocked_workflows()
    decisions = _normalize_items(
        journal_input.decision_records,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    blocked_outcomes = _normalize_items(
        journal_input.blocked_outcomes,
        default_label=BLOCKED_BY_SAFETY_GATE,
    )
    follow_ups = _normalize_items(
        journal_input.follow_up_actions,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    evidence_refs = _normalize_items(
        journal_input.evidence_pack_references,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    safety_status = _safety_scan_payload(
        journal_input.safety_scan_result,
        journal_input.safety_scanner_status,
    )
    operator_notes = _normalize_items(
        journal_input.operator_notes,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    history = _journal_history(decisions, blocked_outcomes, follow_ups, operator_notes)

    payload = {
        "phase": "16B",
        "workflow": "Decision Journal",
        "journal_id": journal_input.journal_id,
        "journal_date": journal_input.journal_date,
        "generated_at_utc": journal_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_DECISION_JOURNAL_LABELS),
        "summary": {
            "decision_record_count": len(decisions),
            "blocked_outcome_count": len(blocked_outcomes),
            "follow_up_action_count": len(follow_ups),
            "evidence_pack_reference_count": len(evidence_refs),
            "allowed_review_workflow_count": len(allowed_workflows),
            "blocked_workflow_count": len(blocked_workflows),
            "operator_note_count": len(operator_notes),
            "safety_scanner_status": safety_status["status"],
            "safety_scanner_finding_count": safety_status["finding_count"],
            "history_event_count": len(history),
            "label_counts": _count_by(
                [
                    *decisions,
                    *blocked_outcomes,
                    *follow_ups,
                    *evidence_refs,
                    safety_status,
                    *operator_notes,
                ],
                "label",
            ),
        },
        "allowed_review_workflows": allowed_workflows,
        "blocked_workflows": blocked_workflows,
        "journal": {
            "decision_records": decisions,
            "blocked_outcomes": blocked_outcomes,
            "follow_up_actions": follow_ups,
            "evidence_pack_references": evidence_refs,
            "safety_scanner_status": safety_status,
            "operator_notes": operator_notes,
            "history": history,
        },
    }
    _validate_json_value("decision_journal_payload", payload)
    return _normalize_json_value(payload)


def write_decision_journal(
    journal_input: DecisionJournalInput,
    *,
    out_dir: Path = DEFAULT_DECISION_JOURNAL_DIR,
) -> tuple[Path, Path]:
    payload = build_decision_journal_payload(journal_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / DECISION_JOURNAL_JSON
    markdown_path = out_dir / DECISION_JOURNAL_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_decision_journal_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_decision_journal_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("decision_journal_payload", payload)
    journal = payload["journal"]
    lines = [
        "# 16B Decision Journal",
        "",
        f"Journal ID: {payload['journal_id']}",
        f"Journal Date: {payload['journal_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE workflows and outcomes remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Decision records", payload["summary"]["decision_record_count"]),
        _summary_line("Blocked outcomes", payload["summary"]["blocked_outcome_count"]),
        _summary_line("Follow-up actions", payload["summary"]["follow_up_action_count"]),
        _summary_line("Evidence pack references", payload["summary"]["evidence_pack_reference_count"]),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        _summary_line("History events", payload["summary"]["history_event_count"]),
        "",
    ]
    lines.extend(_section("Allowed Review Workflows", payload["allowed_review_workflows"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(_section("Decision Records", journal["decision_records"]))
    lines.extend(_section("Blocked Outcomes", journal["blocked_outcomes"]))
    lines.extend(_section("Follow-Up Actions", journal["follow_up_actions"]))
    lines.extend(_section("Evidence Pack References", journal["evidence_pack_references"]))
    lines.extend(_section("Safety Scanner Status", [journal["safety_scanner_status"]]))
    lines.extend(_section("Operator Notes", journal["operator_notes"]))
    lines.extend(_section("Audit History", journal["history"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY records preserve research decisions only.",
            "- MONITOR_ONLY and PAPER_ONLY states are audit states, not execution instructions.",
            "- HUMAN_REVIEW_REQUIRED outcomes require operator review.",
            "- BLOCKED_BY_SAFETY_GATE outcomes and workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _allowed_review_workflows() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": "record_human_review_outcome",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Record a human review outcome without changing execution state.",
        },
        {
            "workflow_id": "record_blocked_outcome",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "allowed_blocked_record_only",
            "summary": "Record blocked safety outcomes for audit history only.",
        },
        {
            "workflow_id": "record_follow_up_action",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Record research follow-up actions for later human review.",
        },
        {
            "workflow_id": "reference_evidence_pack",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Attach evidence pack references without opening secrets or broker routes.",
        },
        {
            "workflow_id": "record_operator_note",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Record operator notes for audit continuity.",
        },
    ]


def _blocked_workflows() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": "live_trading",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Live trading remains disabled.",
        },
        {
            "workflow_id": "broker_order_routing",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker routing cannot be added or enabled by the decision journal.",
        },
        {
            "workflow_id": "broker_order_call",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker order calls are not allowed.",
        },
        {
            "workflow_id": "order_execution",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Order execution is outside this research-only workflow.",
        },
        {
            "workflow_id": "secret_or_credential_access",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Secrets and credential files are not required and must not be opened.",
        },
    ]


def _journal_history(
    decisions: list[dict[str, Any]],
    blocked_outcomes: list[dict[str, Any]],
    follow_ups: list[dict[str, Any]],
    operator_notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for category, items in (
        ("decision_record", decisions),
        ("blocked_outcome", blocked_outcomes),
        ("follow_up_action", follow_ups),
        ("operator_note", operator_notes),
    ):
        for index, item in enumerate(items, start=1):
            item_id = _first_present(item, SORT_KEYS) or f"{category}_{index}"
            events.append(
                {
                    "history_id": f"{category}:{item_id}",
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": item.get("status", "recorded"),
                    "source_id": item_id,
                    "source_type": category,
                    "summary": item.get("summary", "Recorded for audit history."),
                }
            )
    return sorted(events, key=_sort_key)


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_routing_enabled": False,
        "broker_routing_used": False,
        "broker_call_used": False,
        "order_execution_used": False,
        "live_trading_enabled": False,
        "secrets_required": False,
        "credential_file_used": False,
        "prohibited_trade_labels_present": False,
        "status": "LIVE TRADING: DISABLED",
    }


def _safety_scan_payload(
    result: SafetyScanResult | None,
    supplied_status: dict[str, Any] | None,
) -> dict[str, Any]:
    if result is not None:
        return {
            "status": "passed" if result.passed else "blocked",
            "label": HUMAN_REVIEW_REQUIRED if result.passed else BLOCKED_BY_SAFETY_GATE,
            "summary": "Safety scanner result supplied to decision journal.",
            "passed": result.passed,
            "finding_count": len(result.findings),
            "scanned_files": result.scanned_files,
            "skipped_files": list(result.skipped_files),
            "findings": [_dataclass_payload(finding) for finding in result.findings],
        }

    if supplied_status is not None:
        value = dict(supplied_status)
        value.setdefault("label", HUMAN_REVIEW_REQUIRED)
        value.setdefault("finding_count", len(value.get("findings", ())))
        value.setdefault("summary", "Safety scanner status supplied to decision journal.")
        _validate_json_value("safety_scanner_status", value)
        return _normalize_json_value(value)

    return {
        "status": "not_run",
        "label": HUMAN_REVIEW_REQUIRED,
        "summary": "Safety scanner status was not supplied to the decision journal.",
        "passed": None,
        "finding_count": 0,
        "scanned_files": 0,
        "skipped_files": [],
        "findings": [],
    }


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = _first_present(item, SORT_KEYS) or item.get("status") or "item"
        label = item.get("label", "n/a")
        status = item.get("status") or "recorded"
        summary = item.get("summary") or item.get("description") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
    lines.append("")
    return lines


def _normalize_items(
    items: tuple[dict[str, Any], ...],
    *,
    default_label: str,
) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        value = dict(item)
        value.setdefault("label", default_label)
        _validate_json_value("decision_journal_item", value)
        normalized.append(_normalize_json_value(value))
    return sorted(normalized, key=_sort_key)


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _dataclass_payload(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise ValueError("expected dataclass payload")
    return asdict(value)


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_type", "")),
        str(_first_present(item, SORT_KEYS) or json.dumps(item, sort_keys=True)),
    )


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


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
        if label is not None and label not in SAFE_DECISION_JOURNAL_LABELS:
            raise ValueError(f"unsafe decision journal label: {label}")
        if label in DISALLOWED_DECISION_JOURNAL_LABELS:
            raise ValueError(f"disallowed decision journal label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"decision journal cannot set {unsafe_field}")
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
        if value in DISALLOWED_DECISION_JOURNAL_LABELS:
            raise ValueError(f"disallowed decision journal text: {value}")
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
