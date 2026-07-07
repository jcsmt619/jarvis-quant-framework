from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.human_review_closeout_gate import (
    DEFAULT_HUMAN_REVIEW_CLOSEOUT_GATE_DIR,
    HUMAN_REVIEW_CLOSEOUT_GATE_JSON,
)
from core.human_review_queue import DEFAULT_HUMAN_REVIEW_QUEUE_DIR, HUMAN_REVIEW_QUEUE_JSON
from core.operator_acknowledgment_ledger import (
    ACKNOWLEDGED,
    DEFERRED,
    NOTED,
    OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON,
    PENDING_OPERATOR_REVIEW,
    REJECTED,
    DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR,
)
from core.operator_dashboard_snapshot import OPERATOR_DASHBOARD_SNAPSHOT_JSON
from core.report_index import REPORT_INDEX_JSON
from core.research_artifact_retention_policy import (
    DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
    RESEARCH_ARTIFACT_RETENTION_POLICY_JSON,
)
from core.research_cycle_audit_summary import (
    DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR,
    RESEARCH_CYCLE_AUDIT_SUMMARY_JSON,
)
from core.research_cycle_readiness_gate import (
    DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR,
    RESEARCH_CYCLE_READINESS_GATE_JSON,
)
from core.research_cycle_runner import (
    DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
    RESEARCH_CYCLE_MANIFEST_JSON,
)
from core.research_release_bundle import (
    DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR,
    RESEARCH_RELEASE_BUNDLE_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR = Path("reports/research_operations_console")
RESEARCH_OPERATIONS_CONSOLE_JSON = "research_operations_console.json"
RESEARCH_OPERATIONS_CONSOLE_MARKDOWN = "research_operations_console.md"

OPERATIONS_CONSOLE_COMPLETE = "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY"
OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW = "OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW"
OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE = "OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE"

SAFE_CONSOLE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
CONSOLE_STATES = (
    OPERATIONS_CONSOLE_COMPLETE,
    OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW,
    OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_CONSOLE_LABELS = tuple(
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
BASELINE_BLOCKED_WORKFLOWS = {
    "broker_order_call",
    "broker_order_routing",
    "live_trading",
    "order_execution",
    "secret_or_credential_access",
}
DATE_KEYS = (
    "console_date",
    "closeout_date",
    "ledger_date",
    "review_date",
    "gate_date",
    "retention_date",
    "audit_date",
    "cycle_date",
    "bundle_date",
    "snapshot_date",
    "index_date",
    "catalog_date",
    "report_date",
)


@dataclass(frozen=True)
class ResearchOperationsConsoleInput:
    console_id: str
    console_date: str
    generated_at_utc: str
    closeout_gate_path: Path = DEFAULT_HUMAN_REVIEW_CLOSEOUT_GATE_DIR / HUMAN_REVIEW_CLOSEOUT_GATE_JSON
    operator_acknowledgment_ledger_path: Path = (
        DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR / OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON
    )
    human_review_queue_path: Path = DEFAULT_HUMAN_REVIEW_QUEUE_DIR / HUMAN_REVIEW_QUEUE_JSON
    readiness_gate_path: Path = (
        DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR / RESEARCH_CYCLE_READINESS_GATE_JSON
    )
    retention_policy_path: Path = (
        DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR / RESEARCH_ARTIFACT_RETENTION_POLICY_JSON
    )
    audit_summary_path: Path = (
        DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR / RESEARCH_CYCLE_AUDIT_SUMMARY_JSON
    )
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON
    release_bundle_path: Path = DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR / RESEARCH_RELEASE_BUNDLE_JSON
    operator_dashboard_snapshot_path: Path = Path(
        "reports/operator_dashboard_snapshot"
    ) / OPERATOR_DASHBOARD_SNAPSHOT_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = (
        Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    )
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("console_id", "console_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research operations console requires {field_name}")
        _parse_iso_date("console_date", self.console_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.closeout_gate_path,
            self.operator_acknowledgment_ledger_path,
            self.human_review_queue_path,
            self.readiness_gate_path,
            self.retention_policy_path,
            self.audit_summary_path,
            self.manifest_path,
            self.release_bundle_path,
            self.operator_dashboard_snapshot_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_console_path(path)


def build_default_research_operations_console_input(
    *,
    console_date: date | None = None,
    now: datetime | None = None,
) -> ResearchOperationsConsoleInput:
    generated = now or datetime.now(tz=UTC)
    day = console_date or generated.date()
    return ResearchOperationsConsoleInput(
        console_id=f"23A-RESEARCH-OPERATIONS-CONSOLE-{day.isoformat()}",
        console_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_operations_console_payload(
    console_input: ResearchOperationsConsoleInput,
) -> dict[str, Any]:
    console_input.validate()
    console_day = datetime.strptime(console_input.console_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(console_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    closeout_payload = source_payloads.get("closeout_gate", {})
    ledger_payload = source_payloads.get("operator_acknowledgment_ledger", {})
    queue_payload = source_payloads.get("human_review_queue", {})
    retention_payload = source_payloads.get("retention_policy", {})

    missing_artifacts = _missing_artifacts(source_artifacts, closeout_payload)
    stale_artifacts = _stale_artifacts(
        source_artifacts,
        closeout_payload,
        console_day,
        console_input.max_source_age_days,
    )
    completed_items = _completed_items(closeout_payload, ledger_payload, source_artifacts)
    open_items = _open_items(closeout_payload, ledger_payload, queue_payload)
    blocked_items = _blocked_items(closeout_payload, source_payloads)
    rejected_items = _status_items(closeout_payload, ledger_payload, REJECTED, "rejected_items")
    deferred_items = _status_items(closeout_payload, ledger_payload, DEFERRED, "deferred_items")
    retention_items = _retention_items(retention_payload)
    queue_status = _queue_status(console_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(console_input.safety_scanner_path)
    safety_findings = _safety_findings(closeout_payload, safety_scanner_status)
    required_operator_actions = _required_operator_actions(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        open_items=open_items,
        blocked_items=blocked_items,
        rejected_items=rejected_items,
        deferred_items=deferred_items,
        retention_items=retention_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
        safety_findings=safety_findings,
    )
    safety_boundary_confirmation = _safety_boundary_confirmation()
    console_state = _console_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        open_items=open_items,
        blocked_items=blocked_items,
        rejected_items=rejected_items,
        deferred_items=deferred_items,
        retention_items=retention_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
        safety_findings=safety_findings,
        closeout_payload=closeout_payload,
    )

    payload = {
        "phase": "23A",
        "workflow": "Research Operations Console",
        "console_id": console_input.console_id,
        "console_date": console_input.console_date,
        "generated_at_utc": console_input.generated_at_utc,
        "console_state": console_state,
        "safety_boundary": safety_boundary_confirmation,
        "required_labels": [*SAFE_CONSOLE_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "completed_item_count": len(completed_items),
            "open_item_count": len(open_items),
            "blocked_item_count": len(blocked_items),
            "non_baseline_blocked_item_count": len(_non_baseline_blocked_items(blocked_items)),
            "rejected_item_count": len(rejected_items),
            "deferred_item_count": len(deferred_items),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "retention_item_count": len(retention_items),
            "safety_finding_count": len(safety_findings),
            "required_operator_action_count": len(required_operator_actions),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *completed_items,
                    *open_items,
                    *blocked_items,
                    *rejected_items,
                    *deferred_items,
                    *missing_artifacts,
                    *stale_artifacts,
                    *retention_items,
                    *safety_findings,
                    *required_operator_actions,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "completed_items": completed_items,
        "open_items": open_items,
        "blocked_items": blocked_items,
        "rejected_items": rejected_items,
        "deferred_items": deferred_items,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "retention_items": retention_items,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "safety_findings": safety_findings,
        "required_operator_actions": required_operator_actions,
        "final_console_summary": _final_console_summary(
            console_state=console_state,
            completed_items=completed_items,
            open_items=open_items,
            blocked_items=blocked_items,
            rejected_items=rejected_items,
            deferred_items=deferred_items,
            missing_artifacts=missing_artifacts,
            stale_artifacts=stale_artifacts,
            retention_items=retention_items,
            safety_findings=safety_findings,
            required_operator_actions=required_operator_actions,
        ),
    }
    _validate_json_value("research_operations_console_payload", payload)
    return _normalize_json_value(payload)


def write_research_operations_console(
    console_input: ResearchOperationsConsoleInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_operations_console_payload(console_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_OPERATIONS_CONSOLE_JSON
    markdown_path = out_dir / RESEARCH_OPERATIONS_CONSOLE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_operations_console_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_operations_console_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_operations_console_payload", payload)
    lines = [
        "# 23A Research Operations Console",
        "",
        f"Console ID: {payload['console_id']}",
        f"Console Date: {payload['console_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Console State: {payload['console_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Operator operations consoles are records-only and do not enable live trading, broker routing, broker calls, order execution, or automatic actions.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Research-Cycle Console Summary",
        "",
        payload["final_console_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Completed items", payload["summary"]["completed_item_count"]),
        _summary_line("Open items", payload["summary"]["open_item_count"]),
        _summary_line("Blocked items", payload["summary"]["blocked_item_count"]),
        _summary_line("Rejected items", payload["summary"]["rejected_item_count"]),
        _summary_line("Deferred items", payload["summary"]["deferred_item_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Retention items", payload["summary"]["retention_item_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        "",
    ]
    lines.extend(_section("Source Artifacts", payload["source_artifacts"]))
    lines.extend(_section("Completed Items", payload["completed_items"]))
    lines.extend(_section("Open Items", payload["open_items"]))
    lines.extend(_section("Blocked Items", payload["blocked_items"]))
    lines.extend(_section("Rejected Items", payload["rejected_items"]))
    lines.extend(_section("Deferred Items", payload["deferred_items"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Stale Artifacts", payload["stale_artifacts"]))
    lines.extend(_section("Retention Items", payload["retention_items"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Required Operator Actions", payload["required_operator_actions"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(
        [
            "## Safety Boundary Confirmation",
            "",
            "- RESEARCH_ONLY operations console generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "- Records-only console; no live trading, broker routing, broker calls, order execution, or automatic actions are enabled.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(console_input: ResearchOperationsConsoleInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("closeout_gate", "22A Human Review Closeout Gate", console_input.closeout_gate_path),
        ("operator_acknowledgment_ledger", "21B Operator Acknowledgment Ledger", console_input.operator_acknowledgment_ledger_path),
        ("human_review_queue", "21A Human Review Queue", console_input.human_review_queue_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", console_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", console_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", console_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", console_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", console_input.release_bundle_path),
        ("operator_dashboard_snapshot", "17B Operator Dashboard Snapshot", console_input.operator_dashboard_snapshot_path),
        ("report_index", "17A Report Index", console_input.report_index_path),
        ("safe_workflow_catalog", "18A Safe Workflow Catalog", console_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", console_input.safety_scanner_path),
    )
    statuses = []
    for artifact_id, name, path in artifact_paths:
        payload = _read_json_object(path)
        if payload is None:
            statuses.append(
                {
                    "artifact_id": artifact_id,
                    "name": name,
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "missing",
                    "summary": f"{name} JSON was not found or could not be parsed.",
                    "path": path.as_posix(),
                    "generated_date": None,
                    "generated_at_utc": None,
                    "phase": None,
                    "workflow": None,
                    "payload": {},
                }
            )
            continue
        _validate_json_value(artifact_id, payload)
        statuses.append(
            {
                "artifact_id": artifact_id,
                "name": name,
                "label": payload.get("safety_boundary", {}).get(
                    "label",
                    payload.get("label", HUMAN_REVIEW_REQUIRED),
                ),
                "status": "present",
                "summary": _artifact_summary(payload, f"{name} is present."),
                "path": path.as_posix(),
                "generated_date": _generated_date(payload),
                "generated_at_utc": payload.get("generated_at_utc"),
                "phase": payload.get("phase"),
                "workflow": payload.get("workflow", name),
                "payload": payload,
            }
        )
    return [_normalize_json_value(item) for item in statuses]


def _missing_artifacts(
    source_artifacts: list[dict[str, Any]],
    closeout_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        {
            "artifact_id": artifact["artifact_id"],
            "workflow_id": f"missing_{artifact['artifact_id']}",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "path": artifact["path"],
            "summary": artifact["summary"],
            "source_artifact_id": "23a_source_artifacts",
        }
        for artifact in source_artifacts
        if artifact["status"] != "present"
    ]
    for item in _items_from_payload(closeout_payload, "missing_artifacts"):
        value = dict(item)
        value.setdefault("artifact_id", value.get("workflow_id") or "artifact")
        value.setdefault("workflow_id", f"missing_{value.get('artifact_id', 'artifact')}")
        value.setdefault("label", BLOCKED_BY_SAFETY_GATE)
        value.setdefault("status", "missing")
        value.setdefault("summary", "Missing artifact recorded by 22A closeout gate.")
        value["source_artifact_id"] = "closeout_gate"
        _validate_json_value("missing_artifact", value)
        items.append(value)
    return _dedupe_by_id(items, "workflow_id")


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    closeout_payload: dict[str, Any],
    console_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    items = []
    for artifact in source_artifacts:
        if artifact["status"] != "present":
            continue
        generated_date = artifact.get("generated_date")
        if not isinstance(generated_date, str):
            items.append(_stale_item(artifact, "unknown", "Source artifact generated date was not present."))
            continue
        try:
            artifact_day = datetime.strptime(generated_date[:10], "%Y-%m-%d").date()
        except ValueError:
            items.append(_stale_item(artifact, generated_date, "Source artifact generated date was invalid."))
            continue
        age_days = (console_day - artifact_day).days
        if age_days > max_source_age_days:
            items.append(
                _stale_item(
                    artifact,
                    generated_date,
                    f"Source artifact is {age_days} days old; maximum allowed age is {max_source_age_days} days.",
                )
            )
    for item in _items_from_payload(closeout_payload, "stale_artifacts"):
        value = dict(item)
        value.setdefault("workflow_id", value.get("artifact_id") or "stale_artifact")
        value.setdefault("label", HUMAN_REVIEW_REQUIRED)
        value.setdefault("status", "stale")
        value.setdefault("summary", "Stale artifact recorded by 22A closeout gate.")
        value["source_artifact_id"] = "closeout_gate"
        _validate_json_value("stale_artifact", value)
        items.append(value)
    return _dedupe_by_id(items, "workflow_id")


def _stale_item(artifact: dict[str, Any], generated_date: str, summary: str) -> dict[str, Any]:
    value = {
        "artifact_id": artifact["artifact_id"],
        "workflow_id": f"stale_{artifact['artifact_id']}",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "stale",
        "path": artifact["path"],
        "generated_date": generated_date,
        "summary": summary,
        "source_artifact_id": "23a_source_artifacts",
    }
    _validate_json_value("stale_artifact", value)
    return _normalize_json_value(value)


def _completed_items(
    closeout_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    source_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        {
            "item_id": f"present_{artifact['artifact_id']}",
            "artifact_id": artifact["artifact_id"],
            "label": artifact.get("label", HUMAN_REVIEW_REQUIRED),
            "status": "present",
            "summary": artifact.get("summary", "Source artifact present."),
            "source_artifact_id": "23a_source_artifacts",
        }
        for artifact in source_artifacts
        if artifact["status"] == "present"
    ]
    if closeout_payload.get("closeout_state"):
        items.append(
            {
                "item_id": "22A-CLOSEOUT-GATE-RECORDED",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": closeout_payload.get("closeout_state"),
                "summary": "22A closeout gate was included in the 23A operations console.",
                "source_artifact_id": "closeout_gate",
            }
        )
    for entry in _items_from_payload(ledger_payload, "ledger_entries"):
        if entry.get("review_status") in {ACKNOWLEDGED, NOTED}:
            value = _packet_item(entry, "review_item_id", "ledger_entry")
            value["item_id"] = f"completed_{value.get('review_item_id')}"
            value["status"] = entry.get("review_status")
            value["source_artifact_id"] = "operator_acknowledgment_ledger"
            items.append(value)
    return _dedupe_by_id(items, "item_id")


def _open_items(
    closeout_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    queue_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for key in ("unresolved_review_items", "required_next_human_review_actions"):
        for item in _items_from_payload(closeout_payload, key):
            value = _packet_item(item, "review_item_id", key)
            value["item_id"] = f"open_{value.get('review_item_id') or value.get('action_id')}"
            value["status"] = value.get("review_status") or value.get("status") or "open_review_item"
            value["source_artifact_id"] = "closeout_gate"
            items.append(value)
    for entry in _items_from_payload(ledger_payload, "ledger_entries"):
        if entry.get("review_status") == PENDING_OPERATOR_REVIEW:
            value = _packet_item(entry, "review_item_id", "ledger_entry")
            value["item_id"] = f"open_{value.get('review_item_id')}"
            value["status"] = PENDING_OPERATOR_REVIEW
            value["source_artifact_id"] = "operator_acknowledgment_ledger"
            items.append(value)
    for item in _items_from_payload(queue_payload, "next_operator_actions"):
        value = _packet_item(item, "action_id", "next_operator_action")
        value["item_id"] = f"open_{value.get('action_id')}"
        value["status"] = value.get("status", "open_review_item")
        value["source_artifact_id"] = "human_review_queue"
        items.append(value)
    return _dedupe_by_id(items, "item_id")


def _blocked_items(
    closeout_payload: dict[str, Any],
    source_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        {
            "item_id": workflow_id,
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Workflow remains blocked by 23A records-only safety boundary.",
            "source_artifact_id": "23a_safety_boundary",
        }
        for workflow_id in BASELINE_BLOCKED_WORKFLOWS
    ]
    for key in ("blocked_workflows", "safety_findings"):
        for item in _items_from_payload(closeout_payload, key):
            value = _packet_item(item, "workflow_id", key)
            value["item_id"] = value.get("workflow_id") or value.get("finding_id") or key
            value["label"] = BLOCKED_BY_SAFETY_GATE
            value["status"] = value.get("status", "blocked")
            value["source_artifact_id"] = "closeout_gate"
            items.append(value)
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "blocked_workflows"):
            value = _packet_item(item, "workflow_id", "blocked_workflows")
            value["item_id"] = value.get("workflow_id", "blocked_workflow")
            value["label"] = BLOCKED_BY_SAFETY_GATE
            value["status"] = value.get("status", "blocked")
            value["source_artifact_id"] = artifact_id
            items.append(value)
    return _dedupe_by_id(items, "item_id")


def _status_items(
    closeout_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    review_status: str,
    closeout_key: str,
) -> list[dict[str, Any]]:
    items = []
    for item in _items_from_payload(closeout_payload, closeout_key):
        value = _packet_item(item, "review_item_id", closeout_key)
        value["item_id"] = f"{review_status.lower()}_{value.get('review_item_id')}"
        value["status"] = review_status
        value["source_artifact_id"] = "closeout_gate"
        items.append(value)
    for entry in _items_from_payload(ledger_payload, "ledger_entries"):
        if entry.get("review_status") == review_status:
            value = _packet_item(entry, "review_item_id", "ledger_entry")
            value["item_id"] = f"{review_status.lower()}_{value.get('review_item_id')}"
            value["status"] = review_status
            value["source_artifact_id"] = "operator_acknowledgment_ledger"
            items.append(value)
    return _dedupe_by_id(items, "item_id")


def _retention_items(retention_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for artifact in _items_from_payload(retention_payload, "artifacts"):
        action = artifact.get("retention_action")
        if action in {"review", "archive_candidate", "blocked_delete"}:
            value = {
                "item_id": f"retention_{artifact.get('artifact_id', 'artifact')}",
                "artifact_id": artifact.get("artifact_id", "artifact"),
                "label": artifact.get("label", HUMAN_REVIEW_REQUIRED),
                "status": action,
                "retention_action": action,
                "automatic_delete_allowed": False,
                "dry_run_only": True,
                "summary": "; ".join(artifact.get("retention_reasons", []))
                if isinstance(artifact.get("retention_reasons"), list)
                else "Retention item recorded for human review.",
                "source_artifact_id": "retention_policy",
            }
            _validate_json_value("retention_item", value)
            items.append(value)
    return _dedupe_by_id(items, "item_id")


def _queue_status(path: Path) -> dict[str, Any]:
    payload = _read_json_value(path)
    if payload is None:
        return {
            "workflow_id": "master_plan_queue",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "Master plan queue JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "queue_item_count": 0,
            "next_phase": None,
        }
    if not isinstance(payload, list):
        return {
            "workflow_id": "master_plan_queue",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "invalid",
            "summary": "Master plan queue root is not a list.",
            "path": path.as_posix(),
            "queue_item_count": 0,
            "next_phase": None,
        }
    items = [_queue_item(item) for item in payload if isinstance(item, dict)]
    value = {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for 23A operator console context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": _next_phase(items),
        "items": items,
    }
    _validate_json_value("queue_status", value)
    return _normalize_json_value(value)


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to 23A.",
            "path": path.as_posix(),
            "finding_count": 0,
            "passed": None,
            "findings": [],
        }
    findings = payload.get("findings", [])
    finding_count = payload.get("finding_count", len(findings) if isinstance(findings, list) else 0)
    passed = payload.get("passed")
    value = {
        "workflow_id": "safety_scanner",
        "label": payload.get("label", HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE),
        "status": payload.get("status", "passed" if passed else "not_run"),
        "summary": payload.get("summary", "Safety scanner status supplied to 23A."),
        "path": path.as_posix(),
        "finding_count": finding_count,
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _safety_findings(
    closeout_payload: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for item in _items_from_payload(closeout_payload, "safety_findings"):
        value = _packet_item(item, "finding_id", "safety_finding")
        value["finding_id"] = value.get("finding_id") or value.get("workflow_id") or "safety_finding"
        value["label"] = BLOCKED_BY_SAFETY_GATE
        value["status"] = value.get("status", "failed")
        value["source_artifact_id"] = "closeout_gate"
        items.append(value)
    if safety_scanner_status.get("passed") is False or safety_scanner_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": safety_scanner_status.get("status", "failed"),
                "summary": safety_scanner_status.get("summary", "Safety scanner status requires review."),
                "source_artifact_id": "safety_scanner_status",
            }
        )
    for finding in safety_scanner_status.get("findings", []):
        if not isinstance(finding, dict):
            continue
        value = {
            "finding_id": finding.get("rule_id") or finding.get("finding_id") or "safety_finding",
            "workflow_id": "safety_scanner",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "failed",
            "summary": finding.get("summary") or finding.get("message") or "Safety scanner finding recorded.",
            "source_artifact_id": "safety_scanner_status",
        }
        _validate_json_value("safety_finding", value)
        items.append(value)
    return _dedupe_by_id(items, "finding_id")


def _required_operator_actions(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
    safety_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions = [
        _action("23A-REVIEW-OPERATIONS-CONSOLE", "Review this 23A operations console as a records-only artifact.")
    ]
    if open_items:
        actions.append(_action("23A-REVIEW-OPEN-ITEMS", "Review open research-cycle items without enabling automatic actions."))
    if missing_artifacts:
        actions.append(_action("23A-RESOLVE-MISSING-ARTIFACTS", "Regenerate or explicitly accept missing source artifacts."))
    if stale_artifacts:
        actions.append(_action("23A-REFRESH-STALE-ARTIFACTS", "Refresh stale artifacts or record human acceptance."))
    if _non_baseline_blocked_items(blocked_items):
        actions.append(_action("23A-REVIEW-BLOCKED-ITEMS", "Review non-baseline blocked items while keeping safety blocks active."))
    if rejected_items:
        actions.append(_action("23A-ADDRESS-REJECTED-ITEMS", "Address rejected operator review items before the next cycle."))
    if deferred_items:
        actions.append(_action("23A-SCHEDULE-DEFERRED-ITEMS", "Schedule deferred operator review items for the next cycle."))
    if retention_items:
        actions.append(_action("23A-REVIEW-RETENTION-ITEMS", "Review retention items with dry-run records only."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(_action("23A-REVIEW-QUEUE-STATUS", "Review missing or invalid master plan queue status."))
    if safety_findings or safety_scanner_status.get("passed") is False:
        actions.append(_action("23A-RESOLVE-SAFETY-FINDINGS", "Resolve safety findings while leaving live trading disabled."))
    return _dedupe_by_id(actions, "action_id")


def _action(action_id: str, summary: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "open_review_item",
        "summary": summary,
    }


def _queue_item(item: dict[str, Any]) -> dict[str, Any]:
    value = {
        "phase": item.get("phase"),
        "title": item.get("title"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "queued",
        "summary": item.get("spec", "Queued roadmap item."),
    }
    _validate_json_value("queue_item", value)
    return _normalize_json_value(value)


def _next_phase(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in items:
        if item.get("phase") == "23A":
            return item
    return items[0] if items else None


def _console_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
    safety_findings: list[dict[str, Any]],
    closeout_payload: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or safety_findings
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
        or closeout_payload.get("closeout_state") == BLOCKED_BY_SAFETY_GATE
        or _non_baseline_blocked_items(blocked_items)
    ):
        return OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE
    if open_items or stale_artifacts or rejected_items or deferred_items or retention_items:
        return OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW
    return OPERATIONS_CONSOLE_COMPLETE


def _final_console_summary(
    *,
    console_state: str,
    completed_items: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    required_operator_actions: list[dict[str, Any]],
) -> str:
    return (
        f"Research-cycle console state is {console_state}. "
        f"Completed items: {len(completed_items)}. "
        f"Open items: {len(open_items)}. "
        f"Blocked items: {len(blocked_items)}. "
        f"Rejected items: {len(rejected_items)}. "
        f"Deferred items: {len(deferred_items)}. "
        f"Missing artifacts: {len(missing_artifacts)}. "
        f"Stale artifacts: {len(stale_artifacts)}. "
        f"Retention items: {len(retention_items)}. "
        f"Safety findings: {len(safety_findings)}. "
        f"Required operator actions: {len(required_operator_actions)}. "
        "Safety boundary confirmed: console is records-only and does not enable live trading, broker routing, broker calls, order execution, or automatic actions. "
        "LIVE TRADING: DISABLED."
    )


def _safety_boundary_confirmation() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "console_records_only": True,
        "trade_instructions_created": False,
        "broker_actions_created": False,
        "execution_permissions_created": False,
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


def _packet_item(item: dict[str, Any], id_key: str, fallback_id: str) -> dict[str, Any]:
    value = dict(item)
    value.setdefault(id_key, value.get("workflow_id") or value.get("action_id") or value.get("artifact_id") or fallback_id)
    value.setdefault("label", HUMAN_REVIEW_REQUIRED)
    value.setdefault("summary", "Operations console item recorded.")
    _validate_json_value("packet_item", value)
    return _normalize_json_value(value)


def _non_baseline_blocked_items(blocked_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in blocked_items
        if str(item.get("workflow_id") or item.get("item_id")) not in BASELINE_BLOCKED_WORKFLOWS
        and not str(item.get("workflow_id", "")).startswith("missing_")
    ]


def _items_from_payload(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = payload.get(key, [])
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _without_payload(item: dict[str, Any]) -> dict[str, Any]:
    value = {key: field for key, field in item.items() if key != "payload"}
    _validate_json_value("source_artifact_without_payload", value)
    return _normalize_json_value(value)


def _artifact_summary(payload: dict[str, Any], fallback: str) -> str:
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return fallback
    counts = [
        f"{key}={summary[key]}"
        for key in sorted(summary)
        if key.endswith("_count") and isinstance(summary[key], int)
    ]
    workflow = payload.get("workflow", "Artifact")
    return f"{workflow} status: {', '.join(counts[:4]) if counts else 'metadata recorded'}."


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_console_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in DATE_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value[:10]
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("item_id")
            or item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("finding_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("review_status") or item.get("retention_action") or item.get("status") or "recorded"
        summary = item.get("summary") or item.get("operator_note") or item.get("workflow") or item.get("name") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
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


def _dedupe_by_id(items: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        value = dict(item)
        value.setdefault(id_key, "item")
        _validate_json_value(id_key, value)
        by_id[str(value[id_key])] = _normalize_json_value(value)
    return sorted(by_id.values(), key=_sort_key)


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_artifact_id", item.get("source", ""))),
        str(
            item.get("item_id")
            or item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_console_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research operations console cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research operations console cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research operations console paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research operations console paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_CONSOLE_LABELS:
            raise ValueError(f"unsafe research operations console label: {label}")
        console_state = value.get("console_state")
        if console_state is not None and console_state not in CONSOLE_STATES:
            raise ValueError(f"invalid research operations console state: {console_state}")
        review_status = value.get("review_status")
        if review_status is not None and review_status not in {
            ACKNOWLEDGED,
            REJECTED,
            DEFERRED,
            NOTED,
            PENDING_OPERATOR_REVIEW,
        }:
            raise ValueError(f"invalid research operations console review_status: {review_status}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research operations console cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("research operations console cannot allow automatic deletion")
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
        if value in DISALLOWED_CONSOLE_LABELS:
            raise ValueError(f"disallowed research operations console text: {value}")
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
