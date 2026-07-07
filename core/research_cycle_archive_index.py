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
from core.operator_dashboard_snapshot import (
    DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR,
    OPERATOR_DASHBOARD_SNAPSHOT_JSON,
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
    KEEP,
    RESEARCH_ARTIFACT_RETENTION_POLICY_JSON,
    REVIEW,
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


DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR = Path("reports/research_cycle_archive_index")
RESEARCH_CYCLE_ARCHIVE_INDEX_JSON = "research_cycle_archive_index.json"
RESEARCH_CYCLE_ARCHIVE_INDEX_MARKDOWN = "research_cycle_archive_index.md"

ARCHIVE_INDEX_COMPLETE = "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY"
ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW = "ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW"
ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE = "ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE"

SAFE_ARCHIVE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
ARCHIVE_INDEX_STATES = (
    ARCHIVE_INDEX_COMPLETE,
    ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW,
    ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE,
)
RETENTION_ACTIONS = (KEEP, REVIEW, ARCHIVE_CANDIDATE, BLOCKED_DELETE)
DISALLOWED_ARCHIVE_LABELS = tuple(
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
    "automatic_delete_allowed",
    "automatic_file_deletion_enabled",
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
    "snapshot_date",
    "index_date",
    "catalog_date",
    "report_date",
)


@dataclass(frozen=True)
class ResearchCycleArchiveIndexInput:
    archive_index_id: str
    archive_index_date: str
    generated_at_utc: str
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
    operator_dashboard_snapshot_path: Path = (
        DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR / OPERATOR_DASHBOARD_SNAPSHOT_JSON
    )
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")

    def validate(self) -> None:
        for field_name in ("archive_index_id", "archive_index_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research cycle archive index requires {field_name}")
        _parse_iso_date("archive_index_date", self.archive_index_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        for path in (
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
            self.operator_dashboard_snapshot_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
        ):
            _validate_archive_path(path)


def build_default_research_cycle_archive_index_input(
    *,
    archive_index_date: date | None = None,
    now: datetime | None = None,
) -> ResearchCycleArchiveIndexInput:
    generated = now or datetime.now(tz=UTC)
    day = archive_index_date or generated.date()
    return ResearchCycleArchiveIndexInput(
        archive_index_id=f"23B-RESEARCH-CYCLE-ARCHIVE-INDEX-{day.isoformat()}",
        archive_index_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_cycle_archive_index_payload(
    archive_input: ResearchCycleArchiveIndexInput,
) -> dict[str, Any]:
    archive_input.validate()
    source_artifacts = _source_artifacts(archive_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    retention_lookup = _retention_lookup(source_payloads.get("retention_policy", {}))
    indexed_artifacts = [
        _archive_artifact_entry(item, retention_lookup.get(item["artifact_id"]))
        for item in source_artifacts
    ]
    queue_status = _queue_status(archive_input.queue_status_path)
    dry_run_archive_manifest = [
        _dry_run_archive_item(item)
        for item in indexed_artifacts
        if item["archive_eligible"] or item["blocked_delete"]
    ]
    human_review_notes = _human_review_notes(source_payloads, indexed_artifacts, queue_status)
    blocked_workflows = _blocked_workflows()
    archive_index_state = _archive_index_state(indexed_artifacts, queue_status)

    payload = {
        "phase": "23B",
        "workflow": "Research Cycle Archive Index",
        "archive_index_id": archive_input.archive_index_id,
        "archive_index_date": archive_input.archive_index_date,
        "generated_at_utc": archive_input.generated_at_utc,
        "archive_index_state": archive_index_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_ARCHIVE_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in indexed_artifacts if item["artifact_status"] == "present"]),
            "missing_source_artifact_count": len([item for item in indexed_artifacts if item["artifact_status"] != "present"]),
            "archive_eligible_count": len([item for item in indexed_artifacts if item["archive_eligible"]]),
            "blocked_delete_count": len([item for item in indexed_artifacts if item["blocked_delete"]]),
            "dry_run_archive_manifest_count": len(dry_run_archive_manifest),
            "human_review_note_count": len(human_review_notes),
            "queue_status": queue_status["status"],
            "retention_action_counts": _count_by(indexed_artifacts, "retention_action"),
            "label_counts": _count_by([*indexed_artifacts, queue_status, *blocked_workflows], "label"),
        },
        "indexed_artifacts": indexed_artifacts,
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "dry_run_archive_manifest": dry_run_archive_manifest,
        "queue_status": queue_status,
        "human_review_notes": human_review_notes,
        "blocked_workflows": blocked_workflows,
        "final_archive_summary": _final_archive_summary(
            archive_index_state=archive_index_state,
            indexed_artifacts=indexed_artifacts,
            dry_run_archive_manifest=dry_run_archive_manifest,
            human_review_notes=human_review_notes,
        ),
    }
    _validate_json_value("research_cycle_archive_index_payload", payload)
    return _normalize_json_value(payload)


def write_research_cycle_archive_index(
    archive_input: ResearchCycleArchiveIndexInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR,
) -> tuple[Path, Path]:
    payload = build_research_cycle_archive_index_payload(archive_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_CYCLE_ARCHIVE_INDEX_JSON
    markdown_path = out_dir / RESEARCH_CYCLE_ARCHIVE_INDEX_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_cycle_archive_index_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_cycle_archive_index_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_cycle_archive_index_payload", payload)
    lines = [
        "# 23B Research Cycle Archive Index",
        "",
        f"Archive Index ID: {payload['archive_index_id']}",
        f"Archive Index Date: {payload['archive_index_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Archive Index State: {payload['archive_index_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Archive index generation is read-only and dry-run only.",
        "No artifacts are deleted, moved, renamed, compressed, or mutated.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Archive Summary",
        "",
        payload["final_archive_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing source artifacts", payload["summary"]["missing_source_artifact_count"]),
        _summary_line("Archive eligible artifacts", payload["summary"]["archive_eligible_count"]),
        _summary_line("Blocked-delete artifacts", payload["summary"]["blocked_delete_count"]),
        _summary_line("Dry-run archive manifest items", payload["summary"]["dry_run_archive_manifest_count"]),
        _summary_line("Human-review notes", payload["summary"]["human_review_note_count"]),
        "",
    ]
    lines.extend(_section("Indexed Artifacts", payload["indexed_artifacts"]))
    lines.extend(_section("Dry-Run Archive Manifest", payload["dry_run_archive_manifest"]))
    lines.extend(_section("Human-Review Notes", payload["human_review_notes"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY archive index generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are indexed, not executed.",
            "- HUMAN_REVIEW_REQUIRED notes remain review records.",
            "- BLOCKED_BY_SAFETY_GATE items remain blocked.",
            "- Dry-run archive manifest only.",
            "- No delete, move, rename, compression, mutation, broker routing, broker calls, live trading, or order execution.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(archive_input: ResearchCycleArchiveIndexInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("operations_console", "23A Research Operations Console", archive_input.operations_console_path),
        ("operator_signoff_packet", "22B Operator Signoff Packet", archive_input.operator_signoff_packet_path),
        ("closeout_gate", "22A Human Review Closeout Gate", archive_input.closeout_gate_path),
        ("operator_acknowledgment_ledger", "21B Operator Acknowledgment Ledger", archive_input.operator_acknowledgment_ledger_path),
        ("human_review_queue", "21A Human Review Queue", archive_input.human_review_queue_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", archive_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", archive_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", archive_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", archive_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", archive_input.release_bundle_path),
        ("operator_dashboard_snapshot", "Dashboard Snapshot", archive_input.operator_dashboard_snapshot_path),
        ("report_index", "Report Index", archive_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", archive_input.safe_workflow_catalog_path),
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


def _archive_artifact_entry(source: dict[str, Any], retention: dict[str, Any] | None) -> dict[str, Any]:
    retention_action = _retention_action(source, retention)
    blocked_delete = (
        source["status"] != "present"
        or source.get("label") == BLOCKED_BY_SAFETY_GATE
        or retention_action == BLOCKED_DELETE
    )
    archive_eligible = source["status"] == "present" and retention_action == ARCHIVE_CANDIDATE and not blocked_delete
    value = {
        "artifact_id": source["artifact_id"],
        "artifact_name": source["name"],
        "source_artifact_path": source["path"],
        "artifact_status": source["status"],
        "label": source.get("label", HUMAN_REVIEW_REQUIRED),
        "generated_date": source.get("generated_date"),
        "generated_at_utc": source.get("generated_at_utc"),
        "phase": source.get("phase"),
        "workflow": source.get("workflow"),
        "signoff_state": _signoff_state(source),
        "retention_action": retention_action,
        "retention_reasons": retention.get("retention_reasons", []) if retention else [],
        "archive_eligible": archive_eligible,
        "blocked_delete": blocked_delete,
        "dry_run_only": True,
        "automatic_delete_allowed": False,
        "human_review_notes": _artifact_human_review_notes(source),
        "summary": source.get("summary", "Archive index item recorded."),
    }
    _validate_json_value("archive_artifact_entry", value)
    return _normalize_json_value(value)


def _retention_lookup(retention_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for key in ("artifacts", "dry_run_manifest"):
        for item in _items_from_payload(retention_payload, key):
            artifact_id = item.get("artifact_id")
            if isinstance(artifact_id, str) and artifact_id:
                items[artifact_id] = item
    return items


def _retention_action(source: dict[str, Any], retention: dict[str, Any] | None) -> str:
    if source["status"] != "present":
        return BLOCKED_DELETE
    if retention and retention.get("retention_action") in RETENTION_ACTIONS:
        return str(retention["retention_action"])
    if source.get("label") == BLOCKED_BY_SAFETY_GATE:
        return BLOCKED_DELETE
    return KEEP


def _dry_run_archive_item(item: dict[str, Any]) -> dict[str, Any]:
    value = {
        "artifact_id": item["artifact_id"],
        "artifact_name": item["artifact_name"],
        "source_artifact_path": item["source_artifact_path"],
        "label": item["label"],
        "artifact_status": item["artifact_status"],
        "retention_action": item["retention_action"],
        "archive_eligible": item["archive_eligible"],
        "blocked_delete": item["blocked_delete"],
        "retention_reasons": item["retention_reasons"],
        "dry_run_only": True,
        "automatic_delete_allowed": False,
        "summary": "Dry-run archive manifest item; no artifact mutation is allowed.",
    }
    _validate_json_value("dry_run_archive_item", value)
    return _normalize_json_value(value)


def _human_review_notes(
    source_payloads: dict[str, dict[str, Any]],
    indexed_artifacts: list[dict[str, Any]],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    notes = [
        {
            "note_id": "23B-REVIEW-ARCHIVE-INDEX",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review 23B archive index and dry-run archive manifest before any future archive operation.",
            "source_artifact_id": "archive_index",
        }
    ]
    for artifact in indexed_artifacts:
        if artifact["archive_eligible"]:
            notes.append(_note(f"23B-REVIEW-ARCHIVE-{artifact['artifact_id']}", "archive_candidate", artifact["artifact_id"]))
        if artifact["blocked_delete"]:
            notes.append(_note(f"23B-BLOCKED-DELETE-{artifact['artifact_id']}", "blocked_delete", artifact["artifact_id"], BLOCKED_BY_SAFETY_GATE))
    for artifact_id, payload in source_payloads.items():
        for key in ("human_review_notes", "required_operator_actions", "required_next_human_review_actions", "next_operator_actions"):
            for item in _items_from_payload(payload, key):
                note_id = item.get("note_id") or item.get("action_id") or item.get("review_item_id") or item.get("workflow_id")
                notes.append(
                    {
                        "note_id": f"{artifact_id}_{note_id or key}",
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status") or item.get("review_status") or "recorded",
                        "summary": item.get("summary", "Human-review note recorded by source artifact."),
                        "source_artifact_id": artifact_id,
                    }
                )
    if queue_status.get("next_phase"):
        notes.append(
            {
                "note_id": "23B-QUEUE-STATUS",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": queue_status["status"],
                "summary": "Master plan queue status was read for archive index context only.",
                "source_artifact_id": "queue_status",
            }
        )
    return _dedupe_by_id(notes, "note_id")


def _note(note_id: str, status: str, artifact_id: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "note_id": note_id,
        "label": label,
        "status": status,
        "summary": f"{artifact_id} requires human review in the dry-run archive index.",
        "source_artifact_id": artifact_id,
    }


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
        "summary": "Master plan queue read for 23B archive index context only.",
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
        if item.get("phase") == "23B":
            return item
    return items[0] if items else None


def _archive_index_state(indexed_artifacts: list[dict[str, Any]], queue_status: dict[str, Any]) -> str:
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE or any(
        item["artifact_status"] != "present" for item in indexed_artifacts
    ):
        return ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE
    if any(item["archive_eligible"] or item["blocked_delete"] or item["retention_action"] == REVIEW for item in indexed_artifacts):
        return ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW
    return ARCHIVE_INDEX_COMPLETE


def _signoff_state(source: dict[str, Any]) -> str | None:
    payload = source.get("payload", {})
    if not isinstance(payload, dict):
        return None
    for key in ("signoff_state", "closeout_state", "ledger_state", "queue_state", "console_state"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _artifact_human_review_notes(source: dict[str, Any]) -> list[str]:
    notes = []
    payload = source.get("payload", {})
    if isinstance(payload, dict):
        summary = payload.get("final_console_summary") or payload.get("final_signoff_summary")
        if isinstance(summary, str) and summary:
            notes.append(summary)
    if source["status"] != "present":
        notes.append(source["summary"])
    return notes


def _blocked_workflows() -> list[dict[str, Any]]:
    return [
        _blocked("artifact_deletion", "23B may not delete artifacts."),
        _blocked("artifact_move_rename_or_compression", "23B may not move, rename, or compress artifacts."),
        _blocked("artifact_mutation", "23B may only read source artifacts and write index reports."),
        _blocked("live_trading", "Live trading remains disabled."),
        _blocked("broker_order_routing", "Broker routing is outside the 23B archive index."),
        _blocked("broker_order_call", "Broker order calls are not allowed."),
        _blocked("order_execution", "Order execution is not part of this workflow."),
        _blocked("secret_or_credential_access", "Secrets and credential files are not required and must not be opened."),
    ]


def _blocked(workflow_id: str, summary: str) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "label": BLOCKED_BY_SAFETY_GATE,
        "status": "blocked",
        "summary": summary,
    }


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "archive_index_read_only": True,
        "dry_run_only": True,
        "artifact_delete_performed": False,
        "artifact_move_performed": False,
        "artifact_rename_performed": False,
        "artifact_compression_performed": False,
        "artifact_mutation_performed": False,
        "trade_instructions_created": False,
        "broker_actions_created": False,
        "execution_permissions_created": False,
        "automatic_action_enabled": False,
        "automatic_delete_allowed": False,
        "automatic_file_deletion_enabled": False,
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


def _final_archive_summary(
    *,
    archive_index_state: str,
    indexed_artifacts: list[dict[str, Any]],
    dry_run_archive_manifest: list[dict[str, Any]],
    human_review_notes: list[dict[str, Any]],
) -> str:
    return (
        f"Research-cycle archive index state is {archive_index_state}. "
        f"Indexed artifacts: {len(indexed_artifacts)}. "
        f"Archive eligible artifacts: {len([item for item in indexed_artifacts if item['archive_eligible']])}. "
        f"Blocked-delete artifacts: {len([item for item in indexed_artifacts if item['blocked_delete']])}. "
        f"Dry-run archive manifest items: {len(dry_run_archive_manifest)}. "
        f"Human-review notes: {len(human_review_notes)}. "
        "Safety boundary confirmed: archive index is read-only and does not delete, move, rename, compress, mutate, enable live trading, route broker orders, call brokers, or execute orders. "
        "LIVE TRADING: DISABLED."
    )


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
    _validate_archive_path(path)
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
            item.get("artifact_id")
            or item.get("note_id")
            or item.get("workflow_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("retention_action") or item.get("artifact_status") or item.get("status") or "recorded"
        summary = item.get("summary") or item.get("artifact_name") or "Recorded."
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
            item.get("artifact_id")
            or item.get("note_id")
            or item.get("workflow_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_archive_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research cycle archive index cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research cycle archive index cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research cycle archive index paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research cycle archive index paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_ARCHIVE_LABELS:
            raise ValueError(f"unsafe research cycle archive index label: {label}")
        archive_index_state = value.get("archive_index_state")
        if archive_index_state is not None and archive_index_state not in ARCHIVE_INDEX_STATES:
            raise ValueError(f"invalid research cycle archive index state: {archive_index_state}")
        retention_action = value.get("retention_action")
        if retention_action is not None and retention_action not in RETENTION_ACTIONS:
            raise ValueError(f"invalid research cycle archive index retention_action: {retention_action}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research cycle archive index cannot set {unsafe_field}")
        for mutation_field in (
            "artifact_delete_performed",
            "artifact_move_performed",
            "artifact_rename_performed",
            "artifact_compression_performed",
            "artifact_mutation_performed",
        ):
            if value.get(mutation_field) is True:
                raise ValueError(f"research cycle archive index cannot set {mutation_field}")
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
        if value in DISALLOWED_ARCHIVE_LABELS:
            raise ValueError(f"disallowed research cycle archive index text: {value}")
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
