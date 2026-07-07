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
from core.operator_acknowledgment_ledger import (
    DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR,
    OPERATOR_ACKNOWLEDGMENT_LEDGER_JSON,
    ACKNOWLEDGED,
    DEFERRED,
    NOTED,
    PENDING_OPERATOR_REVIEW,
    REJECTED,
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


DEFAULT_HUMAN_REVIEW_CLOSEOUT_GATE_DIR = Path("reports/human_review_closeout_gate")
HUMAN_REVIEW_CLOSEOUT_GATE_JSON = "human_review_closeout_gate.json"
HUMAN_REVIEW_CLOSEOUT_GATE_MARKDOWN = "human_review_closeout_gate.md"

CLOSED_FOR_RECORDS_ONLY = "CLOSED_FOR_RECORDS_ONLY"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"
CLOSEOUT_STATES = (
    CLOSED_FOR_RECORDS_ONLY,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_CLOSEOUT_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_CLOSEOUT_LABELS = tuple(
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
class HumanReviewCloseoutGateInput:
    closeout_id: str
    closeout_date: str
    generated_at_utc: str
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
        for field_name in ("closeout_id", "closeout_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"human review closeout gate requires {field_name}")
        _parse_iso_date("closeout_date", self.closeout_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
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
            _validate_closeout_path(path)


def build_default_human_review_closeout_gate_input(
    *,
    closeout_date: date | None = None,
    now: datetime | None = None,
) -> HumanReviewCloseoutGateInput:
    generated = now or datetime.now(tz=UTC)
    day = closeout_date or generated.date()
    return HumanReviewCloseoutGateInput(
        closeout_id=f"22A-HUMAN-REVIEW-CLOSEOUT-GATE-{day.isoformat()}",
        closeout_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_human_review_closeout_gate_payload(
    closeout_input: HumanReviewCloseoutGateInput,
) -> dict[str, Any]:
    closeout_input.validate()
    closeout_day = datetime.strptime(closeout_input.closeout_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(closeout_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }

    ledger_payload = source_payloads.get("operator_acknowledgment_ledger", {})
    queue_payload = source_payloads.get("human_review_queue", {})
    missing_artifacts = _missing_artifacts(source_artifacts, source_payloads)
    stale_artifacts = _stale_artifacts(source_artifacts, source_payloads, closeout_day, closeout_input.max_source_age_days)
    unresolved_review_items = _unresolved_review_items(ledger_payload, queue_payload)
    rejected_items = _ledger_status_items(ledger_payload, REJECTED)
    deferred_items = _ledger_status_items(ledger_payload, DEFERRED)
    unmatched_acknowledgments = _unmatched_acknowledgments(ledger_payload)
    blocked_workflows = _blocked_workflows(source_payloads)
    safety_findings = _safety_findings(source_payloads, closeout_input.safety_scanner_path)
    queue_status = _queue_status(closeout_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(closeout_input.safety_scanner_path)
    required_next_human_review_actions = _required_next_human_review_actions(
        unresolved_review_items=unresolved_review_items,
        rejected_items=rejected_items,
        deferred_items=deferred_items,
        unmatched_acknowledgments=unmatched_acknowledgments,
        blocked_workflows=blocked_workflows,
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    closeout_state = _closeout_state(
        source_artifacts=source_artifacts,
        source_payloads=source_payloads,
        unresolved_review_items=unresolved_review_items,
        rejected_items=rejected_items,
        deferred_items=deferred_items,
        unmatched_acknowledgments=unmatched_acknowledgments,
        blocked_workflows=blocked_workflows,
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "22A",
        "workflow": "Human Review Closeout Gate",
        "closeout_id": closeout_input.closeout_id,
        "closeout_date": closeout_input.closeout_date,
        "generated_at_utc": closeout_input.generated_at_utc,
        "closeout_state": closeout_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_CLOSEOUT_LABELS),
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "unresolved_review_item_count": len(unresolved_review_items),
            "rejected_item_count": len(rejected_items),
            "deferred_item_count": len(deferred_items),
            "unmatched_acknowledgment_count": len(unmatched_acknowledgments),
            "blocked_workflow_count": len(blocked_workflows),
            "non_baseline_blocked_workflow_count": len(_non_baseline_blocked_workflows(blocked_workflows)),
            "safety_finding_count": len(safety_findings),
            "required_next_human_review_action_count": len(required_next_human_review_actions),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *unresolved_review_items,
                    *rejected_items,
                    *deferred_items,
                    *unmatched_acknowledgments,
                    *blocked_workflows,
                    *safety_findings,
                    *required_next_human_review_actions,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "unresolved_review_items": unresolved_review_items,
        "rejected_items": rejected_items,
        "deferred_items": deferred_items,
        "unmatched_acknowledgments": unmatched_acknowledgments,
        "blocked_workflows": blocked_workflows,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "safety_findings": safety_findings,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "required_next_human_review_actions": required_next_human_review_actions,
    }
    _validate_json_value("human_review_closeout_gate_payload", payload)
    return _normalize_json_value(payload)


def write_human_review_closeout_gate(
    closeout_input: HumanReviewCloseoutGateInput,
    *,
    out_dir: Path = DEFAULT_HUMAN_REVIEW_CLOSEOUT_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_human_review_closeout_gate_payload(closeout_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / HUMAN_REVIEW_CLOSEOUT_GATE_JSON
    markdown_path = out_dir / HUMAN_REVIEW_CLOSEOUT_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_human_review_closeout_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_human_review_closeout_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("human_review_closeout_gate_payload", payload)
    lines = [
        "# 22A Human Review Closeout Gate",
        "",
        f"Closeout ID: {payload['closeout_id']}",
        f"Closeout Date: {payload['closeout_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Closeout State: {payload['closeout_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "Closeout records are not trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Unresolved review items", payload["summary"]["unresolved_review_item_count"]),
        _summary_line("Rejected items", payload["summary"]["rejected_item_count"]),
        _summary_line("Deferred items", payload["summary"]["deferred_item_count"]),
        _summary_line("Unmatched acknowledgments", payload["summary"]["unmatched_acknowledgment_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line(
            "Required next human-review actions",
            payload["summary"]["required_next_human_review_action_count"],
        ),
        "",
    ]
    lines.extend(_section("Source Artifacts", payload["source_artifacts"]))
    lines.extend(_section("Unresolved Review Items", payload["unresolved_review_items"]))
    lines.extend(_section("Rejected Items", payload["rejected_items"]))
    lines.extend(_section("Deferred Items", payload["deferred_items"]))
    lines.extend(_section("Unmatched Acknowledgments", payload["unmatched_acknowledgments"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Stale Artifacts", payload["stale_artifacts"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_section("Required Next Human-Review Actions", payload["required_next_human_review_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY closeout gate generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED actions remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(closeout_input: HumanReviewCloseoutGateInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("operator_acknowledgment_ledger", "21B Operator Acknowledgment Ledger", closeout_input.operator_acknowledgment_ledger_path),
        ("human_review_queue", "21A Human Review Queue", closeout_input.human_review_queue_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", closeout_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", closeout_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", closeout_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", closeout_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", closeout_input.release_bundle_path),
        ("operator_dashboard_snapshot", "17B Operator Dashboard Snapshot", closeout_input.operator_dashboard_snapshot_path),
        ("report_index", "Report Index", closeout_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", closeout_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", closeout_input.safety_scanner_path),
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
    source_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        {
            "artifact_id": artifact["artifact_id"],
            "workflow_id": f"missing_{artifact['artifact_id']}",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "path": artifact["path"],
            "summary": artifact["summary"],
            "source_artifact_id": "22a_source_artifacts",
        }
        for artifact in source_artifacts
        if artifact["status"] != "present"
    ]
    for item in _collect_payload_items(source_payloads, "missing_artifacts", "artifact_id", BLOCKED_BY_SAFETY_GATE):
        item.setdefault("workflow_id", f"missing_{item.get('artifact_id', 'artifact')}")
        items.append(item)
    return _dedupe_by_id(items, "workflow_id")


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
    closeout_day: date,
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
        age_days = (closeout_day - artifact_day).days
        if age_days > max_source_age_days:
            items.append(
                _stale_item(
                    artifact,
                    generated_date,
                    f"Source artifact is {age_days} days old; maximum allowed age is {max_source_age_days} days.",
                )
            )
    for item in _collect_payload_items(source_payloads, "stale_artifacts", "workflow_id", HUMAN_REVIEW_REQUIRED):
        item.setdefault("artifact_id", item.get("workflow_id", "stale_artifact"))
        items.append(item)
    for item in _collect_payload_items(source_payloads, "stale_reports", "workflow_id", HUMAN_REVIEW_REQUIRED):
        item.setdefault("artifact_id", item.get("workflow_id", "stale_artifact"))
        items.append(item)
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
        "source_artifact_id": "22a_source_artifacts",
    }
    _validate_json_value("stale_artifact", value)
    return _normalize_json_value(value)


def _unresolved_review_items(ledger_payload: dict[str, Any], queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = _items_from_payload(ledger_payload, "ledger_entries")
    unresolved = [item for item in entries if item.get("review_status") == PENDING_OPERATOR_REVIEW]
    if entries:
        return _dedupe_by_id([_closeout_item(item, "review_item_id") for item in unresolved], "review_item_id")
    queue_items = []
    for key in (
        "required_human_review_items",
        "missing_artifacts",
        "stale_artifacts",
        "skipped_steps",
        "blocked_workflows",
        "safety_findings",
        "retention_review_items",
        "next_operator_actions",
    ):
        queue_items.extend(_items_from_payload(queue_payload, key))
    return _dedupe_by_id([_queue_unresolved_item(item) for item in queue_items], "review_item_id")


def _ledger_status_items(ledger_payload: dict[str, Any], status: str) -> list[dict[str, Any]]:
    items = [
        _closeout_item(item, "review_item_id")
        for item in _items_from_payload(ledger_payload, "ledger_entries")
        if item.get("review_status") == status
    ]
    return _dedupe_by_id(items, "review_item_id")


def _unmatched_acknowledgments(ledger_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = [_closeout_item(item, "review_item_id") for item in _items_from_payload(ledger_payload, "unmatched_acknowledgments")]
    return _dedupe_by_id(items, "review_item_id")


def _blocked_workflows(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = [
        {
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Workflow remains blocked by 22A safety boundary.",
            "source_artifact_id": "22a_safety_boundary",
        }
        for workflow_id in sorted(BASELINE_BLOCKED_WORKFLOWS)
    ]
    items = [*baseline]
    items.extend(_collect_payload_items(source_payloads, "blocked_workflows", "workflow_id", BLOCKED_BY_SAFETY_GATE))
    items.extend(_collect_payload_items(source_payloads, "blocked_workflow_references", "workflow_id", BLOCKED_BY_SAFETY_GATE))
    return _dedupe_by_id(items, "workflow_id")


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_path: Path,
) -> list[dict[str, Any]]:
    items = []
    for key in ("safety_findings", "failed_safety_findings"):
        items.extend(_collect_payload_items(source_payloads, key, "finding_id", BLOCKED_BY_SAFETY_GATE))
    scanner = _safety_scanner_status(safety_scanner_path)
    if scanner.get("passed") is False or scanner.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": scanner.get("summary", "Safety scanner status requires review."),
                "source_artifact_id": "safety_scanner_status",
            }
        )
    for finding in scanner.get("findings", []):
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
        "summary": "Master plan queue read for 22A closeout context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": _next_phase(items),
        "items": items,
    }
    _validate_json_value("queue_status", value)
    return _normalize_json_value(value)


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
        if item.get("phase") == "22A":
            return item
    return items[0] if items else None


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to 22A.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 22A."),
        "path": path.as_posix(),
        "finding_count": finding_count,
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _required_next_human_review_actions(
    *,
    unresolved_review_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    unmatched_acknowledgments: list[dict[str, Any]],
    blocked_workflows: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [
        {
            "action_id": "22A-REVIEW-CLOSEOUT-GATE",
            "workflow_id": "review_closeout_gate",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review this 22A closeout gate as a records-only artifact.",
        }
    ]
    if unresolved_review_items:
        actions.append(_action("22A-RESOLVE-UNRESOLVED-REVIEW-ITEMS", "Resolve pending review items in the operator acknowledgment ledger."))
    if rejected_items:
        actions.append(_action("22A-ADDRESS-REJECTED-ITEMS", "Address rejected review items before closing the cycle."))
    if deferred_items:
        actions.append(_action("22A-SCHEDULE-DEFERRED-ITEMS", "Schedule deferred review items for the next human-review cycle."))
    if unmatched_acknowledgments:
        actions.append(_action("22A-RECONCILE-UNMATCHED-ACKNOWLEDGMENTS", "Reconcile acknowledgments that do not match 21A review items."))
    if missing_artifacts:
        actions.append(_action("22A-RESOLVE-MISSING-ARTIFACTS", "Regenerate or explicitly accept missing source artifacts."))
    if stale_artifacts:
        actions.append(_action("22A-REFRESH-STALE-ARTIFACTS", "Refresh stale artifacts or record human acceptance."))
    if _non_baseline_blocked_workflows(blocked_workflows):
        actions.append(_action("22A-REVIEW-BLOCKED-WORKFLOWS", "Review non-baseline blocked workflows while keeping safety blocks active."))
    if safety_findings or safety_scanner_status.get("passed") is False:
        actions.append(_action("22A-RESOLVE-SAFETY-FINDINGS", "Resolve safety findings before any future workflow."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(_action("22A-REVIEW-QUEUE-STATUS", "Review missing or invalid master plan queue status."))
    return _dedupe_by_id(actions, "action_id")


def _action(action_id: str, summary: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "open_review_item",
        "summary": summary,
    }


def _closeout_state(
    *,
    source_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    unmatched_acknowledgments: list[dict[str, Any]],
    blocked_workflows: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> str:
    ledger = source_payloads.get("operator_acknowledgment_ledger", {})
    queue = source_payloads.get("human_review_queue", {})
    if (
        missing_artifacts
        or safety_findings
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
        or ledger.get("ledger_state") == BLOCKED_BY_SAFETY_GATE
        or queue.get("queue_state") == "BLOCKED_HUMAN_REVIEW_QUEUE"
        or any(item["status"] != "present" for item in source_artifacts)
    ):
        return BLOCKED_BY_SAFETY_GATE
    if (
        unresolved_review_items
        or rejected_items
        or deferred_items
        or unmatched_acknowledgments
        or stale_artifacts
        or _non_baseline_blocked_workflows(blocked_workflows)
        or ledger.get("ledger_state") == NEEDS_OPERATOR_REVIEW
    ):
        return NEEDS_OPERATOR_REVIEW
    return CLOSED_FOR_RECORDS_ONLY


def _non_baseline_blocked_workflows(blocked_workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in blocked_workflows
        if str(item.get("workflow_id")) not in BASELINE_BLOCKED_WORKFLOWS
        and not str(item.get("workflow_id", "")).startswith("missing_")
    ]


def _queue_unresolved_item(item: dict[str, Any]) -> dict[str, Any]:
    value = dict(item)
    value.setdefault(
        "review_item_id",
        value.get("review_item_id")
        or value.get("action_id")
        or value.get("workflow_id")
        or value.get("artifact_id")
        or value.get("step_id")
        or value.get("finding_id")
        or "review_item",
    )
    value.setdefault("review_status", PENDING_OPERATOR_REVIEW)
    value.setdefault("label", HUMAN_REVIEW_REQUIRED)
    value.setdefault("status", "open_review_item")
    value.setdefault("summary", "Review item remains unresolved because 21B ledger entries were unavailable.")
    _validate_json_value("queue_unresolved_item", value)
    return _normalize_json_value(value)


def _closeout_item(item: dict[str, Any], id_key: str) -> dict[str, Any]:
    value = dict(item)
    value.setdefault(id_key, value.get("workflow_id") or value.get("action_id") or value.get("artifact_id") or "item")
    value.setdefault("label", HUMAN_REVIEW_REQUIRED)
    value.setdefault("summary", "Closeout item recorded.")
    _validate_json_value("closeout_item", value)
    return _normalize_json_value(value)


def _collect_payload_items(
    source_payloads: dict[str, dict[str, Any]],
    key: str,
    id_key: str,
    default_label: str,
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, key):
            value = dict(item)
            value.setdefault(id_key, value.get("workflow_id") or value.get("artifact_id") or "item")
            value.setdefault("workflow_id", value.get(id_key))
            value.setdefault("label", default_label)
            value.setdefault("status", "recorded")
            value.setdefault("summary", "Recorded by source artifact.")
            value["source_artifact_id"] = artifact_id
            _validate_json_value(key, value)
            items.append(_normalize_json_value(value))
    return _dedupe_by_id(items, id_key)


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


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "closeout_records_only": True,
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


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_closeout_path(path)
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
            item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("step_id")
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
            item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("step_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_closeout_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("human review closeout gate cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("human review closeout gate cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("human review closeout gate paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("human review closeout gate paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_CLOSEOUT_LABELS:
            raise ValueError(f"unsafe human review closeout gate label: {label}")
        review_status = value.get("review_status")
        if review_status is not None and review_status not in {
            ACKNOWLEDGED,
            REJECTED,
            DEFERRED,
            NOTED,
            PENDING_OPERATOR_REVIEW,
        }:
            raise ValueError(f"invalid human review closeout review_status: {review_status}")
        closeout_state = value.get("closeout_state")
        if closeout_state is not None and closeout_state not in CLOSEOUT_STATES:
            raise ValueError(f"invalid human review closeout state: {closeout_state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"human review closeout gate cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("human review closeout gate cannot allow automatic deletion")
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
        if value in DISALLOWED_CLOSEOUT_LABELS:
            raise ValueError(f"disallowed human review closeout gate text: {value}")
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
