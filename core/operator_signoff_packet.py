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


DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR = Path("reports/operator_signoff_packet")
OPERATOR_SIGNOFF_PACKET_JSON = "operator_signoff_packet.json"
OPERATOR_SIGNOFF_PACKET_MARKDOWN = "operator_signoff_packet.md"

SIGNOFF_PACKET_COMPLETE = "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY"
SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW = "SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW"
SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE = "SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE"

SAFE_SIGNOFF_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SIGNOFF_STATES = (
    SIGNOFF_PACKET_COMPLETE,
    SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW,
    SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_SIGNOFF_LABELS = tuple(
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
    "signoff_date",
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
class OperatorSignoffPacketInput:
    signoff_id: str
    signoff_date: str
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
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("signoff_id", "signoff_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"operator signoff packet requires {field_name}")
        _parse_iso_date("signoff_date", self.signoff_date)
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
        ):
            _validate_signoff_path(path)


def build_default_operator_signoff_packet_input(
    *,
    signoff_date: date | None = None,
    now: datetime | None = None,
) -> OperatorSignoffPacketInput:
    generated = now or datetime.now(tz=UTC)
    day = signoff_date or generated.date()
    return OperatorSignoffPacketInput(
        signoff_id=f"22B-OPERATOR-SIGNOFF-PACKET-{day.isoformat()}",
        signoff_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_operator_signoff_packet_payload(
    signoff_input: OperatorSignoffPacketInput,
) -> dict[str, Any]:
    signoff_input.validate()
    signoff_day = datetime.strptime(signoff_input.signoff_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(signoff_input)
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
        signoff_day,
        signoff_input.max_source_age_days,
    )
    completed_items = _completed_items(closeout_payload, ledger_payload, source_artifacts)
    open_items = _open_items(closeout_payload, ledger_payload, queue_payload)
    blocked_items = _blocked_items(closeout_payload, source_payloads)
    rejected_items = _status_items(closeout_payload, ledger_payload, REJECTED, "rejected_items")
    deferred_items = _status_items(closeout_payload, ledger_payload, DEFERRED, "deferred_items")
    retention_items = _retention_items(retention_payload)
    queue_status = _queue_status(signoff_input.queue_status_path)
    safety_boundary_confirmation = _safety_boundary_confirmation()
    signoff_state = _signoff_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        open_items=open_items,
        blocked_items=blocked_items,
        rejected_items=rejected_items,
        deferred_items=deferred_items,
        queue_status=queue_status,
        closeout_payload=closeout_payload,
    )

    payload = {
        "phase": "22B",
        "workflow": "Operator Signoff Packet",
        "signoff_id": signoff_input.signoff_id,
        "signoff_date": signoff_input.signoff_date,
        "generated_at_utc": signoff_input.generated_at_utc,
        "signoff_state": signoff_state,
        "safety_boundary": safety_boundary_confirmation,
        "required_labels": [*SAFE_SIGNOFF_LABELS, "LIVE TRADING: DISABLED"],
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
            "queue_status": queue_status["status"],
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
                    queue_status,
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
        "final_signoff_summary": _final_signoff_summary(
            signoff_state=signoff_state,
            completed_items=completed_items,
            open_items=open_items,
            blocked_items=blocked_items,
            rejected_items=rejected_items,
            deferred_items=deferred_items,
            missing_artifacts=missing_artifacts,
            stale_artifacts=stale_artifacts,
            retention_items=retention_items,
        ),
    }
    _validate_json_value("operator_signoff_packet_payload", payload)
    return _normalize_json_value(payload)


def write_operator_signoff_packet(
    signoff_input: OperatorSignoffPacketInput,
    *,
    out_dir: Path = DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR,
) -> tuple[Path, Path]:
    payload = build_operator_signoff_packet_payload(signoff_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / OPERATOR_SIGNOFF_PACKET_JSON
    markdown_path = out_dir / OPERATOR_SIGNOFF_PACKET_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_operator_signoff_packet_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_operator_signoff_packet_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("operator_signoff_packet_payload", payload)
    lines = [
        "# 22B Operator Signoff Packet",
        "",
        f"Signoff ID: {payload['signoff_id']}",
        f"Signoff Date: {payload['signoff_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Signoff State: {payload['signoff_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Operator signoff packets are records-only and do not enable live trading, broker routing, broker calls, order execution, or automatic actions.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Research-Cycle Signoff Summary",
        "",
        payload["final_signoff_summary"],
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
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(
        [
            "## Safety Boundary Confirmation",
            "",
            "- RESEARCH_ONLY signoff packet generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "- Records-only packet; no live trading, broker routing, broker calls, order execution, or automatic actions are enabled.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(signoff_input: OperatorSignoffPacketInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("closeout_gate", "22A Human Review Closeout Gate", signoff_input.closeout_gate_path),
        ("operator_acknowledgment_ledger", "21B Operator Acknowledgment Ledger", signoff_input.operator_acknowledgment_ledger_path),
        ("human_review_queue", "21A Human Review Queue", signoff_input.human_review_queue_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", signoff_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", signoff_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", signoff_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", signoff_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", signoff_input.release_bundle_path),
        ("operator_dashboard_snapshot", "Dashboard Snapshot", signoff_input.operator_dashboard_snapshot_path),
        ("report_index", "Report Index", signoff_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", signoff_input.safe_workflow_catalog_path),
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
            "source_artifact_id": "22b_source_artifacts",
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
    signoff_day: date,
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
        age_days = (signoff_day - artifact_day).days
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
        "source_artifact_id": "22b_source_artifacts",
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
            "source_artifact_id": "22b_source_artifacts",
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
                "summary": "22A closeout gate was included in the 22B signoff packet.",
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
            "summary": "Workflow remains blocked by 22B records-only safety boundary.",
            "source_artifact_id": "22b_safety_boundary",
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
        "summary": "Master plan queue read for 22B operator signoff context only.",
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
        if item.get("phase") == "22B":
            return item
    return items[0] if items else None


def _signoff_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    closeout_payload: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or closeout_payload.get("closeout_state") == BLOCKED_BY_SAFETY_GATE
        or _non_baseline_blocked_items(blocked_items)
    ):
        return SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE
    if open_items or stale_artifacts or rejected_items or deferred_items:
        return SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW
    return SIGNOFF_PACKET_COMPLETE


def _final_signoff_summary(
    *,
    signoff_state: str,
    completed_items: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    deferred_items: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    retention_items: list[dict[str, Any]],
) -> str:
    return (
        f"Research-cycle signoff state is {signoff_state}. "
        f"Completed items: {len(completed_items)}. "
        f"Open items: {len(open_items)}. "
        f"Blocked items: {len(blocked_items)}. "
        f"Rejected items: {len(rejected_items)}. "
        f"Deferred items: {len(deferred_items)}. "
        f"Missing artifacts: {len(missing_artifacts)}. "
        f"Stale artifacts: {len(stale_artifacts)}. "
        f"Retention items: {len(retention_items)}. "
        "Safety boundary confirmed: signoff is records-only and does not enable live trading, broker routing, broker calls, order execution, or automatic actions. "
        "LIVE TRADING: DISABLED."
    )


def _safety_boundary_confirmation() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "signoff_records_only": True,
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
    value.setdefault("summary", "Signoff packet item recorded.")
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
    _validate_signoff_path(path)
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


def _validate_signoff_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("operator signoff packet cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("operator signoff packet cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("operator signoff packet paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("operator signoff packet paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_SIGNOFF_LABELS:
            raise ValueError(f"unsafe operator signoff packet label: {label}")
        signoff_state = value.get("signoff_state")
        if signoff_state is not None and signoff_state not in SIGNOFF_STATES:
            raise ValueError(f"invalid operator signoff packet state: {signoff_state}")
        review_status = value.get("review_status")
        if review_status is not None and review_status not in {
            ACKNOWLEDGED,
            REJECTED,
            DEFERRED,
            NOTED,
            PENDING_OPERATOR_REVIEW,
        }:
            raise ValueError(f"invalid operator signoff packet review_status: {review_status}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"operator signoff packet cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("operator signoff packet cannot allow automatic deletion")
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
        if value in DISALLOWED_SIGNOFF_LABELS:
            raise ValueError(f"disallowed operator signoff packet text: {value}")
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
