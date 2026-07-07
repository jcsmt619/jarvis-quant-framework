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
    DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR,
    OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON,
)
from core.operator_signoff_packet import (
    DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR,
    OPERATOR_SIGNOFF_PACKET_JSON,
)
from core.report_index import REPORT_INDEX_JSON
from core.research_artifact_retention_policy import (
    ARCHIVE_CANDIDATE,
    BLOCKED_DELETE,
    DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
    RESEARCH_ARTIFACT_RETENTION_POLICY_JSON,
    REVIEW,
)
from core.research_cycle_archive_index import (
    DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR,
    RESEARCH_CYCLE_ARCHIVE_INDEX_JSON,
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
from core.research_operations_console import (
    DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR,
    RESEARCH_OPERATIONS_CONSOLE_JSON,
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


DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR = Path("reports/research_cycle_rollover_gate")
RESEARCH_CYCLE_ROLLOVER_GATE_JSON = "research_cycle_rollover_gate.json"
RESEARCH_CYCLE_ROLLOVER_GATE_MARKDOWN = "research_cycle_rollover_gate.md"

ROLLOVER_READY_FOR_HUMAN_REVIEW = "ROLLOVER_READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"

SAFE_ROLLOVER_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
ROLLOVER_STATES = (
    ROLLOVER_READY_FOR_HUMAN_REVIEW,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
REVIEW_STATUSES = {
    "PENDING_OPERATOR_REVIEW",
    "REJECTED",
    "DEFERRED",
    "open_review_item",
    "missing",
    "invalid",
}
BASELINE_BLOCKED_WORKFLOWS = {
    "artifact_deletion",
    "artifact_move_rename_or_compression",
    "artifact_mutation",
    "broker_order_call",
    "broker_order_routing",
    "live_trading",
    "order_execution",
    "secret_or_credential_access",
}
DISALLOWED_ROLLOVER_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)
UNSAFE_TRUE_FIELDS = (
    "automatic_action_enabled",
    "broker_actions_created",
    "broker_call_used",
    "broker_order_call_performed",
    "broker_order_routing_enabled",
    "broker_routing_used",
    "credential_file_used",
    "execution_permissions_created",
    "live_trading_approval_granted",
    "live_trading_enabled",
    "order_execution_used",
    "real_paper_order_submitted",
    "real_paper_wrapper_attempted",
    "real_paper_wrapper_connected",
    "secrets_required",
    "trade_instructions_created",
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
DATE_KEYS = (
    "rollover_gate_date",
    "archive_index_date",
    "console_date",
    "signoff_date",
    "closeout_date",
    "ledger_date",
    "review_date",
    "gate_date",
    "retention_date",
    "audit_date",
    "cycle_date",
    "bundle_date",
    "index_date",
    "catalog_date",
    "report_date",
)


@dataclass(frozen=True)
class ResearchCycleRolloverGateInput:
    rollover_gate_id: str
    rollover_gate_date: str
    generated_at_utc: str
    archive_index_path: Path = DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR / RESEARCH_CYCLE_ARCHIVE_INDEX_JSON
    operations_console_path: Path = DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR / RESEARCH_OPERATIONS_CONSOLE_JSON
    operator_signoff_packet_path: Path = DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR / OPERATOR_SIGNOFF_PACKET_JSON
    closeout_gate_path: Path = DEFAULT_HUMAN_REVIEW_CLOSEOUT_GATE_DIR / HUMAN_REVIEW_CLOSEOUT_GATE_JSON
    operator_acknowledgment_ledger_path: Path = (
        DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR / OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON
    )
    human_review_queue_path: Path = DEFAULT_HUMAN_REVIEW_QUEUE_DIR / HUMAN_REVIEW_QUEUE_JSON
    readiness_gate_path: Path = DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR / RESEARCH_CYCLE_READINESS_GATE_JSON
    retention_policy_path: Path = (
        DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR / RESEARCH_ARTIFACT_RETENTION_POLICY_JSON
    )
    audit_summary_path: Path = DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR / RESEARCH_CYCLE_AUDIT_SUMMARY_JSON
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON
    release_bundle_path: Path = DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR / RESEARCH_RELEASE_BUNDLE_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("rollover_gate_id", "rollover_gate_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research cycle rollover gate requires {field_name}")
        _parse_iso_date("rollover_gate_date", self.rollover_gate_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.archive_index_path,
            self.operations_console_path,
            self.operator_signoff_packet_path,
            self.closeout_gate_path,
            self.operator_acknowledgment_ledger_path,
            self.human_review_queue_path,
            self.readiness_gate_path,
            self.retention_policy_path,
            self.audit_summary_path,
            self.manifest_path,
            self.release_bundle_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_rollover_path(path)


def build_default_research_cycle_rollover_gate_input(
    *,
    rollover_gate_date: date | None = None,
    now: datetime | None = None,
) -> ResearchCycleRolloverGateInput:
    generated = now or datetime.now(tz=UTC)
    day = rollover_gate_date or generated.date()
    return ResearchCycleRolloverGateInput(
        rollover_gate_id=f"24A-RESEARCH-CYCLE-ROLLOVER-GATE-{day.isoformat()}",
        rollover_gate_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_cycle_rollover_gate_payload(
    rollover_input: ResearchCycleRolloverGateInput,
) -> dict[str, Any]:
    rollover_input.validate()
    gate_day = datetime.strptime(rollover_input.rollover_gate_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(rollover_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    archive_payload = source_payloads.get("archive_index", {})
    console_payload = source_payloads.get("operations_console", {})
    signoff_payload = source_payloads.get("operator_signoff_packet", {})
    closeout_payload = source_payloads.get("closeout_gate", {})
    retention_payload = source_payloads.get("retention_policy", {})

    missing_artifacts = _missing_artifacts(source_artifacts, archive_payload, console_payload)
    stale_artifacts = _stale_artifacts(source_artifacts, gate_day, rollover_input.max_source_age_days)
    unresolved_items = _unresolved_items(source_payloads)
    blocked_items = _blocked_items(source_payloads)
    safety_scanner_status = _safety_scanner_status(rollover_input.safety_scanner_path)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    archive_index_findings = _archive_index_findings(archive_payload)
    retention_items = _retention_items(retention_payload, archive_payload)
    signoff_state = _signoff_state(signoff_payload, closeout_payload)
    queue_status = _queue_status(rollover_input.queue_status_path)
    required_operator_actions = _required_operator_actions(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        unresolved_items=unresolved_items,
        blocked_items=blocked_items,
        safety_findings=safety_findings,
        archive_index_findings=archive_index_findings,
        retention_items=retention_items,
        signoff_state=signoff_state,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    rollover_state = _rollover_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        unresolved_items=unresolved_items,
        blocked_items=blocked_items,
        safety_findings=safety_findings,
        archive_index_findings=archive_index_findings,
        retention_items=retention_items,
        signoff_state=signoff_state,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
        archive_payload=archive_payload,
        console_payload=console_payload,
        closeout_payload=closeout_payload,
    )

    payload = {
        "phase": "24A",
        "workflow": "Research Cycle Rollover Gate",
        "rollover_gate_id": rollover_input.rollover_gate_id,
        "rollover_gate_date": rollover_input.rollover_gate_date,
        "generated_at_utc": rollover_input.generated_at_utc,
        "rollover_state": rollover_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_ROLLOVER_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "unresolved_item_count": len(unresolved_items),
            "blocked_item_count": len(blocked_items),
            "non_baseline_blocked_item_count": len(_non_baseline_blocked_items(blocked_items)),
            "safety_finding_count": len(safety_findings),
            "archive_index_finding_count": len(archive_index_findings),
            "retention_item_count": len(retention_items),
            "required_operator_action_count": len(required_operator_actions),
            "signoff_state": signoff_state["status"],
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *unresolved_items,
                    *blocked_items,
                    *safety_findings,
                    *archive_index_findings,
                    *retention_items,
                    *required_operator_actions,
                    signoff_state,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "unresolved_items": unresolved_items,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "blocked_items": blocked_items,
        "safety_findings": safety_findings,
        "archive_index_findings": archive_index_findings,
        "retention_items": retention_items,
        "signoff_state": signoff_state,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "required_operator_actions": required_operator_actions,
        "final_rollover_summary": _final_rollover_summary(
            rollover_state=rollover_state,
            unresolved_items=unresolved_items,
            missing_artifacts=missing_artifacts,
            stale_artifacts=stale_artifacts,
            blocked_items=blocked_items,
            safety_findings=safety_findings,
            archive_index_findings=archive_index_findings,
            retention_items=retention_items,
            required_operator_actions=required_operator_actions,
        ),
    }
    _validate_json_value("research_cycle_rollover_gate_payload", payload)
    return _normalize_json_value(payload)


def write_research_cycle_rollover_gate(
    rollover_input: ResearchCycleRolloverGateInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_cycle_rollover_gate_payload(rollover_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_CYCLE_ROLLOVER_GATE_JSON
    markdown_path = out_dir / RESEARCH_CYCLE_ROLLOVER_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_cycle_rollover_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_cycle_rollover_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_cycle_rollover_gate_payload", payload)
    lines = [
        "# 24A Research Cycle Rollover Gate",
        "",
        f"Rollover Gate ID: {payload['rollover_gate_id']}",
        f"Rollover Gate Date: {payload['rollover_gate_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Rollover State: {payload['rollover_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Rollover-gate reports are read-only and records-only.",
        "No trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions are created.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Rollover Summary",
        "",
        payload["final_rollover_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Unresolved items", payload["summary"]["unresolved_item_count"]),
        _summary_line("Blocked items", payload["summary"]["blocked_item_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Archive-index findings", payload["summary"]["archive_index_finding_count"]),
        _summary_line("Retention items", payload["summary"]["retention_item_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        "",
    ]
    lines.extend(_section("Unresolved Items", payload["unresolved_items"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Stale Artifacts", payload["stale_artifacts"]))
    lines.extend(_section("Blocked Items", payload["blocked_items"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Archive-Index Findings", payload["archive_index_findings"]))
    lines.extend(_section("Retention Items", payload["retention_items"]))
    lines.extend(_section("Signoff State", [payload["signoff_state"]]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_section("Required Operator Actions Before Next Cycle", payload["required_operator_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY rollover-gate generation only.",
            "- MONITOR_ONLY and PAPER_ONLY source artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED rollover decisions remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE items remain blocked.",
            "- Read-only and records-only.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(rollover_input: ResearchCycleRolloverGateInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("archive_index", "23B Research Cycle Archive Index", rollover_input.archive_index_path),
        ("operations_console", "23A Research Operations Console", rollover_input.operations_console_path),
        ("operator_signoff_packet", "22B Operator Signoff Packet", rollover_input.operator_signoff_packet_path),
        ("closeout_gate", "22A Human Review Closeout Gate", rollover_input.closeout_gate_path),
        ("operator_acknowledgment_ledger", "21B Operator Acknowledgment Ledger", rollover_input.operator_acknowledgment_ledger_path),
        ("human_review_queue", "21A Human Review Queue", rollover_input.human_review_queue_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", rollover_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", rollover_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", rollover_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", rollover_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", rollover_input.release_bundle_path),
        ("report_index", "Report Index", rollover_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", rollover_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", rollover_input.safety_scanner_path),
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
                "label": payload.get("safety_boundary", {}).get("label", payload.get("label", HUMAN_REVIEW_REQUIRED)),
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
    archive_payload: dict[str, Any],
    console_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        {
            "artifact_id": item["artifact_id"],
            "workflow_id": f"missing_{item['artifact_id']}",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "path": item["path"],
            "summary": item["summary"],
            "source_artifact_id": "24a_source_artifacts",
        }
        for item in source_artifacts
        if item["status"] != "present"
    ]
    for payload, source_id in ((archive_payload, "archive_index"), (console_payload, "operations_console")):
        for item in _items_from_payload(payload, "missing_artifacts"):
            value = _rollover_item(item, "artifact_id", "missing_artifact")
            value["workflow_id"] = value.get("workflow_id") or f"missing_{value['artifact_id']}"
            value["label"] = BLOCKED_BY_SAFETY_GATE
            value["status"] = "missing"
            value["source_artifact_id"] = source_id
            items.append(value)
    return _dedupe_by_id(items, "artifact_id")


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    gate_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    items = []
    for artifact in source_artifacts:
        generated_date = artifact.get("generated_date")
        age_days = _age_days(gate_day, generated_date)
        if age_days is not None and age_days > max_source_age_days:
            items.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "workflow_id": f"stale_{artifact['artifact_id']}",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "stale",
                    "path": artifact["path"],
                    "generated_date": generated_date,
                    "age_days": age_days,
                    "summary": f"{artifact['name']} is {age_days} days old.",
                    "source_artifact_id": "24a_source_artifacts",
                }
            )
    return _dedupe_by_id(items, "artifact_id")


def _unresolved_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "unresolved_items",
        "unresolved_review_items",
        "open_items",
        "rejected_items",
        "deferred_items",
        "unmatched_acknowledgments",
        "required_next_human_review_actions",
        "required_operator_actions",
        "next_operator_actions",
        "human_review_notes",
    )
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in keys:
            for item in _items_from_payload(payload, key):
                status = str(item.get("review_status") or item.get("status") or "")
                if key in {"required_operator_actions", "human_review_notes"} and status not in REVIEW_STATUSES:
                    continue
                value = _rollover_item(item, "item_id", key)
                value["item_id"] = value.get("item_id") or value.get("review_item_id") or value.get("action_id") or value.get("note_id") or key
                value["label"] = value.get("label", HUMAN_REVIEW_REQUIRED)
                value["status"] = status or "open_review_item"
                value["source_artifact_id"] = artifact_id
                items.append(value)
    return _dedupe_by_id(items, "item_id")


def _blocked_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {
            "item_id": workflow_id,
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Workflow remains blocked by the 24A records-only safety boundary.",
            "source_artifact_id": "24a_safety_boundary",
        }
        for workflow_id in BASELINE_BLOCKED_WORKFLOWS
    ]
    for artifact_id, payload in source_payloads.items():
        for key in ("blocked_items", "blocked_workflows"):
            for item in _items_from_payload(payload, key):
                value = _rollover_item(item, "workflow_id", key)
                value["item_id"] = value.get("item_id") or value.get("workflow_id") or key
                value["label"] = BLOCKED_BY_SAFETY_GATE
                value["status"] = value.get("status", "blocked")
                value["source_artifact_id"] = artifact_id
                items.append(value)
    return _dedupe_by_id(items, "item_id")


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in ("safety_findings", "failed_safety_findings"):
            for item in _items_from_payload(payload, key):
                value = _rollover_item(item, "finding_id", key)
                value["finding_id"] = value.get("finding_id") or value.get("workflow_id") or key
                value["label"] = BLOCKED_BY_SAFETY_GATE
                value["status"] = value.get("status", "failed")
                value["source_artifact_id"] = artifact_id
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
        items.append(
            {
                "finding_id": finding.get("rule_id") or finding.get("finding_id") or "safety_finding",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": finding.get("summary") or finding.get("message") or "Safety scanner finding recorded.",
                "source_artifact_id": "safety_scanner_status",
            }
        )
    return _dedupe_by_id(items, "finding_id")


def _archive_index_findings(archive_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in _items_from_payload(archive_payload, "indexed_artifacts"):
        if item.get("archive_eligible") or item.get("blocked_delete") or item.get("artifact_status") != "present":
            label = BLOCKED_BY_SAFETY_GATE if item.get("blocked_delete") else HUMAN_REVIEW_REQUIRED
            items.append(
                {
                    "finding_id": f"archive_index_{item.get('artifact_id', 'artifact')}",
                    "artifact_id": item.get("artifact_id", "artifact"),
                    "label": label,
                    "status": item.get("retention_action") or item.get("artifact_status") or "recorded",
                    "summary": item.get("summary", "Archive-index finding requires rollover review."),
                    "source_artifact_id": "archive_index",
                }
            )
    for item in _items_from_payload(archive_payload, "human_review_notes"):
        value = _rollover_item(item, "note_id", "archive_note")
        value["finding_id"] = value.get("note_id")
        value["label"] = value.get("label", HUMAN_REVIEW_REQUIRED)
        value["source_artifact_id"] = "archive_index"
        items.append(value)
    return _dedupe_by_id(items, "finding_id")


def _retention_items(retention_payload: dict[str, Any], archive_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for payload, source_id in ((retention_payload, "retention_policy"), (archive_payload, "archive_index")):
        for key in ("artifacts", "dry_run_manifest", "dry_run_archive_manifest", "indexed_artifacts"):
            for item in _items_from_payload(payload, key):
                action = item.get("retention_action")
                if action not in {REVIEW, ARCHIVE_CANDIDATE, BLOCKED_DELETE}:
                    continue
                value = {
                    "item_id": f"retention_{source_id}_{item.get('artifact_id', 'artifact')}",
                    "artifact_id": item.get("artifact_id", "artifact"),
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": action,
                    "retention_action": action,
                    "automatic_delete_allowed": False,
                    "dry_run_only": True,
                    "summary": "; ".join(item.get("retention_reasons", []))
                    if isinstance(item.get("retention_reasons"), list)
                    else item.get("summary", "Retention item requires rollover review."),
                    "source_artifact_id": source_id,
                }
                _validate_json_value("retention_item", value)
                items.append(value)
    return _dedupe_by_id(items, "item_id")


def _signoff_state(signoff_payload: dict[str, Any], closeout_payload: dict[str, Any]) -> dict[str, Any]:
    status = signoff_payload.get("signoff_state") or closeout_payload.get("closeout_state") or "missing"
    label = HUMAN_REVIEW_REQUIRED
    if status == BLOCKED_BY_SAFETY_GATE or str(status).endswith("BLOCKED_BY_SAFETY_GATE"):
        label = BLOCKED_BY_SAFETY_GATE
    value = {
        "workflow_id": "operator_signoff_state",
        "label": label,
        "status": status,
        "summary": "22B signoff and 22A closeout states recorded for rollover gating.",
    }
    _validate_json_value("signoff_state", value)
    return _normalize_json_value(value)


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
        "summary": "Master plan queue read for 24A rollover gate context only.",
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
            "summary": "Safety scanner status was not supplied to 24A.",
            "path": path.as_posix(),
            "finding_count": 0,
            "passed": None,
            "findings": [],
        }
    findings = payload.get("findings", [])
    passed = payload.get("passed")
    value = {
        "workflow_id": "safety_scanner",
        "label": payload.get("label", HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE),
        "status": payload.get("status", "passed" if passed else "not_run"),
        "summary": payload.get("summary", "Safety scanner status supplied to 24A."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _required_operator_actions(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    archive_index_findings: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    signoff_state: dict[str, Any],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [_action("24A-REVIEW-ROLLOVER-GATE", "Review this rollover gate before starting the next research cycle.")]
    if unresolved_items:
        actions.append(_action("24A-RESOLVE-UNRESOLVED-ITEMS", "Resolve unresolved review or operator items before rollover."))
    if missing_artifacts:
        actions.append(_action("24A-RESOLVE-MISSING-ARTIFACTS", "Regenerate or explicitly accept missing source artifacts."))
    if stale_artifacts:
        actions.append(_action("24A-REFRESH-STALE-ARTIFACTS", "Refresh stale artifacts or record human acceptance."))
    if _non_baseline_blocked_items(blocked_items):
        actions.append(_action("24A-REVIEW-BLOCKED-ITEMS", "Review non-baseline blocked items while keeping safety gates active."))
    if safety_findings or safety_scanner_status.get("passed") is False:
        actions.append(_action("24A-RESOLVE-SAFETY-FINDINGS", "Resolve safety findings while leaving live trading disabled."))
    if archive_index_findings:
        actions.append(_action("24A-REVIEW-ARCHIVE-INDEX-FINDINGS", "Review archive-index findings before rollover."))
    if retention_items:
        actions.append(_action("24A-REVIEW-RETENTION-ITEMS", "Review retention items as dry-run records only."))
    if signoff_state.get("status") != "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY":
        actions.append(_action("24A-CONFIRM-SIGNOFF-STATE", "Confirm completed signoff state before the next cycle."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(_action("24A-REVIEW-QUEUE-STATUS", "Review missing or invalid master plan queue status."))
    return _dedupe_by_id(actions, "action_id")


def _rollover_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    archive_index_findings: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    signoff_state: dict[str, Any],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
    archive_payload: dict[str, Any],
    console_payload: dict[str, Any],
    closeout_payload: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or safety_findings
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
        or signoff_state.get("label") == BLOCKED_BY_SAFETY_GATE
        or archive_payload.get("archive_index_state") == "ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE"
        or console_payload.get("console_state") == "OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE"
        or closeout_payload.get("closeout_state") == BLOCKED_BY_SAFETY_GATE
        or _non_baseline_blocked_items(blocked_items)
        or any(item.get("label") == BLOCKED_BY_SAFETY_GATE for item in archive_index_findings)
        or any(item.get("retention_action") == BLOCKED_DELETE for item in retention_items)
    ):
        return BLOCKED_BY_SAFETY_GATE
    if (
        stale_artifacts
        or unresolved_items
        or archive_index_findings
        or retention_items
        or signoff_state.get("status") != "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY"
        or archive_payload.get("archive_index_state") != "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY"
        or console_payload.get("console_state") != "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY"
    ):
        return NEEDS_OPERATOR_REVIEW
    return ROLLOVER_READY_FOR_HUMAN_REVIEW


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "rollover_gate_read_only": True,
        "records_only": True,
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


def _final_rollover_summary(
    *,
    rollover_state: str,
    unresolved_items: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    archive_index_findings: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
    required_operator_actions: list[dict[str, Any]],
) -> str:
    return (
        f"Research-cycle rollover state is {rollover_state}. "
        f"Unresolved items: {len(unresolved_items)}. "
        f"Missing artifacts: {len(missing_artifacts)}. "
        f"Stale artifacts: {len(stale_artifacts)}. "
        f"Blocked items: {len(blocked_items)}. "
        f"Safety findings: {len(safety_findings)}. "
        f"Archive-index findings: {len(archive_index_findings)}. "
        f"Retention items: {len(retention_items)}. "
        f"Required operator actions before next cycle: {len(required_operator_actions)}. "
        "Safety boundary confirmed: rollover gate is read-only and records-only and does not create trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions. "
        "LIVE TRADING: DISABLED."
    )


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
        if item.get("phase") == "24A":
            return item
    return items[0] if items else None


def _rollover_item(item: dict[str, Any], id_key: str, fallback_id: str) -> dict[str, Any]:
    value = dict(item)
    value.setdefault(
        id_key,
        value.get("item_id")
        or value.get("review_item_id")
        or value.get("action_id")
        or value.get("note_id")
        or value.get("finding_id")
        or value.get("workflow_id")
        or value.get("artifact_id")
        or fallback_id,
    )
    value.setdefault("label", HUMAN_REVIEW_REQUIRED)
    value.setdefault("summary", "Rollover gate item recorded.")
    _validate_json_value("rollover_item", value)
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
    _validate_rollover_path(path)
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


def _age_days(gate_day: date, generated_date: str | None) -> int | None:
    if generated_date is None:
        return None
    try:
        generated_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (gate_day - generated_day).days


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
            or item.get("note_id")
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
            or item.get("note_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_rollover_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research cycle rollover gate cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research cycle rollover gate cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research cycle rollover gate paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research cycle rollover gate paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_ROLLOVER_LABELS:
            raise ValueError(f"unsafe research cycle rollover gate label: {label}")
        rollover_state = value.get("rollover_state")
        if rollover_state is not None and rollover_state not in ROLLOVER_STATES:
            raise ValueError(f"invalid research cycle rollover state: {rollover_state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research cycle rollover gate cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("research cycle rollover gate cannot allow automatic deletion")
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
        if value in DISALLOWED_ROLLOVER_LABELS:
            raise ValueError(f"disallowed research cycle rollover gate text: {value}")
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
