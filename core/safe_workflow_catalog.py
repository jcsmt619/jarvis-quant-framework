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


DEFAULT_SAFE_WORKFLOW_CATALOG_DIR = Path("reports/safe_workflow_catalog")
SAFE_WORKFLOW_CATALOG_JSON = "safe_workflow_catalog.json"
SAFE_WORKFLOW_CATALOG_MARKDOWN = "safe_workflow_catalog.md"

SAFE_WORKFLOW_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_WORKFLOW_LABELS = tuple(
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


@dataclass(frozen=True)
class SafeWorkflow:
    workflow_id: str
    name: str
    category: str
    command_hints: tuple[str, ...]
    input_paths: tuple[Path, ...]
    output_paths: tuple[Path, ...]
    required_labels: tuple[str, ...]
    safety_status: str
    allowed_human_review_behavior: tuple[str, ...]
    blocked_behavior: tuple[str, ...]
    description: str

    def validate(self) -> None:
        for field_name in (
            "workflow_id",
            "name",
            "category",
            "safety_status",
            "description",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"safe workflow requires {field_name}")
        for field_name in (
            "command_hints",
            "input_paths",
            "output_paths",
            "required_labels",
            "allowed_human_review_behavior",
            "blocked_behavior",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must be a non-empty tuple")
        for label in self.required_labels:
            if label not in SAFE_WORKFLOW_LABELS:
                raise ValueError(f"unsafe workflow label: {label}")
        for path in (*self.input_paths, *self.output_paths):
            _validate_catalog_path(path)


@dataclass(frozen=True)
class SafeWorkflowCatalogInput:
    catalog_id: str
    catalog_date: str
    generated_at_utc: str
    workflows: tuple[SafeWorkflow, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("catalog_id", "catalog_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"safe workflow catalog requires {field_name}")
        _parse_iso_date("catalog_date", self.catalog_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.workflows, tuple) or not self.workflows:
            raise ValueError("workflows must be a non-empty tuple")
        for workflow in self.workflows:
            workflow.validate()


def build_default_safe_workflow_catalog_input(
    *,
    catalog_date: date | None = None,
    now: datetime | None = None,
) -> SafeWorkflowCatalogInput:
    generated = now or datetime.now(tz=UTC)
    day = catalog_date or generated.date()
    return SafeWorkflowCatalogInput(
        catalog_id=f"18A-SAFE-WORKFLOW-CATALOG-{day.isoformat()}",
        catalog_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        workflows=default_safe_workflows(),
    )


def default_safe_workflows() -> tuple[SafeWorkflow, ...]:
    return (
        _workflow(
            "daily_research_summary",
            "Daily Research Summary",
            "daily_research_summaries",
            ("python scripts/run_daily_research_command_center.py",),
            ("reports/experiment_registry/", "engines/"),
            (
                "reports/daily_research_command_center/daily_research_summary.json",
                "reports/daily_research_command_center/daily_research_summary.md",
            ),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED),
            "Summarize deterministic research and safety context for human review.",
        ),
        _workflow(
            "weekly_review",
            "Weekly Review",
            "weekly_reviews",
            ("python scripts/run_weekly_review.py",),
            ("reports/daily_research_command_center/", "reports/experiment_registry/"),
            ("reports/weekly_review/weekly_review.json", "reports/weekly_review/weekly_review.md"),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Compile weekly research, blocked decisions, and next review actions.",
        ),
        _workflow(
            "operator_dashboard_snapshot",
            "Operator Dashboard Snapshot",
            "operator_dashboards",
            ("python scripts/run_operator_dashboard_snapshot.py",),
            ("reports/operator_runbook/", "reports/orchestrator/"),
            (
                "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json",
                "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.md",
            ),
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Create a monitor-only operator dashboard snapshot.",
        ),
        _workflow(
            "operator_runbook",
            "Operator Runbook",
            "operator_dashboards",
            ("python scripts/run_operator_runbook.py",),
            ("reports/daily_research_command_center/", "reports/weekly_review/"),
            ("reports/operator_runbook/operator_runbook.json", "reports/operator_runbook/operator_runbook.md"),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Provide an operator checklist for review-only workflows.",
        ),
        _workflow(
            "research_evidence_pack",
            "Research Evidence Pack",
            "evidence_packs",
            ("python scripts/run_research_evidence_pack.py",),
            ("reports/daily_research_command_center/", "reports/operator_runbook/"),
            (
                "reports/research_evidence_pack/research_evidence_pack.json",
                "reports/research_evidence_pack/research_evidence_pack.md",
            ),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Bundle research evidence for human review without changing execution state.",
        ),
        _workflow(
            "decision_journal",
            "Decision Journal",
            "decision_journals",
            ("python scripts/run_decision_journal.py",),
            ("reports/research_evidence_pack/", "reports/safety_scanner/"),
            ("reports/decision_journal/decision_journal.json", "reports/decision_journal/decision_journal.md"),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Record human-review outcomes, blocked outcomes, and follow-up actions.",
        ),
        _workflow(
            "report_index",
            "Report Index",
            "report_generators",
            ("python scripts/run_report_index.py",),
            ("reports/daily_research_command_center/", "reports/weekly_review/", "reports/decision_journal/"),
            ("reports/report_index/report_index.json", "reports/report_index/report_index.md"),
            (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Index safe report artifacts and mark missing artifacts blocked.",
        ),
        _workflow(
            "safety_scanner",
            "Safety Scanner",
            "safety_scanners",
            ("python scripts/check_jarvis_safety_scanner.py", "powershell scripts/run_jarvis_safety_scanner.ps1"),
            ("automation/", "core/", "risk/", "scripts/"),
            ("reports/safety_scanner/safety_scanner_status.json", "reports/safety_scanner/safety_scanner_status.md"),
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Scan for safety boundary regressions and block unsafe findings.",
        ),
        _workflow(
            "orchestrator_audit_reader",
            "Orchestrator Audit Reader",
            "queue_readers",
            ("python scripts/view_orchestrator_audit.py",),
            ("reports/orchestrator/audit/", "reports/manual_repair/direct-run/audit/"),
            ("reports/orchestrator/audit_reader/audit_reader.json", "reports/orchestrator/audit_reader/audit_reader.md"),
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Read audit ledger entries without mutating queue state.",
        ),
        _workflow(
            "orchestrator_heartbeat_reader",
            "Orchestrator Heartbeat Reader",
            "queue_readers",
            ("python scripts/view_orchestrator_heartbeat.py",),
            ("reports/orchestrator/heartbeat.json",),
            (
                "reports/orchestrator/heartbeat_reader/heartbeat_reader.json",
                "reports/orchestrator/heartbeat_reader/heartbeat_reader.md",
            ),
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
            "Read heartbeat state and surface stale or blocked conditions.",
        ),
    )


def build_safe_workflow_catalog_payload(catalog_input: SafeWorkflowCatalogInput) -> dict[str, Any]:
    catalog_input.validate()
    workflows = [_workflow_payload(workflow) for workflow in catalog_input.workflows]
    payload = {
        "phase": "18A",
        "workflow": "Safe Workflow Catalog",
        "catalog_id": catalog_input.catalog_id,
        "catalog_date": catalog_input.catalog_date,
        "generated_at_utc": catalog_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_WORKFLOW_LABELS),
        "summary": {
            "workflow_count": len(workflows),
            "category_counts": _count_by(workflows, "category"),
            "label_counts": _label_counts(workflows),
            "safety_status_counts": _count_by(workflows, "safety_status"),
        },
        "workflows": workflows,
        "blocked_behaviors": _blocked_behaviors(),
        "allowed_human_review_behaviors": _allowed_human_review_behaviors(),
    }
    _validate_json_value("safe_workflow_catalog_payload", payload)
    return _normalize_json_value(payload)


def write_safe_workflow_catalog(
    catalog_input: SafeWorkflowCatalogInput,
    *,
    out_dir: Path = DEFAULT_SAFE_WORKFLOW_CATALOG_DIR,
) -> tuple[Path, Path]:
    payload = build_safe_workflow_catalog_payload(catalog_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SAFE_WORKFLOW_CATALOG_JSON
    markdown_path = out_dir / SAFE_WORKFLOW_CATALOG_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_safe_workflow_catalog_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_safe_workflow_catalog_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("safe_workflow_catalog_payload", payload)
    lines = [
        "# 18A Safe Workflow Catalog",
        "",
        f"Catalog ID: {payload['catalog_id']}",
        f"Catalog Date: {payload['catalog_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE behaviors remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Workflows", payload["summary"]["workflow_count"]),
        "",
    ]
    lines.extend(_workflow_section(payload["workflows"]))
    lines.extend(_simple_section("Allowed Human-Review Behaviors", payload["allowed_human_review_behaviors"]))
    lines.extend(_simple_section("Blocked Behaviors", payload["blocked_behaviors"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY workflows may generate research artifacts.",
            "- MONITOR_ONLY workflows may read and summarize operational state.",
            "- PAPER_ONLY workflows may summarize paper-state artifacts only.",
            "- HUMAN_REVIEW_REQUIRED workflows may record review notes without execution.",
            "- BLOCKED_BY_SAFETY_GATE behaviors remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _workflow(
    workflow_id: str,
    name: str,
    category: str,
    command_hints: tuple[str, ...],
    input_paths: tuple[str, ...],
    output_paths: tuple[str, ...],
    labels: tuple[str, ...],
    description: str,
) -> SafeWorkflow:
    return SafeWorkflow(
        workflow_id=workflow_id,
        name=name,
        category=category,
        command_hints=command_hints,
        input_paths=tuple(Path(path) for path in input_paths),
        output_paths=tuple(Path(path) for path in output_paths),
        required_labels=labels,
        safety_status="LIVE TRADING: DISABLED",
        allowed_human_review_behavior=_allowed_human_review_behaviors(),
        blocked_behavior=_blocked_behaviors(),
        description=description,
    )


def _workflow_payload(workflow: SafeWorkflow) -> dict[str, Any]:
    workflow.validate()
    return {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "category": workflow.category,
        "command_hints": list(workflow.command_hints),
        "input_paths": [path.as_posix() for path in workflow.input_paths],
        "output_paths": [path.as_posix() for path in workflow.output_paths],
        "required_labels": list(workflow.required_labels),
        "safety_status": workflow.safety_status,
        "allowed_human_review_behavior": list(workflow.allowed_human_review_behavior),
        "blocked_behavior": list(workflow.blocked_behavior),
        "description": workflow.description,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": BLOCKED_BY_SAFETY_GATE in workflow.required_labels,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "real_paper_order_submitted": False,
        "secrets_required": False,
        "credential_file_used": False,
    }


def _allowed_human_review_behaviors() -> tuple[str, ...]:
    return (
        "review generated research artifacts",
        "record operator notes",
        "record blocked outcomes",
        "request more deterministic evidence",
        "keep trade-relevant interpretation HUMAN_REVIEW_REQUIRED",
    )


def _blocked_behaviors() -> tuple[str, ...]:
    return (
        "enable live trading",
        "submit broker orders",
        "add broker order routing",
        "perform broker order calls",
        "open secrets or credential files",
        "convert research output into trade instructions",
    )


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


def _workflow_section(workflows: list[dict[str, Any]]) -> list[str]:
    lines = ["## Workflows", ""]
    for item in workflows:
        labels = ", ".join(item["required_labels"])
        commands = "; ".join(item["command_hints"])
        outputs = ", ".join(item["output_paths"])
        lines.append(
            f"- {item['workflow_id']} | {item['category']} | {labels} | {item['safety_status']} | {commands} | outputs: {outputs}"
        )
    lines.append("")
    return lines


def _simple_section(title: str, items: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        lines.append(f"- {item}")
    lines.append("")
    return lines


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _label_counts(workflows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for workflow in workflows:
        for label in workflow["required_labels"]:
            counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _validate_catalog_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("safe workflow catalog cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("safe workflow catalog cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("safe workflow catalog paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("safe workflow catalog paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_WORKFLOW_LABELS:
            raise ValueError(f"unsafe workflow catalog label: {label}")
        if label in DISALLOWED_WORKFLOW_LABELS:
            raise ValueError(f"disallowed workflow catalog label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"safe workflow catalog cannot set {unsafe_field}")
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
        if value in DISALLOWED_WORKFLOW_LABELS:
            raise ValueError(f"disallowed workflow catalog text: {value}")
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
