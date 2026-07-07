from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.research_cycle_runner import (
    DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
    RESEARCH_CYCLE_MANIFEST_JSON,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR = Path("reports/research_cycle_audit_summary")
RESEARCH_CYCLE_AUDIT_SUMMARY_JSON = "research_cycle_audit_summary.json"
RESEARCH_CYCLE_AUDIT_SUMMARY_MARKDOWN = "research_cycle_audit_summary.md"

SAFE_AUDIT_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_AUDIT_LABELS = tuple(
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
class ResearchCycleAuditSummaryInput:
    audit_id: str
    audit_date: str
    generated_at_utc: str
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON
    queue_path: Path = Path("config/jarvis_master_plan_queue.json")

    def validate(self) -> None:
        for field_name in ("audit_id", "audit_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research cycle audit summary requires {field_name}")
        _parse_iso_date("audit_date", self.audit_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        for path in (self.manifest_path, self.queue_path):
            _validate_audit_path(path)


def build_default_research_cycle_audit_summary_input(
    *,
    audit_date: date | None = None,
    now: datetime | None = None,
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON,
    queue_path: Path = Path("config/jarvis_master_plan_queue.json"),
) -> ResearchCycleAuditSummaryInput:
    generated = now or datetime.now(tz=UTC)
    day = audit_date or generated.date()
    return ResearchCycleAuditSummaryInput(
        audit_id=f"19B-RESEARCH-CYCLE-AUDIT-SUMMARY-{day.isoformat()}",
        audit_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        manifest_path=manifest_path,
        queue_path=queue_path,
    )


def build_research_cycle_audit_summary_payload(
    audit_input: ResearchCycleAuditSummaryInput,
) -> dict[str, Any]:
    audit_input.validate()
    manifest = _manifest_status(audit_input.manifest_path)
    generated_reports = _generated_reports(manifest["payload"])
    missing_artifacts = _manifest_items(manifest["payload"], "missing_artifacts")
    skipped_steps = _manifest_items(manifest["payload"], "skipped_steps")
    safety_scanner_status = _safety_scanner_status(manifest["payload"])
    release_bundle_status = _artifact_payload_status(
        "research_release_bundle",
        "Research Release Bundle",
        _report_path(generated_reports, "research_release_bundle"),
    )
    dashboard_status = _artifact_payload_status(
        "operator_dashboard_snapshot",
        "Operator Dashboard Snapshot",
        _report_path(generated_reports, "operator_dashboard_snapshot"),
    )
    queue_status = _queue_status(audit_input.queue_path, release_bundle_status)
    human_review_notes = _human_review_notes(
        manifest["payload"],
        dashboard_status,
        release_bundle_status,
    )
    allowed_workflows = _allowed_human_review_workflows(
        manifest["payload"],
        dashboard_status,
        release_bundle_status,
        human_review_notes,
    )
    blocked_workflows = _blocked_workflows(
        _without_payload(manifest),
        manifest["payload"],
        missing_artifacts,
        safety_scanner_status,
        dashboard_status,
        release_bundle_status,
        queue_status,
    )

    payload = {
        "phase": "19B",
        "workflow": "Research Cycle Audit Summary",
        "audit_id": audit_input.audit_id,
        "audit_date": audit_input.audit_date,
        "generated_at_utc": audit_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_AUDIT_LABELS),
        "cycle_manifest_status": _without_payload(manifest),
        "summary": {
            "generated_report_count": len(generated_reports),
            "missing_artifact_count": len(missing_artifacts),
            "skipped_step_count": len(skipped_steps),
            "blocked_workflow_count": len(blocked_workflows),
            "allowed_human_review_workflow_count": len(allowed_workflows),
            "human_review_note_count": len(human_review_notes),
            "safety_scanner_status": safety_scanner_status["status"],
            "safety_scanner_finding_count": safety_scanner_status["finding_count"],
            "release_bundle_status": release_bundle_status["status"],
            "dashboard_status": dashboard_status["status"],
            "queue_status": queue_status["status"],
            "label_counts": _count_by(
                [
                    *generated_reports,
                    *missing_artifacts,
                    *skipped_steps,
                    safety_scanner_status,
                    release_bundle_status,
                    dashboard_status,
                    queue_status,
                    *human_review_notes,
                    *allowed_workflows,
                    *blocked_workflows,
                ],
                "label",
            ),
        },
        "generated_reports": generated_reports,
        "missing_artifacts": missing_artifacts,
        "skipped_steps": skipped_steps,
        "safety_scanner_status": safety_scanner_status,
        "release_bundle_status": release_bundle_status,
        "dashboard_status": dashboard_status,
        "queue_status": queue_status,
        "human_review_notes": human_review_notes,
        "allowed_human_review_workflows": allowed_workflows,
        "blocked_workflows": blocked_workflows,
    }
    _validate_json_value("research_cycle_audit_summary_payload", payload)
    return _normalize_json_value(payload)


def write_research_cycle_audit_summary(
    audit_input: ResearchCycleAuditSummaryInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR,
) -> tuple[Path, Path]:
    payload = build_research_cycle_audit_summary_payload(audit_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_CYCLE_AUDIT_SUMMARY_JSON
    markdown_path = out_dir / RESEARCH_CYCLE_AUDIT_SUMMARY_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_cycle_audit_summary_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_cycle_audit_summary_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_cycle_audit_summary_payload", payload)
    lines = [
        "# 19B Research Cycle Audit Summary",
        "",
        f"Audit ID: {payload['audit_id']}",
        f"Audit Date: {payload['audit_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "Allowed human-review workflows are separated from BLOCKED_BY_SAFETY_GATE workflows.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Generated reports", payload["summary"]["generated_report_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Allowed human-review workflows", payload["summary"]["allowed_human_review_workflow_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Human review notes", payload["summary"]["human_review_note_count"]),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        "",
    ]
    lines.extend(_section("Cycle Manifest Status", [payload["cycle_manifest_status"]]))
    lines.extend(_section("Generated Reports", payload["generated_reports"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_section("Release Bundle Status", [payload["release_bundle_status"]]))
    lines.extend(_section("Dashboard Status", [payload["dashboard_status"]]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Human Review Notes", payload["human_review_notes"]))
    lines.extend(_section("Allowed Human-Review Workflows", payload["allowed_human_review_workflows"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY audit summary only.",
            "- MONITOR_ONLY and PAPER_ONLY cycle states are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED workflows are review workflows only.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        status = {
            "workflow_id": "research_cycle_manifest",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "19A research cycle manifest JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "cycle_id": None,
            "cycle_date": None,
            "payload": {},
        }
        _validate_json_value("manifest_status", status)
        return _normalize_json_value(status)
    _validate_json_value("research_cycle_manifest", payload)
    summary = payload.get("summary", {})
    status = {
        "workflow_id": "research_cycle_manifest",
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": "present",
        "summary": (
            f"19A manifest present with {summary.get('completed_command_count', 0)} completed commands, "
            f"{summary.get('skipped_step_count', 0)} skipped steps, and "
            f"{summary.get('missing_artifact_count', 0)} missing artifacts."
        ),
        "path": path.as_posix(),
        "cycle_id": payload.get("cycle_id"),
        "cycle_date": payload.get("cycle_date"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "manifest_phase": payload.get("phase"),
        "payload": payload,
    }
    _validate_json_value("manifest_status", status)
    return _normalize_json_value(status)


def _generated_reports(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = manifest.get("command_outcomes", [])
    if not isinstance(outcomes, list):
        outcomes = []
    reports = []
    for item in outcomes:
        if not isinstance(item, dict) or item.get("status") != "completed":
            continue
        report = _report_from_outcome(item)
        if report is not None:
            reports.append(report)
    return sorted(reports, key=_sort_key)


def _report_from_outcome(item: dict[str, Any]) -> dict[str, Any] | None:
    json_path_value = item.get("json_path")
    markdown_path_value = item.get("markdown_path")
    if not isinstance(json_path_value, str) or not isinstance(markdown_path_value, str):
        return None
    json_path = Path(json_path_value)
    markdown_path = Path(markdown_path_value)
    _validate_audit_path(json_path)
    _validate_audit_path(markdown_path)
    metadata = _read_json_object(json_path) or {}
    if metadata:
        _validate_json_value("generated_report_metadata", metadata)
    value = {
        "workflow_id": item.get("step_id", "report"),
        "label": metadata.get("safety_boundary", {}).get("label", item.get("label", HUMAN_REVIEW_REQUIRED)),
        "status": "present" if json_path.is_file() and markdown_path.is_file() else "missing",
        "summary": _artifact_summary(metadata, item.get("summary", "Generated report recorded.")),
        "json_path": json_path.as_posix(),
        "markdown_path": markdown_path.as_posix(),
        "phase": metadata.get("phase"),
        "workflow": metadata.get("workflow", item.get("step_id", "Report")),
        "generated_at_utc": metadata.get("generated_at_utc"),
        "generated_date": _generated_date(metadata),
    }
    if value["status"] == "missing":
        value["label"] = BLOCKED_BY_SAFETY_GATE
    _validate_json_value("generated_report", value)
    return _normalize_json_value(value)


def _manifest_items(manifest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = manifest.get(key, [])
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = dict(item)
        if key == "missing_artifacts":
            value.setdefault("workflow_id", f"missing_{value.get('artifact_id', 'artifact')}")
            value.setdefault("label", BLOCKED_BY_SAFETY_GATE)
            value.setdefault("status", "missing")
        elif key == "skipped_steps":
            value.setdefault("workflow_id", value.get("step_id", "skipped_step"))
            value.setdefault("label", HUMAN_REVIEW_REQUIRED)
            value.setdefault("status", "skipped")
        value.setdefault("summary", "Recorded by 19A manifest.")
        _validate_json_value(key, value)
        normalized.append(_normalize_json_value(value))
    return sorted(normalized, key=_sort_key)


def _safety_scanner_status(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = manifest.get("safety_scanner_status")
    if not isinstance(payload, dict):
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied by the 19A manifest.",
            "finding_count": 0,
            "passed": None,
        }
    value = dict(payload)
    value.setdefault("workflow_id", "safety_scanner")
    value.setdefault("label", HUMAN_REVIEW_REQUIRED if value.get("passed") is not False else BLOCKED_BY_SAFETY_GATE)
    value.setdefault("status", "passed" if value.get("passed") else "not_run")
    value.setdefault("summary", "Safety scanner status carried from 19A manifest.")
    value.setdefault("finding_count", len(value.get("findings", ())) if isinstance(value.get("findings"), list) else 0)
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _artifact_payload_status(
    workflow_id: str,
    name: str,
    path: Path | None,
) -> dict[str, Any]:
    if path is None:
        return {
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": f"{name} JSON path was not present in the 19A manifest.",
            "path": None,
        }
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": f"{name} JSON was not found or could not be parsed.",
            "path": path.as_posix(),
        }
    _validate_json_value(workflow_id, payload)
    summary = payload.get("summary", {})
    value = {
        "workflow_id": workflow_id,
        "label": payload.get("safety_boundary", {}).get("label", payload.get("label", HUMAN_REVIEW_REQUIRED)),
        "status": payload.get("safety_boundary", {}).get("status", "LIVE TRADING: DISABLED"),
        "summary": _artifact_summary(payload, f"{name} was read for audit context."),
        "path": path.as_posix(),
        "phase": payload.get("phase"),
        "workflow": payload.get("workflow", name),
        "generated_at_utc": payload.get("generated_at_utc"),
        "generated_date": _generated_date(payload),
        "missing_artifact_count": summary.get("missing_artifact_count", 0) if isinstance(summary, dict) else 0,
        "blocked_workflow_count": summary.get("blocked_workflow_count", 0) if isinstance(summary, dict) else 0,
        "allowed_human_review_workflow_count": (
            summary.get("allowed_human_review_workflow_count", 0) if isinstance(summary, dict) else 0
        ),
    }
    _validate_json_value(f"{workflow_id}_status", value)
    return _normalize_json_value(value)


def _queue_status(path: Path, release_bundle_status: dict[str, Any]) -> dict[str, Any]:
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
    next_phase = _next_phase_from_release_bundle(release_bundle_status) or (items[0] if items else None)
    value = {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for 19B audit context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": next_phase,
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


def _next_phase_from_release_bundle(release_bundle_status: dict[str, Any]) -> dict[str, Any] | None:
    path_value = release_bundle_status.get("path")
    if not isinstance(path_value, str):
        return None
    payload = _read_json_object(Path(path_value))
    if not isinstance(payload, dict):
        return None
    queue_status = payload.get("queue_status")
    if not isinstance(queue_status, dict):
        return None
    next_phase = queue_status.get("next_phase")
    return next_phase if isinstance(next_phase, dict) else None


def _human_review_notes(
    manifest: dict[str, Any],
    dashboard_status: dict[str, Any],
    release_bundle_status: dict[str, Any],
) -> list[dict[str, Any]]:
    notes = [
        {
            "note_id": "19B-CYCLE-MANIFEST-REVIEW",
            "workflow_id": "review_cycle_manifest",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review the 19A cycle manifest before using audit findings for planning.",
        },
        {
            "note_id": "19B-RELEASE-BUNDLE-REVIEW",
            "workflow_id": "review_release_bundle",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review release bundle status and missing artifacts without changing execution state.",
        },
        {
            "note_id": "19B-DASHBOARD-REVIEW",
            "workflow_id": "review_dashboard_status",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review dashboard status as a monitor-only artifact.",
        },
    ]
    if manifest.get("missing_artifacts"):
        notes.append(
            {
                "note_id": "19B-MISSING-ARTIFACTS-REVIEW",
                "workflow_id": "review_missing_artifacts",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Resolve or explicitly accept missing artifacts before the next research cycle.",
            }
        )
    if dashboard_status.get("status") == "missing" or release_bundle_status.get("status") == "missing":
        notes.append(
            {
                "note_id": "19B-MISSING-SUMMARY-INPUTS",
                "workflow_id": "review_missing_summary_inputs",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "One or more 19B summary inputs were missing and require human review.",
            }
        )
    return _dedupe_by_id(notes, "note_id")


def _allowed_human_review_workflows(
    manifest: dict[str, Any],
    dashboard_status: dict[str, Any],
    release_bundle_status: dict[str, Any],
    notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        {
            "workflow_id": "review_cycle_manifest",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review the completed 19A manifest.",
        },
        {
            "workflow_id": "review_generated_reports",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review generated report artifacts.",
        },
        {
            "workflow_id": "review_queue_status",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review queued roadmap phases for planning only.",
        },
    ]
    items.extend(_extract_payload_workflows(dashboard_status, "allowed_human_review_workflows", HUMAN_REVIEW_REQUIRED))
    items.extend(_extract_payload_workflows(release_bundle_status, "allowed_human_review_workflows", HUMAN_REVIEW_REQUIRED))
    for note in notes:
        items.append(
            {
                "workflow_id": note["workflow_id"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "allowed_review_only",
                "summary": note["summary"],
                "source": "human_review_notes",
            }
        )
    if manifest.get("skipped_steps"):
        items.append(
            {
                "workflow_id": "review_skipped_steps",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "allowed_review_only",
                "summary": "Human operator may review skipped steps without treating them as execution instructions.",
            }
        )
    return _dedupe_workflows(items, default_label=HUMAN_REVIEW_REQUIRED)


def _blocked_workflows(
    manifest_status: dict[str, Any],
    manifest: dict[str, Any],
    missing_artifacts: list[dict[str, Any]],
    safety_scanner_status: dict[str, Any],
    dashboard_status: dict[str, Any],
    release_bundle_status: dict[str, Any],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
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
            "summary": "Broker routing is outside the 19B research cycle audit summary.",
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
    if manifest_status.get("label") == BLOCKED_BY_SAFETY_GATE or manifest_status.get("status") in {
        "missing",
        "invalid",
        "blocked",
    }:
        items.append(
            {
                "workflow_id": manifest_status.get("workflow_id", "research_cycle_manifest"),
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": manifest_status.get("summary", "19A manifest is blocked or incomplete."),
                "source": "cycle_manifest_status",
            }
        )
    items.extend(_manifest_items(manifest, "blocked_workflows"))
    for artifact in missing_artifacts:
        items.append(
            {
                "workflow_id": artifact.get("workflow_id", f"missing_{artifact.get('artifact_id', 'artifact')}"),
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": artifact.get("summary", "Missing artifact remains blocked."),
                "source": "missing_artifacts",
            }
        )
    for status_item in (safety_scanner_status, dashboard_status, release_bundle_status, queue_status):
        if status_item.get("label") == BLOCKED_BY_SAFETY_GATE or status_item.get("status") in {
            "missing",
            "invalid",
            "blocked",
        }:
            items.append(
                {
                    "workflow_id": status_item.get("workflow_id", "workflow"),
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": status_item.get("summary", "Workflow is blocked or incomplete."),
                    "source": "audit_status",
                }
            )
    items.extend(_extract_payload_workflows(dashboard_status, "blocked_workflows", BLOCKED_BY_SAFETY_GATE))
    items.extend(_extract_payload_workflows(release_bundle_status, "blocked_workflows", BLOCKED_BY_SAFETY_GATE))
    return _dedupe_workflows(items, default_label=BLOCKED_BY_SAFETY_GATE)


def _extract_payload_workflows(
    status: dict[str, Any],
    key: str,
    default_label: str,
) -> list[dict[str, Any]]:
    path_value = status.get("path")
    if not isinstance(path_value, str):
        return []
    payload = _read_json_object(Path(path_value))
    if not isinstance(payload, dict):
        return []
    workflows = payload.get(key, [])
    if not isinstance(workflows, list):
        return []
    extracted = []
    for item in workflows:
        if not isinstance(item, dict):
            continue
        value = {
            "workflow_id": item.get("workflow_id", "workflow"),
            "label": item.get("label", default_label),
            "status": item.get("status", "recorded"),
            "summary": item.get("summary", "Workflow recorded."),
            "source": status.get("workflow_id"),
        }
        _validate_json_value("extracted_workflow", value)
        extracted.append(value)
    return extracted


def _report_path(generated_reports: list[dict[str, Any]], workflow_id: str) -> Path | None:
    for report in generated_reports:
        if report.get("workflow_id") == workflow_id and isinstance(report.get("json_path"), str):
            return Path(str(report["json_path"]))
    return None


def _artifact_summary(payload: dict[str, Any], fallback: Any) -> str:
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return str(fallback)
    counts = [
        f"{key}={summary[key]}"
        for key in sorted(summary)
        if key.endswith("_count") and isinstance(summary[key], int)
    ]
    workflow = payload.get("workflow", "Artifact")
    return f"{workflow} status: {', '.join(counts[:4]) if counts else 'metadata recorded'}."


def _without_payload(status: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in status.items() if key != "payload"}
    _validate_json_value("manifest_status_without_payload", value)
    return _normalize_json_value(value)


def _dedupe_workflows(items: list[dict[str, Any]], *, default_label: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        workflow_id = str(item.get("workflow_id", "workflow"))
        value = dict(item)
        value.setdefault("workflow_id", workflow_id)
        value.setdefault("label", default_label)
        value.setdefault("status", "recorded")
        value.setdefault("summary", "Workflow recorded.")
        _validate_json_value("workflow", value)
        by_id[workflow_id] = _normalize_json_value(value)
    return sorted(by_id.values(), key=_sort_key)


def _dedupe_by_id(items: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    by_id = {}
    for item in items:
        value = dict(item)
        value.setdefault(id_key, "item")
        _validate_json_value(id_key, value)
        by_id[str(value[id_key])] = _normalize_json_value(value)
    return sorted(by_id.values(), key=_sort_key)


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


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_audit_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "cycle_date",
        "bundle_date",
        "snapshot_date",
        "index_date",
        "evidence_date",
        "journal_date",
        "runbook_date",
        "week_end",
        "report_date",
        "catalog_date",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
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
            item.get("workflow_id")
            or item.get("artifact_id")
            or item.get("step_id")
            or item.get("note_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status") or item.get("safety_status") or "recorded"
        summary = item.get("summary") or item.get("workflow") or "Recorded."
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


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source", "")),
        str(
            item.get("workflow_id")
            or item.get("artifact_id")
            or item.get("step_id")
            or item.get("note_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_audit_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research cycle audit summary cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research cycle audit summary cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research cycle audit summary paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research cycle audit summary paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_AUDIT_LABELS:
            raise ValueError(f"unsafe research cycle audit summary label: {label}")
        if label in DISALLOWED_AUDIT_LABELS:
            raise ValueError(f"disallowed research cycle audit summary label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research cycle audit summary cannot set {unsafe_field}")
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
        if value in DISALLOWED_AUDIT_LABELS:
            raise ValueError(f"disallowed research cycle audit summary text: {value}")
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
