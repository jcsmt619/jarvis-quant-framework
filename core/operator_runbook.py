from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_OPERATOR_RUNBOOK_DIR = Path("reports/operator_runbook")
OPERATOR_RUNBOOK_JSON = "operator_runbook.json"
OPERATOR_RUNBOOK_MARKDOWN = "operator_runbook.md"

SAFE_OPERATOR_RUNBOOK_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_OPERATOR_RUNBOOK_LABELS = tuple(
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
)


@dataclass(frozen=True)
class OperatorRunbookInput:
    runbook_id: str
    runbook_date: str
    generated_at_utc: str
    daily_research_payload: dict[str, Any] | None = None
    weekly_review_payload: dict[str, Any] | None = None
    experiment_review_items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    promotion_review_items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    safety_findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    operator_notes: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("runbook_id", "runbook_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"operator runbook requires {field_name}")
        _parse_iso_date("runbook_date", self.runbook_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        for value in (self.daily_research_payload, self.weekly_review_payload):
            if value is not None:
                _validate_json_value("operator_runbook_context", value)
        for field_name in (
            "experiment_review_items",
            "promotion_review_items",
            "safety_findings",
            "operator_notes",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be a tuple")
            for item in values:
                _validate_json_value(field_name, item)


def build_default_operator_runbook_input(
    *,
    runbook_date: date | None = None,
    now: datetime | None = None,
) -> OperatorRunbookInput:
    generated = now or datetime.now(tz=UTC)
    day = runbook_date or generated.date()
    return OperatorRunbookInput(
        runbook_id=f"15B-OPERATOR-RUNBOOK-{day.isoformat()}",
        runbook_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        operator_notes=(
            {
                "note_id": "15B-DEFAULT-NOTE",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Use this runbook as an operator checklist only.",
            },
        ),
    )


def build_operator_runbook_payload(runbook_input: OperatorRunbookInput) -> dict[str, Any]:
    runbook_input.validate()

    sections = _runbook_sections()
    allowed_workflows = _allowed_human_review_workflows()
    blocked_workflows = _blocked_workflows()
    experiment_items = _normalize_items(
        runbook_input.experiment_review_items,
        default_label=RESEARCH_ONLY,
    )
    promotion_items = _normalize_items(
        runbook_input.promotion_review_items,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    safety_findings = _normalize_items(
        runbook_input.safety_findings,
        default_label=BLOCKED_BY_SAFETY_GATE,
    )
    operator_notes = _normalize_items(
        runbook_input.operator_notes,
        default_label=HUMAN_REVIEW_REQUIRED,
    )

    payload = {
        "phase": "15B",
        "workflow": "Operator Runbook",
        "runbook_id": runbook_input.runbook_id,
        "runbook_date": runbook_input.runbook_date,
        "generated_at_utc": runbook_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "summary": {
            "checklist_section_count": len(sections),
            "checklist_item_count": sum(len(section["items"]) for section in sections),
            "allowed_human_review_workflow_count": len(allowed_workflows),
            "blocked_workflow_count": len(blocked_workflows),
            "experiment_review_item_count": len(experiment_items),
            "promotion_review_item_count": len(promotion_items),
            "safety_finding_count": len(safety_findings),
            "operator_note_count": len(operator_notes),
        },
        "checklists": sections,
        "allowed_human_review_workflows": allowed_workflows,
        "blocked_workflows": blocked_workflows,
        "context": {
            "daily_research": _daily_research_summary(runbook_input.daily_research_payload),
            "weekly_review": _weekly_review_summary(runbook_input.weekly_review_payload),
            "experiment_review_items": experiment_items,
            "promotion_review_items": promotion_items,
            "safety_findings": safety_findings,
            "operator_notes": operator_notes,
        },
    }
    _validate_json_value("operator_runbook_payload", payload)
    return _normalize_json_value(payload)


def write_operator_runbook(
    runbook_input: OperatorRunbookInput,
    *,
    out_dir: Path = DEFAULT_OPERATOR_RUNBOOK_DIR,
) -> tuple[Path, Path]:
    payload = build_operator_runbook_payload(runbook_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / OPERATOR_RUNBOOK_JSON
    markdown_path = out_dir / OPERATOR_RUNBOOK_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_operator_runbook_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_operator_runbook_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("operator_runbook_payload", payload)
    lines = [
        "# 15B Operator Runbook",
        "",
        f"Runbook ID: {payload['runbook_id']}",
        f"Runbook Date: {payload['runbook_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "LIVE TRADING: DISABLED. No secrets, broker routing, broker calls, or order execution are used.",
        "",
        "## Operator Checklists",
        "",
    ]
    for section in payload["checklists"]:
        lines.extend(_checklist_section(section))
    lines.extend(_section("Allowed Human-Review Workflows", payload["allowed_human_review_workflows"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(_section("Experiment Review Context", payload["context"]["experiment_review_items"]))
    lines.extend(_section("Promotion Review Context", payload["context"]["promotion_review_items"]))
    lines.extend(_section("Safety Findings", payload["context"]["safety_findings"]))
    lines.extend(_section("Operator Notes", payload["context"]["operator_notes"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY outputs only.",
            "- MONITOR_ONLY and PAPER_ONLY states may be checked, logged, and reviewed.",
            "- HUMAN_REVIEW_REQUIRED workflows are allowed only as review workflows.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _runbook_sections() -> list[dict[str, Any]]:
    return [
        _section_payload(
            "daily_startup",
            "Daily Startup",
            HUMAN_REVIEW_REQUIRED,
            (
                "Confirm operator identity and runbook date.",
                "Open research dashboards and monitoring views.",
                "Confirm LIVE TRADING: DISABLED before reviewing any output.",
                "Record startup timestamp in operator notes.",
            ),
        ),
        _section_payload(
            "safety_preflight",
            "Safety Preflight",
            BLOCKED_BY_SAFETY_GATE,
            (
                "Confirm live_trading_enabled=false.",
                "Confirm broker_order_routing_enabled=false.",
                "Confirm broker_order_call_performed=false.",
                "Confirm real_paper_order_submitted=false.",
                "Confirm secrets_required=false and no credential files are opened.",
            ),
        ),
        _section_payload(
            "research_review",
            "Research Review",
            RESEARCH_ONLY,
            (
                "Review daily research command center outputs.",
                "Check wealth and moonshot summaries for stale data flags.",
                "Label trade-relevant interpretations HUMAN_REVIEW_REQUIRED.",
                "Do not convert research output into instructions.",
            ),
        ),
        _section_payload(
            "experiment_review",
            "Experiment Review",
            RESEARCH_ONLY,
            (
                "Review deterministic experiment registry entries.",
                "Confirm walk-forward and slippage evidence is present before promotion discussion.",
                "Keep incomplete experiments RESEARCH_ONLY or BLOCKED_BY_SAFETY_GATE.",
                "Log missing evidence without changing execution state.",
            ),
        ),
        _section_payload(
            "weekly_review",
            "Weekly Review",
            HUMAN_REVIEW_REQUIRED,
            (
                "Review weekly summary counts and blocked decisions.",
                "Confirm blocked decisions remain blocked.",
                "Record any unresolved safety findings for next review.",
                "Escalate trade-relevant interpretation to HUMAN_REVIEW_REQUIRED.",
            ),
        ),
        _section_payload(
            "promotion_review",
            "Promotion Review",
            HUMAN_REVIEW_REQUIRED,
            (
                "Review promotion gate evidence only.",
                "Confirm validation, paper history, and unresolved findings.",
                "Keep promotion outcomes paper-only unless a future approved phase changes policy.",
                "Block any request that needs broker routing or live trading.",
            ),
        ),
        _section_payload(
            "shutdown",
            "Shutdown",
            MONITOR_ONLY,
            (
                "Confirm no broker calls or order submission occurred.",
                "Save operator notes and generated reports.",
                "Record shutdown timestamp.",
                "Leave LIVE TRADING: DISABLED.",
            ),
        ),
    ]


def _allowed_human_review_workflows() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": "review_daily_research",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Operator may review deterministic research summaries and add notes.",
        },
        {
            "workflow_id": "review_experiment_evidence",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Operator may review experiment evidence without changing execution state.",
        },
        {
            "workflow_id": "review_promotion_gate",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Operator may review promotion gate evidence and record a human decision.",
        },
        {
            "workflow_id": "review_safety_findings",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Operator may review blocked safety findings and decide next research action.",
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
            "summary": "Broker routing is outside the 15B operator runbook.",
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
            "summary": "Order execution is not part of this workflow.",
        },
        {
            "workflow_id": "secret_or_credential_access",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Secrets and credential files are not required and must not be opened.",
        },
    ]


def _section_payload(
    section_id: str,
    title: str,
    label: str,
    descriptions: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "title": title,
        "label": label,
        "items": [
            {
                "item_id": f"{section_id}_{index:02d}",
                "label": label,
                "status": "check_required",
                "description": description,
            }
            for index, description in enumerate(descriptions, start=1)
        ],
    }


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
        "live_trading_enabled": False,
        "secrets_required": False,
        "status": "LIVE TRADING: DISABLED",
    }


def _daily_research_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "status": "not_supplied",
            "label": HUMAN_REVIEW_REQUIRED,
            "summary": "Daily research payload was not supplied.",
        }
    return {
        "phase": payload.get("phase"),
        "workflow": payload.get("workflow"),
        "report_date": payload.get("report_date"),
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": payload.get("safety_boundary", {}).get("status", "recorded"),
        "summary": (
            f"{payload.get('summary', {}).get('experiment_count', 0)} experiments and "
            f"{payload.get('summary', {}).get('safety_scanner_finding_count', 0)} safety findings summarized."
        ),
    }


def _weekly_review_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "status": "not_supplied",
            "label": HUMAN_REVIEW_REQUIRED,
            "summary": "Weekly review payload was not supplied.",
        }
    return {
        "phase": payload.get("phase"),
        "workflow": payload.get("workflow"),
        "review_id": payload.get("review_id"),
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": payload.get("safety_boundary", {}).get("status", "recorded"),
        "summary": (
            f"{payload.get('summary', {}).get('experiment_count', 0)} experiments and "
            f"{payload.get('summary', {}).get('blocked_decision_count', 0)} blocked decisions summarized."
        ),
    }


def _checklist_section(section: dict[str, Any]) -> list[str]:
    lines = [f"### {section['title']}", ""]
    for item in section["items"]:
        lines.append(f"- [ ] {item['item_id']} | {item['label']} | {item['description']}")
    lines.append("")
    return lines


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("workflow_id")
            or item.get("experiment_id")
            or item.get("strategy_id")
            or item.get("finding_id")
            or item.get("note_id")
            or item.get("id")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status") or item.get("promotion_status") or "recorded"
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
        _validate_json_value("operator_runbook_item", value)
        normalized.append(_normalize_json_value(value))
    return sorted(normalized, key=_sort_key)


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("engine", "")),
        str(
            item.get("workflow_id")
            or item.get("experiment_id")
            or item.get("strategy_id")
            or item.get("finding_id")
            or item.get("note_id")
            or json.dumps(item, sort_keys=True)
        ),
    )


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
        if label is not None and label not in SAFE_OPERATOR_RUNBOOK_LABELS:
            raise ValueError(f"unsafe operator runbook label: {label}")
        if label in DISALLOWED_OPERATOR_RUNBOOK_LABELS:
            raise ValueError(f"disallowed operator runbook label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"operator runbook cannot set {unsafe_field}")
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
        if value in DISALLOWED_OPERATOR_RUNBOOK_LABELS:
            raise ValueError(f"disallowed operator runbook text: {value}")
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
