from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.operator_dashboard_snapshot import OPERATOR_DASHBOARD_SNAPSHOT_JSON
from core.report_index import REPORT_INDEX_JSON
from core.research_cycle_audit_summary import (
    DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR,
    RESEARCH_CYCLE_AUDIT_SUMMARY_JSON,
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


DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR = Path("reports/research_cycle_readiness_gate")
RESEARCH_CYCLE_READINESS_GATE_JSON = "research_cycle_readiness_gate.json"
RESEARCH_CYCLE_READINESS_GATE_MARKDOWN = "research_cycle_readiness_gate.md"

READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"
READINESS_DECISIONS = (
    READY_FOR_HUMAN_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
    NEEDS_OPERATOR_REVIEW,
)
BASELINE_BLOCKED_WORKFLOWS = {
    "broker_order_call",
    "broker_order_routing",
    "live_trading",
    "order_execution",
    "secret_or_credential_access",
}
SAFE_READINESS_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_READINESS_LABELS = tuple(
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
class ResearchCycleReadinessGateInput:
    gate_id: str
    gate_date: str
    generated_at_utc: str
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON
    audit_summary_path: Path = (
        DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR / RESEARCH_CYCLE_AUDIT_SUMMARY_JSON
    )
    release_bundle_path: Path = DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR / RESEARCH_RELEASE_BUNDLE_JSON
    operator_dashboard_snapshot_path: Path = Path(
        "reports/operator_dashboard_snapshot"
    ) / OPERATOR_DASHBOARD_SNAPSHOT_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = (
        Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    )
    queue_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_report_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("gate_id", "gate_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research cycle readiness gate requires {field_name}")
        _parse_iso_date("gate_date", self.gate_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_report_age_days, int) or self.max_report_age_days < 0:
            raise ValueError("max_report_age_days must be a non-negative integer")
        for path in (
            self.manifest_path,
            self.audit_summary_path,
            self.release_bundle_path,
            self.operator_dashboard_snapshot_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_path,
            self.safety_scanner_path,
        ):
            _validate_readiness_path(path)


def build_default_research_cycle_readiness_gate_input(
    *,
    gate_date: date | None = None,
    now: datetime | None = None,
) -> ResearchCycleReadinessGateInput:
    generated = now or datetime.now(tz=UTC)
    day = gate_date or generated.date()
    return ResearchCycleReadinessGateInput(
        gate_id=f"20A-RESEARCH-CYCLE-READINESS-GATE-{day.isoformat()}",
        gate_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_cycle_readiness_gate_payload(
    gate_input: ResearchCycleReadinessGateInput,
) -> dict[str, Any]:
    gate_input.validate()
    gate_day = datetime.strptime(gate_input.gate_date, "%Y-%m-%d").date()
    required_artifacts = _required_artifact_statuses(gate_input)
    missing_artifacts = _missing_artifacts(required_artifacts)
    skipped_steps = _collect_keyed_items(required_artifacts, "skipped_steps", "step_id")
    blocked_workflows = _collect_keyed_items(required_artifacts, "blocked_workflows", "workflow_id")
    stale_reports = _stale_reports(required_artifacts, gate_day, gate_input.max_report_age_days)
    safety_scanner_status = _safety_scanner_status(gate_input, required_artifacts)
    failed_safety_findings = _failed_safety_findings(safety_scanner_status, required_artifacts)
    queue_status = _queue_status(gate_input.queue_path)
    required_actions = _required_human_review_actions(
        missing_artifacts,
        skipped_steps,
        stale_reports,
        blocked_workflows,
        failed_safety_findings,
        queue_status,
    )
    decision = _readiness_decision(
        missing_artifacts,
        skipped_steps,
        stale_reports,
        blocked_workflows,
        failed_safety_findings,
        queue_status,
    )

    payload = {
        "phase": "20A",
        "workflow": "Research Cycle Readiness Gate",
        "gate_id": gate_input.gate_id,
        "gate_date": gate_input.gate_date,
        "generated_at_utc": gate_input.generated_at_utc,
        "decision": decision,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_READINESS_LABELS),
        "summary": {
            "required_artifact_count": len(required_artifacts),
            "present_required_artifact_count": sum(
                1 for item in required_artifacts if item["status"] == "present"
            ),
            "missing_artifact_count": len(missing_artifacts),
            "skipped_step_count": len(skipped_steps),
            "stale_report_count": len(stale_reports),
            "blocked_workflow_count": len(blocked_workflows),
            "failed_safety_finding_count": len(failed_safety_findings),
            "required_human_review_action_count": len(required_actions),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *required_artifacts,
                    *missing_artifacts,
                    *skipped_steps,
                    *stale_reports,
                    *blocked_workflows,
                    *failed_safety_findings,
                    *required_actions,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "required_artifacts": required_artifacts,
        "missing_artifacts": missing_artifacts,
        "skipped_steps": skipped_steps,
        "stale_reports": stale_reports,
        "blocked_workflows": blocked_workflows,
        "failed_safety_findings": failed_safety_findings,
        "required_human_review_actions": required_actions,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
    }
    _validate_json_value("research_cycle_readiness_gate_payload", payload)
    return _normalize_json_value(payload)


def write_research_cycle_readiness_gate(
    gate_input: ResearchCycleReadinessGateInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_cycle_readiness_gate_payload(gate_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_CYCLE_READINESS_GATE_JSON
    markdown_path = out_dir / RESEARCH_CYCLE_READINESS_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_cycle_readiness_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_cycle_readiness_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_cycle_readiness_gate_payload", payload)
    lines = [
        "# 20A Research Cycle Readiness Gate",
        "",
        f"Gate ID: {payload['gate_id']}",
        f"Gate Date: {payload['gate_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Decision: {payload['decision']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE findings remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Required artifacts", payload["summary"]["required_artifact_count"]),
        _summary_line("Present required artifacts", payload["summary"]["present_required_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Stale reports", payload["summary"]["stale_report_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Failed safety findings", payload["summary"]["failed_safety_finding_count"]),
        _summary_line(
            "Required human-review actions",
            payload["summary"]["required_human_review_action_count"],
        ),
        "",
    ]
    lines.extend(_section("Required Artifacts", payload["required_artifacts"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"]))
    lines.extend(_section("Stale Reports", payload["stale_reports"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(_section("Failed Safety Findings", payload["failed_safety_findings"]))
    lines.extend(_section("Required Human-Review Actions", payload["required_human_review_actions"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY readiness gate only.",
            "- MONITOR_ONLY and PAPER_ONLY source artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED is the only allowed next-cycle approval path.",
            "- BLOCKED_BY_SAFETY_GATE findings remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _required_artifact_statuses(
    gate_input: ResearchCycleReadinessGateInput,
) -> list[dict[str, Any]]:
    artifact_paths = (
        ("research_cycle_manifest", "19A Research Cycle Manifest", gate_input.manifest_path),
        ("research_cycle_audit_summary", "19B Research Cycle Audit Summary", gate_input.audit_summary_path),
        ("research_release_bundle", "18B Research Release Bundle", gate_input.release_bundle_path),
        (
            "operator_dashboard_snapshot",
            "17B Operator Dashboard Snapshot",
            gate_input.operator_dashboard_snapshot_path,
        ),
        ("report_index", "17A Report Index", gate_input.report_index_path),
        ("safe_workflow_catalog", "18A Safe Workflow Catalog", gate_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", gate_input.safety_scanner_path),
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
    for status in statuses:
        _validate_json_value("required_artifact_status", status)
    return [_normalize_json_value(status) for status in statuses]


def _missing_artifacts(required_artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missing = []
    for artifact in required_artifacts:
        if artifact["status"] != "present":
            missing.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "workflow_id": f"missing_{artifact['artifact_id']}",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "missing",
                    "path": artifact["path"],
                    "summary": artifact["summary"],
                }
            )
    return sorted(missing, key=_sort_key)


def _collect_keyed_items(
    required_artifacts: list[dict[str, Any]],
    key: str,
    id_key: str,
) -> list[dict[str, Any]]:
    items = []
    for artifact in required_artifacts:
        payload = artifact.get("payload", {})
        if not isinstance(payload, dict):
            continue
        values = payload.get(key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            value = dict(item)
            value.setdefault(id_key, value.get("workflow_id") or value.get("artifact_id") or "item")
            value.setdefault("workflow_id", value.get(id_key))
            value.setdefault(
                "label",
                BLOCKED_BY_SAFETY_GATE if key == "blocked_workflows" else HUMAN_REVIEW_REQUIRED,
            )
            value.setdefault("status", "recorded")
            value.setdefault("summary", "Recorded by readiness input artifact.")
            value["source_artifact_id"] = artifact["artifact_id"]
            _validate_json_value(key, value)
            items.append(_normalize_json_value(value))
    return _dedupe_by_id(items, id_key)


def _stale_reports(
    required_artifacts: list[dict[str, Any]],
    gate_day: date,
    max_report_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for artifact in required_artifacts:
        if artifact["status"] != "present":
            continue
        generated_date = artifact.get("generated_date")
        if not isinstance(generated_date, str):
            stale.append(_stale_report(artifact, "unknown", "Report generated date was not present."))
            continue
        try:
            report_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
        except ValueError:
            stale.append(_stale_report(artifact, generated_date, "Report generated date was invalid."))
            continue
        age_days = (gate_day - report_day).days
        if age_days > max_report_age_days:
            stale.append(
                _stale_report(
                    artifact,
                    generated_date,
                    f"Report is {age_days} days old; maximum allowed age is {max_report_age_days} days.",
                )
            )
    return sorted(stale, key=_sort_key)


def _stale_report(artifact: dict[str, Any], generated_date: str, summary: str) -> dict[str, Any]:
    value = {
        "artifact_id": artifact["artifact_id"],
        "workflow_id": f"stale_{artifact['artifact_id']}",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "stale",
        "path": artifact["path"],
        "generated_date": generated_date,
        "summary": summary,
    }
    _validate_json_value("stale_report", value)
    return _normalize_json_value(value)


def _safety_scanner_status(
    gate_input: ResearchCycleReadinessGateInput,
    required_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    direct = _read_json_object(gate_input.safety_scanner_path)
    if isinstance(direct, dict):
        findings = direct.get("findings", [])
        finding_count = direct.get("finding_count", len(findings) if isinstance(findings, list) else 0)
        passed = direct.get("passed")
        value = {
            "workflow_id": "safety_scanner",
            "label": direct.get(
                "label",
                HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE,
            ),
            "status": direct.get("status", "passed" if passed else "not_run"),
            "summary": direct.get("summary", "Safety scanner status read by readiness gate."),
            "path": gate_input.safety_scanner_path.as_posix(),
            "finding_count": finding_count,
            "passed": passed,
            "findings": findings if isinstance(findings, list) else [],
        }
        _validate_json_value("safety_scanner_status", value)
        return _normalize_json_value(value)
    for artifact in required_artifacts:
        payload = artifact.get("payload", {})
        if isinstance(payload, dict) and isinstance(payload.get("safety_scanner_status"), dict):
            status = dict(payload["safety_scanner_status"])
            status.setdefault("workflow_id", "safety_scanner")
            status.setdefault("label", HUMAN_REVIEW_REQUIRED)
            status.setdefault("status", "not_run")
            status.setdefault("summary", "Safety scanner status inherited from readiness input artifact.")
            status.setdefault("path", artifact["path"])
            status.setdefault("finding_count", 0)
            status.setdefault("passed", None)
            status.setdefault("findings", [])
            _validate_json_value("safety_scanner_status", status)
            return _normalize_json_value(status)
    return {
        "workflow_id": "safety_scanner",
        "label": BLOCKED_BY_SAFETY_GATE,
        "status": "missing",
        "summary": "Safety scanner status was not found or could not be parsed.",
        "path": gate_input.safety_scanner_path.as_posix(),
        "finding_count": 0,
        "passed": None,
        "findings": [],
    }


def _failed_safety_findings(
    safety_scanner_status: dict[str, Any],
    required_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings = []
    if safety_scanner_status.get("passed") is False or safety_scanner_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        findings.append(
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": safety_scanner_status.get("summary", "Safety scanner failed."),
                "source": "safety_scanner_status",
            }
        )
    for item in safety_scanner_status.get("findings", []):
        if not isinstance(item, dict):
            continue
        value = {
            "finding_id": item.get("rule_id") or item.get("finding_id") or "safety_finding",
            "workflow_id": "safety_scanner",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "failed",
            "summary": item.get("summary") or item.get("message") or "Safety finding recorded.",
            "source": "safety_scanner_status",
        }
        _validate_json_value("failed_safety_finding", value)
        findings.append(_normalize_json_value(value))
    for artifact in required_artifacts:
        if artifact.get("label") == BLOCKED_BY_SAFETY_GATE and artifact.get("artifact_id") == "safety_scanner_status":
            findings.append(
                {
                    "finding_id": "missing_safety_scanner_status",
                    "workflow_id": "safety_scanner",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "failed",
                    "summary": artifact.get("summary", "Safety scanner status is missing."),
                    "source": artifact["artifact_id"],
                }
            )
    return _dedupe_by_id(findings, "finding_id")


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
        "summary": "Master plan queue read for 20A readiness context only.",
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
        if item.get("phase") == "20A":
            return item
    return items[0] if items else None


def _required_human_review_actions(
    missing_artifacts: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    stale_reports: list[dict[str, Any]],
    blocked_workflows: list[dict[str, Any]],
    failed_safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [
        {
            "action_id": "20A-REVIEW-READINESS-GATE",
            "workflow_id": "review_readiness_gate",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review this readiness gate before starting the next research cycle.",
        }
    ]
    if missing_artifacts:
        actions.append(
            {
                "action_id": "20A-RESOLVE-MISSING-ARTIFACTS",
                "workflow_id": "resolve_missing_artifacts",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Resolve or explicitly accept missing required artifacts before proceeding.",
            }
        )
    if skipped_steps:
        actions.append(
            {
                "action_id": "20A-REVIEW-SKIPPED-STEPS",
                "workflow_id": "review_skipped_steps",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review skipped cycle steps before interpreting readiness.",
            }
        )
    if stale_reports:
        actions.append(
            {
                "action_id": "20A-REFRESH-STALE-REPORTS",
                "workflow_id": "refresh_stale_reports",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Refresh stale report artifacts or record operator acceptance.",
            }
        )
    if _operator_blocked_workflows(blocked_workflows):
        actions.append(
            {
                "action_id": "20A-REVIEW-BLOCKED-WORKFLOWS",
                "workflow_id": "review_blocked_workflows",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review non-baseline blocked workflows before the next cycle.",
            }
        )
    if failed_safety_findings:
        actions.append(
            {
                "action_id": "20A-RESOLVE-SAFETY-FINDINGS",
                "workflow_id": "resolve_safety_findings",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Resolve failed safety findings before proceeding.",
            }
        )
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(
            {
                "action_id": "20A-REVIEW-QUEUE-STATUS",
                "workflow_id": "review_queue_status",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review missing or invalid queue status.",
            }
        )
    return _dedupe_by_id(actions, "action_id")


def _readiness_decision(
    missing_artifacts: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    stale_reports: list[dict[str, Any]],
    blocked_workflows: list[dict[str, Any]],
    failed_safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
) -> str:
    if missing_artifacts or failed_safety_findings or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        return BLOCKED_BY_SAFETY_GATE
    if skipped_steps or stale_reports or _operator_blocked_workflows(blocked_workflows):
        return NEEDS_OPERATOR_REVIEW
    return READY_FOR_HUMAN_REVIEW


def _operator_blocked_workflows(blocked_workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in blocked_workflows
        if str(item.get("workflow_id")) not in BASELINE_BLOCKED_WORKFLOWS
        and not str(item.get("workflow_id", "")).startswith("missing_")
    ]


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
    _validate_readiness_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "gate_date",
        "audit_date",
        "cycle_date",
        "bundle_date",
        "snapshot_date",
        "index_date",
        "catalog_date",
        "evidence_date",
        "journal_date",
        "runbook_date",
        "week_end",
        "report_date",
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
            item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("step_id")
            or item.get("finding_id")
            or item.get("action_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status") or item.get("decision") or "recorded"
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
            or item.get("workflow_id")
            or item.get("step_id")
            or item.get("finding_id")
            or item.get("action_id")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_readiness_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research cycle readiness gate cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research cycle readiness gate cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research cycle readiness gate paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research cycle readiness gate paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_READINESS_LABELS:
            raise ValueError(f"unsafe research cycle readiness gate label: {label}")
        if label in DISALLOWED_READINESS_LABELS:
            raise ValueError(f"disallowed research cycle readiness gate label: {label}")
        decision = value.get("decision")
        if decision is not None and decision not in READINESS_DECISIONS:
            raise ValueError(f"invalid research cycle readiness decision: {decision}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research cycle readiness gate cannot set {unsafe_field}")
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
        if value in DISALLOWED_READINESS_LABELS:
            raise ValueError(f"disallowed research cycle readiness gate text: {value}")
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
