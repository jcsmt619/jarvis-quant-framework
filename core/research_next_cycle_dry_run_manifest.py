from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.report_index import REPORT_INDEX_JSON
from core.research_cycle_rollover_gate import (
    DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR,
    RESEARCH_CYCLE_ROLLOVER_GATE_JSON,
)
from core.research_next_cycle_plan import (
    DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
    RESEARCH_NEXT_CYCLE_PLAN_JSON,
)
from core.research_next_cycle_safety_preflight import (
    DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR,
    RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR = Path("reports/research_next_cycle_dry_run_manifest")
RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON = "research_next_cycle_dry_run_manifest.json"
RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_MARKDOWN = "research_next_cycle_dry_run_manifest.md"

DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW = "DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW"
DRY_RUN_MANIFEST_NEEDS_OPERATOR_REVIEW = "DRY_RUN_MANIFEST_NEEDS_OPERATOR_REVIEW"

SAFE_DRY_RUN_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DRY_RUN_MANIFEST_STATES = (
    DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW,
    DRY_RUN_MANIFEST_NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_DRY_RUN_LABELS = tuple(
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
    "next_cycle_started",
    "order_execution_used",
    "real_paper_order_submitted",
    "real_paper_wrapper_attempted",
    "real_paper_wrapper_connected",
    "research_workflow_run_started",
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
    "dry_run_manifest_date",
    "preflight_date",
    "next_cycle_plan_date",
    "rollover_gate_date",
    "index_date",
    "catalog_date",
    "report_date",
)
OPERATOR_REVIEW_KEYS = (
    "required_operator_actions",
    "required_next_human_review_actions",
    "operator_review_items",
    "unresolved_operator_review_items",
    "safety_preflight_items",
    "open_items",
    "human_review_notes",
)


@dataclass(frozen=True)
class ResearchNextCycleDryRunManifestInput:
    dry_run_manifest_id: str
    dry_run_manifest_date: str
    generated_at_utc: str
    safety_preflight_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR / RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON
    )
    next_cycle_plan_path: Path = DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR / RESEARCH_NEXT_CYCLE_PLAN_JSON
    rollover_gate_path: Path = DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR / RESEARCH_CYCLE_ROLLOVER_GATE_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("dry_run_manifest_id", "dry_run_manifest_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research next cycle dry-run manifest requires {field_name}")
        _parse_iso_date("dry_run_manifest_date", self.dry_run_manifest_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.safety_preflight_path,
            self.next_cycle_plan_path,
            self.rollover_gate_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_dry_run_path(path)


def build_default_research_next_cycle_dry_run_manifest_input(
    *,
    dry_run_manifest_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCycleDryRunManifestInput:
    generated = now or datetime.now(tz=UTC)
    day = dry_run_manifest_date or generated.date()
    return ResearchNextCycleDryRunManifestInput(
        dry_run_manifest_id=f"25B-RESEARCH-NEXT-CYCLE-DRY-RUN-MANIFEST-{day.isoformat()}",
        dry_run_manifest_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_dry_run_manifest_payload(
    manifest_input: ResearchNextCycleDryRunManifestInput,
) -> dict[str, Any]:
    manifest_input.validate()
    manifest_day = datetime.strptime(manifest_input.dry_run_manifest_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(manifest_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    queue_status = _queue_status(manifest_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(manifest_input.safety_scanner_path)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, manifest_day, manifest_input.max_source_age_days)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    blocked_prerequisites = _blocked_prerequisites(source_payloads, missing_artifacts, safety_findings, queue_status)
    required_refreshed_artifacts = _required_refreshed_artifacts(source_payloads, missing_artifacts, stale_artifacts)
    required_operator_review_items = _required_operator_review_items(source_payloads)
    planned_steps = _planned_steps(source_payloads, queue_status)
    command_hints = _command_hints(planned_steps)
    input_artifacts = _input_artifacts(source_artifacts)
    expected_output_artifacts = _expected_output_artifacts(planned_steps)
    skipped_steps = _skipped_steps(planned_steps, blocked_prerequisites, missing_artifacts, safety_findings)
    acceptance_criteria = _acceptance_criteria(
        blocked_prerequisites=blocked_prerequisites,
        required_refreshed_artifacts=required_refreshed_artifacts,
        required_operator_review_items=required_operator_review_items,
        skipped_steps=skipped_steps,
    )
    dry_run_manifest_state = _dry_run_manifest_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        blocked_prerequisites=blocked_prerequisites,
        required_operator_review_items=required_operator_review_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "25B",
        "workflow": "Next Cycle Dry Run Manifest",
        "dry_run_manifest_id": manifest_input.dry_run_manifest_id,
        "dry_run_manifest_date": manifest_input.dry_run_manifest_date,
        "generated_at_utc": manifest_input.generated_at_utc,
        "dry_run_manifest_state": dry_run_manifest_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_DRY_RUN_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "planned_step_count": len(planned_steps),
            "command_hint_count": len(command_hints),
            "input_artifact_count": len(input_artifacts),
            "expected_output_artifact_count": len(expected_output_artifacts),
            "skipped_step_count": len(skipped_steps),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "required_operator_review_item_count": len(required_operator_review_items),
            "safety_finding_count": len(safety_findings),
            "acceptance_criteria_count": len(acceptance_criteria),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *planned_steps,
                    *command_hints,
                    *input_artifacts,
                    *expected_output_artifacts,
                    *skipped_steps,
                    *blocked_prerequisites,
                    *required_refreshed_artifacts,
                    *required_operator_review_items,
                    *safety_findings,
                    *acceptance_criteria,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "planned_next_cycle_steps": planned_steps,
        "command_hints": command_hints,
        "input_artifacts": input_artifacts,
        "expected_output_artifacts": expected_output_artifacts,
        "skipped_steps": skipped_steps,
        "blocked_prerequisites": blocked_prerequisites,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "required_operator_review_items": required_operator_review_items,
        "safety_findings": safety_findings,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "acceptance_criteria": acceptance_criteria,
        "final_dry_run_manifest_summary": _final_dry_run_manifest_summary(
            dry_run_manifest_state=dry_run_manifest_state,
            planned_steps=planned_steps,
            command_hints=command_hints,
            skipped_steps=skipped_steps,
            blocked_prerequisites=blocked_prerequisites,
            required_refreshed_artifacts=required_refreshed_artifacts,
            required_operator_review_items=required_operator_review_items,
            acceptance_criteria=acceptance_criteria,
        ),
    }
    _validate_json_value("research_next_cycle_dry_run_manifest_payload", payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_dry_run_manifest(
    manifest_input: ResearchNextCycleDryRunManifestInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_dry_run_manifest_payload(manifest_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_dry_run_manifest_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_dry_run_manifest_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_next_cycle_dry_run_manifest_payload", payload)
    lines = [
        "# 25B Next Cycle Dry Run Manifest",
        "",
        f"Dry Run Manifest ID: {payload['dry_run_manifest_id']}",
        f"Dry Run Manifest Date: {payload['dry_run_manifest_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Dry Run Manifest State: {payload['dry_run_manifest_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Next-cycle dry-run manifests are read-only and records-only.",
        "Command hints are inert records only; commands are not executed and the next cycle is not run.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Dry-Run Manifest Summary",
        "",
        payload["final_dry_run_manifest_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Planned steps", payload["summary"]["planned_step_count"]),
        _summary_line("Command hints", payload["summary"]["command_hint_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Required operator review items", payload["summary"]["required_operator_review_item_count"]),
        _summary_line("Acceptance criteria", payload["summary"]["acceptance_criteria_count"]),
        "",
    ]
    lines.extend(_section("Planned Next-Cycle Steps", payload["planned_next_cycle_steps"]))
    lines.extend(_section("Command Hints", payload["command_hints"]))
    lines.extend(_section("Input Artifacts", payload["input_artifacts"]))
    lines.extend(_section("Expected Output Artifacts", payload["expected_output_artifacts"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"]))
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Required Operator Review Items", payload["required_operator_review_items"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Acceptance Criteria", payload["acceptance_criteria"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY dry-run manifest generation only.",
            "- MONITOR_ONLY and PAPER_ONLY workflows are described, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only manifest; no command execution, next-cycle run, artifact mutation, artifact deletion, broker action, trade instruction, execution permission, live-trading enablement, or order path submission is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(manifest_input: ResearchNextCycleDryRunManifestInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("safety_preflight", "25A Next Cycle Safety Preflight", manifest_input.safety_preflight_path),
        ("next_cycle_plan", "24B Next Research Cycle Plan", manifest_input.next_cycle_plan_path),
        ("rollover_gate", "24A Research Cycle Rollover Gate", manifest_input.rollover_gate_path),
        ("report_index", "Report Index", manifest_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", manifest_input.safe_workflow_catalog_path),
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


def _planned_steps(source_payloads: dict[str, dict[str, Any]], queue_status: dict[str, Any]) -> list[dict[str, Any]]:
    plan_payload = source_payloads.get("next_cycle_plan", {})
    planned = plan_payload.get("planned_research_report_workflows", [])
    steps = []
    if isinstance(planned, list):
        for index, item in enumerate(planned, start=1):
            if not isinstance(item, dict):
                continue
            phase = item.get("phase") or f"planned_{index}"
            title = item.get("title") or item.get("workflow") or "Planned research/report workflow"
            steps.append(
                {
                    "step_id": f"25B-STEP-{phase}",
                    "phase": phase,
                    "title": title,
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": "dry_run_planned_not_started",
                    "summary": item.get("summary", "Planned next-cycle workflow recorded as a dry-run step."),
                    "would_run": False,
                    "run_started": False,
                    "records_only": True,
                    "human_review_required": True,
                }
            )
    if not steps:
        next_phase = queue_status.get("next_phase")
        if isinstance(next_phase, dict):
            steps.append(
                {
                    "step_id": f"25B-STEP-{next_phase.get('phase', 'next_phase')}",
                    "phase": next_phase.get("phase"),
                    "title": next_phase.get("title", "Queued next phase"),
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "dry_run_planned_not_started",
                    "summary": next_phase.get("summary", "Queued next phase recorded as a dry-run step."),
                    "would_run": False,
                    "run_started": False,
                    "records_only": True,
                    "human_review_required": True,
                }
            )
    if not steps:
        steps.append(
            {
                "step_id": "25B-STEP-NEXT-CYCLE-SELECTION",
                "phase": None,
                "title": "Next-cycle workflow selection",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "requires_operator_review",
                "summary": "No planned next-cycle workflow was available; operator review is required.",
                "would_run": False,
                "run_started": False,
                "records_only": True,
                "human_review_required": True,
            }
        )
    return _dedupe_by_id(steps, "step_id")


def _command_hints(planned_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hints = []
    for step in planned_steps:
        phase = step.get("phase") or "next_cycle"
        hints.append(
            {
                "hint_id": f"25B-HINT-{phase}",
                "step_id": step["step_id"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "hint_only_not_executed",
                "summary": f"Review the approved runbook or phase script for {phase}; this manifest does not execute it.",
                "command_hint": f"# dry-run hint only: review command for {phase}",
                "would_run": False,
                "executed": False,
                "records_only": True,
            }
        )
    return _dedupe_by_id(hints, "hint_id")


def _input_artifacts(source_artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for source in source_artifacts:
        items.append(
            {
                "artifact_id": source["artifact_id"],
                "label": source["label"],
                "status": source["status"],
                "summary": source["summary"],
                "path": source["path"],
                "required_for_dry_run": True,
                "read_only": True,
            }
        )
    return _dedupe_by_id(items, "artifact_id")


def _expected_output_artifacts(planned_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs = [
        {
            "artifact_id": "25b_dry_run_manifest_json",
            "step_id": "25B-SELF",
            "label": RESEARCH_ONLY,
            "status": "expected_record",
            "summary": "25B JSON dry-run manifest record.",
            "path": (
                DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR
                / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON
            ).as_posix(),
            "created_by_next_cycle": False,
        },
        {
            "artifact_id": "25b_dry_run_manifest_markdown",
            "step_id": "25B-SELF",
            "label": RESEARCH_ONLY,
            "status": "expected_record",
            "summary": "25B Markdown dry-run manifest record.",
            "path": (
                DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR
                / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_MARKDOWN
            ).as_posix(),
            "created_by_next_cycle": False,
        },
    ]
    for step in planned_steps:
        phase = str(step.get("phase") or step["step_id"]).lower().replace("-", "_")
        outputs.append(
            {
                "artifact_id": f"dry_run_expected_{phase}",
                "step_id": step["step_id"],
                "label": MONITOR_ONLY,
                "status": "expected_next_cycle_artifact_not_created",
                "summary": f"Expected future records for {step.get('title', phase)} are listed only; 25B does not create them.",
                "path": f"reports/{phase}/",
                "created_by_next_cycle": False,
            }
        )
    return _dedupe_by_id(outputs, "artifact_id")


def _skipped_steps(
    planned_steps: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons = []
    if blocked_prerequisites:
        reasons.append("blocked prerequisites")
    if missing_artifacts:
        reasons.append("missing source artifacts")
    if safety_findings:
        reasons.append("safety findings")
    reason_text = ", ".join(reasons) if reasons else "25B is dry-run only"
    return _dedupe_by_id(
        [
            {
                "skipped_step_id": f"SKIP-{step['step_id']}",
                "step_id": step["step_id"],
                "label": HUMAN_REVIEW_REQUIRED if not reasons else BLOCKED_BY_SAFETY_GATE,
                "status": "skipped_not_executed",
                "summary": f"{step.get('title', 'Planned step')} was not executed: {reason_text}.",
                "would_run": False,
                "executed": False,
            }
            for step in planned_steps
        ],
        "skipped_step_id",
    )


def _blocked_prerequisites(
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        _blocked(f"missing_{item['artifact_id']}", f"{item['name']} must be present before any next-cycle run.")
        for item in missing_artifacts
    ]
    for artifact_id, payload in source_payloads.items():
        for key in ("blocked_prerequisites", "blocked_items"):
            for item in _items_from_payload(payload, key):
                items.append(
                    {
                        "prerequisite_id": f"{artifact_id}_{item.get('prerequisite_id') or item.get('item_id') or item.get('workflow_id') or key}",
                        "label": BLOCKED_BY_SAFETY_GATE,
                        "status": item.get("status", "blocked"),
                        "summary": item.get("summary", "Source artifact reported a blocked prerequisite."),
                        "source_artifact_id": artifact_id,
                    }
                )
    if safety_findings:
        items.append(_blocked("safety_findings_present", "Safety findings must be resolved before any next-cycle run."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(_blocked("master_plan_queue_unavailable", "Master plan queue must be present and valid."))
    return _dedupe_by_id(items, "prerequisite_id")


def _required_refreshed_artifacts(
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        _refresh(f"refresh_missing_{item['artifact_id']}", item["artifact_id"], f"{item['name']} must be regenerated or explicitly accepted.")
        for item in missing_artifacts
    ]
    items.extend(
        _refresh(f"refresh_stale_{item['artifact_id']}", item["artifact_id"], f"{item['name']} is stale or has an unknown date.")
        for item in stale_artifacts
    )
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "required_refreshed_artifacts"):
            items.append(
                {
                    "refresh_id": f"{artifact_id}_{item.get('refresh_id') or item.get('artifact_id') or 'refresh'}",
                    "artifact_id": item.get("artifact_id", artifact_id),
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": item.get("status", "required_before_next_cycle"),
                    "summary": item.get("summary", "Source artifact requires a refreshed artifact."),
                    "source_artifact_id": artifact_id,
                }
            )
    return _dedupe_by_id(items, "refresh_id")


def _required_operator_review_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in OPERATOR_REVIEW_KEYS:
            for item in _items_from_payload(payload, key):
                items.append(
                    {
                        "review_item_id": f"{artifact_id}_{item.get('review_item_id') or item.get('action_id') or item.get('preflight_id') or item.get('workflow_id') or key}",
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status", "open_review_item"),
                        "summary": item.get("summary", "Source artifact requires operator review."),
                        "source_artifact_id": artifact_id,
                    }
                )
    return _dedupe_by_id(items, "review_item_id")


def _acceptance_criteria(
    *,
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    required_operator_review_items: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _criterion("25B-ACCEPT-RECORDS-ONLY", "25B produces JSON and Markdown records only and does not run the next cycle.", RESEARCH_ONLY),
            _criterion("25B-ACCEPT-COMMAND-HINTS-INERT", "Command hints are recorded as inert text with would_run=false and executed=false.", HUMAN_REVIEW_REQUIRED),
            _criterion("25B-ACCEPT-SAFETY-LABELS", "Required safety labels and LIVE TRADING: DISABLED are present.", HUMAN_REVIEW_REQUIRED),
            _criterion("25B-ACCEPT-BLOCKED-PREREQS", f"Blocked prerequisite count is {len(blocked_prerequisites)} and remains blocked until human review.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
            _criterion("25B-ACCEPT-REFRESHES", f"Required refreshed artifact count is {len(required_refreshed_artifacts)} and must be resolved or accepted.", HUMAN_REVIEW_REQUIRED),
            _criterion("25B-ACCEPT-OPERATOR-REVIEW", f"Required operator review item count is {len(required_operator_review_items)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("25B-ACCEPT-SKIPPED-STEPS", f"Skipped step count is {len(skipped_steps)} and no planned step is executed.", PAPER_ONLY),
        ],
        "criterion_id",
    )


def _dry_run_manifest_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    required_operator_review_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or safety_findings
        or blocked_prerequisites
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
    ):
        return BLOCKED_BY_SAFETY_GATE
    if stale_artifacts or required_operator_review_items:
        return DRY_RUN_MANIFEST_NEEDS_OPERATOR_REVIEW
    return DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "safety_findings"):
            items.append(
                {
                    "finding_id": f"{artifact_id}_{item.get('finding_id') or item.get('rule_id') or item.get('workflow_id') or 'safety_finding'}",
                    "workflow_id": item.get("workflow_id", artifact_id),
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": item.get("status", "failed"),
                    "summary": item.get("summary", "Safety finding recorded by source artifact."),
                    "source_artifact_id": artifact_id,
                }
            )
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
            "items": [],
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
            "items": [],
        }
    items = [_queue_item(item) for item in payload if isinstance(item, dict)]
    value = {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for 25B dry-run manifest context only.",
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
            "summary": "Safety scanner status was not supplied to 25B.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 25B."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
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
        if item.get("phase") == "25B":
            return item
    return items[0] if items else None


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "records_only": True,
        "dry_run_only": True,
        "read_only": True,
        "commands_executed": False,
        "next_cycle_started": False,
        "research_workflow_run_started": False,
        "artifact_delete_performed": False,
        "artifact_mutation_performed": False,
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


def _final_dry_run_manifest_summary(
    *,
    dry_run_manifest_state: str,
    planned_steps: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    required_operator_review_items: list[dict[str, Any]],
    acceptance_criteria: list[dict[str, Any]],
) -> str:
    return (
        f"Next-cycle dry-run manifest state is {dry_run_manifest_state}. "
        f"Planned steps: {len(planned_steps)}. "
        f"Command hints: {len(command_hints)}. "
        f"Skipped steps: {len(skipped_steps)}. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Required operator review items: {len(required_operator_review_items)}. "
        f"Acceptance criteria: {len(acceptance_criteria)}. "
        "Safety boundary confirmed: 25B is dry-run only and records-only and does not execute commands, run the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, grant execution permissions, or submit any order path. "
        "LIVE TRADING: DISABLED."
    )


def _refresh(refresh_id: str, artifact_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "refresh_id": refresh_id,
        "artifact_id": artifact_id,
        "label": label,
        "status": "required_before_next_cycle",
        "summary": summary,
    }


def _blocked(prerequisite_id: str, summary: str) -> dict[str, Any]:
    return {
        "prerequisite_id": prerequisite_id,
        "label": BLOCKED_BY_SAFETY_GATE,
        "status": "blocked",
        "summary": summary,
    }


def _criterion(criterion_id: str, summary: str, label: str) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "label": label,
        "status": "acceptance_required",
        "summary": summary,
    }


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


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    manifest_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for item in source_artifacts:
        if item["status"] != "present":
            continue
        age_days = _age_days(manifest_day, item.get("generated_date"))
        if age_days is None or age_days > max_source_age_days:
            value = {
                "artifact_id": item["artifact_id"],
                "name": item["name"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "stale_or_unknown_date",
                "summary": f"{item['name']} is stale or has no recognized generated date.",
                "path": item["path"],
                "generated_date": item.get("generated_date"),
                "age_days": age_days,
            }
            _validate_json_value("stale_artifact", value)
            stale.append(value)
    return _dedupe_by_id(stale, "artifact_id")


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_dry_run_path(path)
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


def _age_days(manifest_day: date, generated_date: str | None) -> int | None:
    if generated_date is None:
        return None
    try:
        generated_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (manifest_day - generated_day).days


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("step_id")
            or item.get("hint_id")
            or item.get("artifact_id")
            or item.get("skipped_step_id")
            or item.get("prerequisite_id")
            or item.get("refresh_id")
            or item.get("review_item_id")
            or item.get("finding_id")
            or item.get("criterion_id")
            or item.get("workflow_id")
            or item.get("phase")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status", "recorded")
        summary = item.get("summary") or item.get("title") or item.get("name") or "Recorded."
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
            item.get("step_id")
            or item.get("hint_id")
            or item.get("artifact_id")
            or item.get("skipped_step_id")
            or item.get("prerequisite_id")
            or item.get("refresh_id")
            or item.get("review_item_id")
            or item.get("finding_id")
            or item.get("criterion_id")
            or item.get("workflow_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_dry_run_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research next cycle dry-run manifest cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research next cycle dry-run manifest cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research next cycle dry-run manifest paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research next cycle dry-run manifest paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_DRY_RUN_LABELS:
            raise ValueError(f"unsafe research next cycle dry-run manifest label: {label}")
        manifest_state = value.get("dry_run_manifest_state")
        if manifest_state is not None and manifest_state not in DRY_RUN_MANIFEST_STATES:
            raise ValueError(f"invalid research next cycle dry-run manifest state: {manifest_state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research next cycle dry-run manifest cannot set {unsafe_field}")
        for mutation_field in ("artifact_delete_performed", "artifact_mutation_performed", "commands_executed"):
            if value.get(mutation_field) is True:
                raise ValueError(f"research next cycle dry-run manifest cannot set {mutation_field}")
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
        if value in DISALLOWED_DRY_RUN_LABELS:
            raise ValueError(f"disallowed research next cycle dry-run manifest text: {value}")
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
