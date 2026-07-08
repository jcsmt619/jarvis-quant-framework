from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.report_index import REPORT_INDEX_JSON
from core.research_cycle_archive_index import (
    DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR,
    RESEARCH_CYCLE_ARCHIVE_INDEX_JSON,
)
from core.research_cycle_rollover_gate import (
    DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR,
    RESEARCH_CYCLE_ROLLOVER_GATE_JSON,
)
from core.research_next_cycle_dry_run_manifest import (
    DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR,
    RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON,
)
from core.research_next_cycle_operator_acceptance_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_DIR,
    RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_JSON,
)
from core.research_next_cycle_acceptance_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_JSON,
)
from core.research_next_cycle_plan import (
    DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
    RESEARCH_NEXT_CYCLE_PLAN_JSON,
)
from core.research_next_cycle_safety_preflight import (
    DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR,
    RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON,
)
from core.research_operations_console import (
    DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR,
    RESEARCH_OPERATIONS_CONSOLE_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_DIR = Path("reports/research_next_cycle_launch_control_gate")
RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_JSON = "research_next_cycle_launch_control_gate.json"
RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_MARKDOWN = "research_next_cycle_launch_control_gate.md"

LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW = "LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"

SAFE_LAUNCH_CONTROL_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
LAUNCH_CONTROL_STATES = (
    LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_LAUNCH_CONTROL_LABELS = tuple(
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
    "launch_control_gate_date",
    "operator_acceptance_gate_date",
    "dry_run_manifest_date",
    "preflight_date",
    "next_cycle_plan_date",
    "rollover_gate_date",
    "archive_index_date",
    "console_date",
    "index_date",
    "catalog_date",
    "report_date",
)
REVIEW_KEYS = (
    "required_operator_actions",
    "required_next_human_review_actions",
    "required_operator_review_items",
    "operator_review_items",
    "unresolved_operator_review_items",
    "safety_preflight_items",
    "open_items",
    "human_review_notes",
)


@dataclass(frozen=True)
class ResearchNextCycleLaunchControlGateInput:
    launch_control_gate_id: str
    launch_control_gate_date: str
    generated_at_utc: str
    acceptance_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_DIR / RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_JSON
    )
    operator_acceptance_gate_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_DIR / RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_JSON
    )
    dry_run_manifest_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON
    )
    safety_preflight_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR / RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON
    )
    next_cycle_plan_path: Path = DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR / RESEARCH_NEXT_CYCLE_PLAN_JSON
    rollover_gate_path: Path = DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR / RESEARCH_CYCLE_ROLLOVER_GATE_JSON
    archive_index_path: Path = DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR / RESEARCH_CYCLE_ARCHIVE_INDEX_JSON
    operations_console_path: Path = DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR / RESEARCH_OPERATIONS_CONSOLE_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("launch_control_gate_id", "launch_control_gate_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research Next Cycle Launch Control Gate requires {field_name}")
        _parse_iso_date("launch_control_gate_date", self.launch_control_gate_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.acceptance_packet_path,
            self.operator_acceptance_gate_path,
            self.dry_run_manifest_path,
            self.safety_preflight_path,
            self.next_cycle_plan_path,
            self.rollover_gate_path,
            self.archive_index_path,
            self.operations_console_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_gate_path(path)


def build_default_research_next_cycle_launch_control_gate_input(
    *,
    launch_control_gate_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCycleLaunchControlGateInput:
    generated = now or datetime.now(tz=UTC)
    day = launch_control_gate_date or generated.date()
    return ResearchNextCycleLaunchControlGateInput(
        launch_control_gate_id=f"27A-RESEARCH-NEXT-CYCLE-LAUNCH-CONTROL-GATE-{day.isoformat()}",
        launch_control_gate_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_launch_control_gate_payload(
    gate_input: ResearchNextCycleLaunchControlGateInput,
) -> dict[str, Any]:
    gate_input.validate()
    gate_day = datetime.strptime(gate_input.launch_control_gate_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(gate_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    queue_status = _queue_status(gate_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(gate_input.safety_scanner_path)
    acceptance_state = _source_acceptance_state(source_payloads)
    queue_next_phase = _queue_next_phase(queue_status)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, gate_day, gate_input.max_source_age_days)
    planned_steps = _planned_dry_run_steps(source_payloads, queue_status)
    command_hints = _command_hints(source_payloads, planned_steps)
    skipped_steps = _skipped_steps(planned_steps, missing_artifacts)
    blocked_prerequisites = _blocked_prerequisites(source_payloads, missing_artifacts, safety_scanner_status)
    required_refreshed_artifacts = _required_refreshed_artifacts(missing_artifacts, stale_artifacts, source_payloads)
    operator_review_items = _operator_review_items(source_payloads)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    unresolved_items = _unresolved_items(source_payloads, blocked_prerequisites, required_refreshed_artifacts)
    required_human_review_actions = _required_human_review_actions(
        blocked_prerequisites=blocked_prerequisites,
        required_refreshed_artifacts=required_refreshed_artifacts,
        operator_review_items=operator_review_items,
        safety_findings=safety_findings,
        unresolved_items=unresolved_items,
    )
    launch_control_criteria = _launch_control_criteria(
        planned_steps=planned_steps,
        command_hints=command_hints,
        skipped_steps=skipped_steps,
        blocked_prerequisites=blocked_prerequisites,
        required_refreshed_artifacts=required_refreshed_artifacts,
        operator_review_items=operator_review_items,
        safety_findings=safety_findings,
        unresolved_items=unresolved_items,
    )
    launch_control_gate_state = _launch_control_gate_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        blocked_prerequisites=blocked_prerequisites,
        operator_review_items=operator_review_items,
        unresolved_items=unresolved_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "27A",
        "workflow": "Next Cycle Launch Control Gate",
        "launch_control_gate_id": gate_input.launch_control_gate_id,
        "launch_control_gate_date": gate_input.launch_control_gate_date,
        "generated_at_utc": gate_input.generated_at_utc,
        "acceptance_state": acceptance_state,
        "launch_control_gate_state": launch_control_gate_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_LAUNCH_CONTROL_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "planned_dry_run_step_count": len(planned_steps),
            "planned_records_only_step_count": len(planned_steps),
            "command_hint_count": len(command_hints),
            "skipped_step_count": len(skipped_steps),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "operator_review_item_count": len(operator_review_items),
            "safety_finding_count": len(safety_findings),
            "launch_control_criteria_count": len(launch_control_criteria),
            "unresolved_item_count": len(unresolved_items),
            "required_human_review_action_count": len(required_human_review_actions),
            "required_operator_action_count": len(required_human_review_actions),
            "acceptance_state": acceptance_state,
            "queue_next_phase": queue_next_phase.get("phase"),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *planned_steps,
                    *command_hints,
                    *skipped_steps,
                    *blocked_prerequisites,
                    *required_refreshed_artifacts,
                    *operator_review_items,
                    *safety_findings,
                    *launch_control_criteria,
                    *unresolved_items,
                    *required_human_review_actions,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "planned_dry_run_steps": planned_steps,
        "planned_records_only_steps": planned_steps,
        "inert_command_hints": command_hints,
        "skipped_steps": skipped_steps,
        "blocked_prerequisites": blocked_prerequisites,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "operator_review_items": operator_review_items,
        "safety_findings": safety_findings,
        "launch_control_criteria": launch_control_criteria,
        "unresolved_items": unresolved_items,
        "required_human_review_actions": required_human_review_actions,
        "required_operator_actions": required_human_review_actions,
        "queue_next_phase": queue_next_phase,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "final_next_cycle_launch_control_summary": _final_summary(
            launch_control_gate_state=launch_control_gate_state,
            source_artifacts=source_artifacts,
            planned_steps=planned_steps,
            command_hints=command_hints,
            skipped_steps=skipped_steps,
            blocked_prerequisites=blocked_prerequisites,
            required_refreshed_artifacts=required_refreshed_artifacts,
            operator_review_items=operator_review_items,
            safety_findings=safety_findings,
            launch_control_criteria=launch_control_criteria,
            unresolved_items=unresolved_items,
            required_human_review_actions=required_human_review_actions,
        ),
    }
    _validate_json_value("research_next_cycle_launch_control_gate_payload", payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_launch_control_gate(
    gate_input: ResearchNextCycleLaunchControlGateInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_launch_control_gate_payload(gate_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_launch_control_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_launch_control_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_next_cycle_launch_control_gate_payload", payload)
    lines = [
        "# 27A Next Cycle Launch Control Gate",
        "",
        f"launch control gate ID: {payload['launch_control_gate_id']}",
        f"launch control gate Date: {payload['launch_control_gate_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Acceptance State: {payload['acceptance_state']}",
        f"Launch-Control Gate State: {payload['launch_control_gate_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "next-cycle launch-control gates are read-only and records-only.",
        "Inert command hints are records only; commands are not executed and the next cycle is not run.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Next-Cycle Launch-Control Summary",
        "",
        payload["final_next_cycle_launch_control_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Planned dry-run steps", payload["summary"]["planned_dry_run_step_count"]),
        _summary_line("Planned records-only steps", payload["summary"]["planned_records_only_step_count"]),
        _summary_line("Inert command hints", payload["summary"]["command_hint_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Operator review items", payload["summary"]["operator_review_item_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Launch-Control Criteria", payload["summary"]["launch_control_criteria_count"]),
        _summary_line("Unresolved items", payload["summary"]["unresolved_item_count"]),
        _summary_line("Required human-review actions", payload["summary"]["required_human_review_action_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        "",
    ]
    lines.extend(_section("Source Artifact Status", payload["source_artifacts"]))
    lines.extend(_section("Planned Dry-Run Steps", payload["planned_dry_run_steps"]))
    lines.extend(_section("Planned Records-Only Steps", payload["planned_records_only_steps"]))
    lines.extend(_section("Inert Command Hints", payload["inert_command_hints"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"]))
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Operator Review Items", payload["operator_review_items"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Launch-Control Criteria", payload["launch_control_criteria"]))
    lines.extend(_section("Unresolved Items", payload["unresolved_items"]))
    lines.extend(_section("Required Human-Review Actions", payload["required_human_review_actions"]))
    lines.extend(_section("Required Operator Actions", payload["required_operator_actions"]))
    lines.extend(_section("Queue Next Phase", [payload["queue_next_phase"]]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY launch control gate generation only.",
            "- MONITOR_ONLY and PAPER_ONLY workflows are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only gate; no command execution, next-cycle run, artifact mutation, artifact deletion, broker action, trade instruction, execution permission, live-trading enablement, or order path submission is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(gate_input: ResearchNextCycleLaunchControlGateInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("acceptance_packet", "26B Next Cycle Acceptance Packet", gate_input.acceptance_packet_path),
        ("operator_acceptance_gate", "26A Next Cycle Operator Acceptance Gate", gate_input.operator_acceptance_gate_path),
        ("dry_run_manifest", "25B Next Cycle Dry Run Manifest", gate_input.dry_run_manifest_path),
        ("safety_preflight", "25A Next Cycle Safety Preflight", gate_input.safety_preflight_path),
        ("next_cycle_plan", "24B Next Research Cycle Plan", gate_input.next_cycle_plan_path),
        ("rollover_gate", "24A Research Cycle Rollover Gate", gate_input.rollover_gate_path),
        ("archive_index", "23B Research Cycle Archive Index", gate_input.archive_index_path),
        ("operations_console", "23A Research Operations Console", gate_input.operations_console_path),
        ("report_index", "Report Index", gate_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", gate_input.safe_workflow_catalog_path),
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


def _planned_dry_run_steps(
    source_payloads: dict[str, dict[str, Any]],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    source_steps = source_payloads.get("operator_acceptance_gate", {}).get("planned_next_cycle_steps", [])
    if not isinstance(source_steps, list) or not source_steps:
        source_steps = source_payloads.get("dry_run_manifest", {}).get("planned_next_cycle_steps", [])
    steps = []
    if isinstance(source_steps, list):
        for index, item in enumerate(source_steps, start=1):
            if not isinstance(item, dict):
                continue
            phase = item.get("phase") or f"planned_{index}"
            steps.append(
                {
                    "step_id": f"27A-DRY-RUN-STEP-{phase}",
                    "source_step_id": item.get("step_id"),
                    "phase": phase,
                    "title": item.get("title") or item.get("workflow") or "Planned dry-run step",
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": "recorded_not_started",
                    "summary": item.get("summary", "Planned dry-run step accepted as an inert record."),
                    "would_run": False,
                    "run_started": False,
                    "executed": False,
                    "records_only": True,
                    "human_review_required": True,
                }
            )
    if not steps:
        next_phase = queue_status.get("next_phase")
        if isinstance(next_phase, dict):
            steps.append(
                {
                    "step_id": f"27A-DRY-RUN-STEP-{next_phase.get('phase') or 'NEXT'}",
                    "source_step_id": None,
                    "phase": next_phase.get("phase"),
                    "title": next_phase.get("title", "Queued next phase"),
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "queue_recorded_not_started",
                    "summary": next_phase.get("summary", "Queued next phase recorded as an inert dry-run step."),
                    "would_run": False,
                    "run_started": False,
                    "executed": False,
                    "records_only": True,
                    "human_review_required": True,
                }
            )
    return _dedupe_by_id(steps, "step_id")


def _command_hints(
    source_payloads: dict[str, dict[str, Any]],
    planned_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_hints = source_payloads.get("operator_acceptance_gate", {}).get("command_hints", [])
    hints = []
    if isinstance(source_hints, list):
        for index, item in enumerate(source_hints, start=1):
            if not isinstance(item, dict):
                continue
            hints.append(
                {
                    "hint_id": f"27A-HINT-{index}",
                    "source_hint_id": item.get("hint_id"),
                    "step_id": item.get("step_id"),
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": "inert_record_only",
                    "summary": item.get("summary", "Inert command hint recorded from 26A."),
                    "command_hint": item.get("command_hint") or item.get("command") or "",
                    "would_run": False,
                    "executed": False,
                    "records_only": True,
                }
            )
    if not hints:
        for step in planned_steps:
            hints.append(
                {
                    "hint_id": f"27A-HINT-{step['step_id']}",
                    "source_hint_id": None,
                    "step_id": step["step_id"],
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "inert_record_only",
                    "summary": f"Inert operator hint for {step.get('phase') or step['step_id']}; no command is executed.",
                    "command_hint": f"review gate for {step.get('phase') or step['step_id']}",
                    "would_run": False,
                    "executed": False,
                    "records_only": True,
                }
            )
    return _dedupe_by_id(hints, "hint_id")


def _skipped_steps(planned_steps: list[dict[str, Any]], missing_artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label = BLOCKED_BY_SAFETY_GATE if missing_artifacts else PAPER_ONLY
    return _dedupe_by_id(
        [
            {
                "skipped_step_id": f"27A-SKIPPED-{step['step_id']}",
                "step_id": step["step_id"],
                "label": label,
                "status": "skipped_by_records_only_gate",
                "summary": "Step is recorded for launch-control review only and is not run by 27A.",
                "would_run": False,
                "run_started": False,
                "executed": False,
            }
            for step in planned_steps
        ],
        "skipped_step_id",
    )


def _blocked_prerequisites(
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked = [
        _blocked(f"missing_{item['artifact_id']}", f"{item['name']} is required before next-cycle launch control.")
        for item in missing_artifacts
    ]
    for artifact_id, payload in source_payloads.items():
        for key in ("blocked_prerequisites", "blocked_items", "blocked_workflows"):
            for item in _items_from_payload(payload, key):
                blocked.append(
                    _blocked(
                        f"{artifact_id}_{item.get('prerequisite_id') or item.get('workflow_id') or item.get('artifact_id') or key}",
                        item.get("summary", "Blocked prerequisite recorded by source artifact."),
                    )
                )
    if safety_scanner_status.get("passed") is False:
        blocked.append(_blocked("safety_scanner_not_passed", "Safety scanner must pass before launch control can proceed."))
    return _dedupe_by_id(blocked, "prerequisite_id")


def _required_refreshed_artifacts(
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    refreshes = [
        _refresh(f"refresh_missing_{item['artifact_id']}", item["artifact_id"], f"{item['name']} must be generated.")
        for item in missing_artifacts
    ]
    refreshes.extend(
        _refresh(f"refresh_stale_{item['artifact_id']}", item["artifact_id"], f"{item['name']} must be refreshed or accepted by operator review.")
        for item in stale_artifacts
    )
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "required_refreshed_artifacts"):
            refreshes.append(
                _refresh(
                    f"{artifact_id}_{item.get('refresh_id') or item.get('artifact_id') or 'refresh'}",
                    item.get("artifact_id", artifact_id),
                    item.get("summary", "Source artifact requires refresh before next-cycle launch control."),
                    item.get("label", HUMAN_REVIEW_REQUIRED),
                )
            )
    return _dedupe_by_id(refreshes, "refresh_id")


def _operator_review_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in REVIEW_KEYS:
            for index, item in enumerate(_items_from_payload(payload, key), start=1):
                items.append(
                    {
                        "review_item_id": f"{artifact_id}_{item.get('action_id') or item.get('review_item_id') or item.get('workflow_id') or key}_{index}",
                        "source_artifact_id": artifact_id,
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status", "open_review_item"),
                        "summary": item.get("summary", "Operator review item recorded by source artifact."),
                    }
                )
    return _dedupe_by_id(items, "review_item_id")


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "safety_findings"):
            findings.append(
                {
                    "finding_id": f"{artifact_id}_{item.get('finding_id') or item.get('rule_id') or item.get('workflow_id') or 'safety_finding'}",
                    "source_artifact_id": artifact_id,
                    "workflow_id": item.get("workflow_id", artifact_id),
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": item.get("status", "failed"),
                    "summary": item.get("summary", "Safety finding recorded by source artifact."),
                }
            )
    if safety_scanner_status.get("passed") is False or safety_scanner_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        findings.append(
            {
                "finding_id": "safety_scanner_status",
                "source_artifact_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": safety_scanner_status.get("status", "failed"),
                "summary": safety_scanner_status.get("summary", "Safety scanner status requires review."),
            }
        )
    for finding in safety_scanner_status.get("findings", []):
        if not isinstance(finding, dict):
            continue
        findings.append(
            {
                "finding_id": finding.get("rule_id") or finding.get("finding_id") or "safety_finding",
                "source_artifact_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": finding.get("summary") or finding.get("message") or "Safety scanner finding recorded.",
            }
        )
    return _dedupe_by_id(findings, "finding_id")


def _unresolved_items(
    source_payloads: dict[str, dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in ("unresolved_items", "unresolved_operator_review_items", "open_items"):
            for index, item in enumerate(_items_from_payload(payload, key), start=1):
                items.append(
                    {
                        "unresolved_item_id": f"{artifact_id}_{item.get('unresolved_item_id') or item.get('review_item_id') or key}_{index}",
                        "source_artifact_id": artifact_id,
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status", "unresolved"),
                        "summary": item.get("summary", "Unresolved item recorded by source artifact."),
                    }
                )
    items.extend(
        {
            "unresolved_item_id": f"blocked_{item['prerequisite_id']}",
            "source_artifact_id": "blocked_prerequisites",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "unresolved",
            "summary": item["summary"],
        }
        for item in blocked_prerequisites
    )
    items.extend(
        {
            "unresolved_item_id": f"refresh_{item['refresh_id']}",
            "source_artifact_id": "required_refreshed_artifacts",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "unresolved",
            "summary": item["summary"],
        }
        for item in required_refreshed_artifacts
    )
    return _dedupe_by_id(items, "unresolved_item_id")


def _required_human_review_actions(
    *,
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions = [
        _action("27A-HUMAN-REVIEW-SAFETY-BOUNDARY", "Confirm 27A remains records-only and LIVE TRADING: DISABLED."),
        _action("27A-HUMAN-REVIEW-LAUNCH-CONTROL-STATE", "Review Launch-Control Gate State before any separate future workflow is considered."),
    ]
    if blocked_prerequisites:
        actions.append(_action("27A-HUMAN-REVIEW-BLOCKED-PREREQUISITES", f"Review {len(blocked_prerequisites)} blocked prerequisites."))
    if required_refreshed_artifacts:
        actions.append(_action("27A-HUMAN-REVIEW-REFRESHED-ARTIFACTS", f"Refresh or explicitly accept {len(required_refreshed_artifacts)} artifacts."))
    if operator_review_items:
        actions.append(_action("27A-HUMAN-REVIEW-OPERATOR-ITEMS", f"Review {len(operator_review_items)} operator review items."))
    if safety_findings:
        actions.append(_action("27A-HUMAN-REVIEW-SAFETY-FINDINGS", f"Resolve {len(safety_findings)} safety findings."))
    if unresolved_items:
        actions.append(_action("27A-HUMAN-REVIEW-UNRESOLVED-ITEMS", f"Resolve or accept {len(unresolved_items)} unresolved items."))
    return _dedupe_by_id(actions, "action_id")


def _launch_control_criteria(
    *,
    planned_steps: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _criterion("27A-ACCEPT-RECORDS-ONLY", "27A produces deterministic JSON and Markdown records only.", RESEARCH_ONLY),
            _criterion("27A-ACCEPT-NO-WORKFLOW-START", "The next cycle is not run and no workflow is started.", HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-INERT-COMMAND-HINTS", f"{len(command_hints)} command hints are inert records with executed=false.", HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-PLANNED-DRY-RUN-STEPS", f"{len(planned_steps)} planned dry-run steps are recorded with would_run=false.", PAPER_ONLY),
            _criterion("27A-ACCEPT-SKIPPED-STEPS", f"{len(skipped_steps)} steps are explicitly skipped by the records-only gate.", PAPER_ONLY),
            _criterion("27A-ACCEPT-BLOCKED-PREREQUISITES", f"Blocked prerequisite count is {len(blocked_prerequisites)} and remains blocked.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-REFRESHED-ARTIFACTS", f"Required refreshed artifact count is {len(required_refreshed_artifacts)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-OPERATOR-REVIEW", f"Operator review item count is {len(operator_review_items)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-SAFETY-FINDINGS", f"Safety finding count is {len(safety_findings)}.", BLOCKED_BY_SAFETY_GATE if safety_findings else HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-UNRESOLVED-ITEMS", f"Unresolved item count is {len(unresolved_items)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("27A-ACCEPT-LIVE-TRADING-DISABLED", "LIVE TRADING: DISABLED is present and no broker/order path is created.", HUMAN_REVIEW_REQUIRED),
        ],
        "criterion_id",
    )


def _launch_control_gate_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
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
    if stale_artifacts or operator_review_items or unresolved_items:
        return NEEDS_OPERATOR_REVIEW
    return LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW


def _source_acceptance_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    packet_payload = source_payloads.get("acceptance_packet", {})
    value = packet_payload.get("acceptance_state")
    if isinstance(value, str) and value.strip():
        return value
    operator_payload = source_payloads.get("operator_acceptance_gate", {})
    value = operator_payload.get("operator_acceptance_gate_state")
    if isinstance(value, str) and value.strip():
        return value
    return "ACCEPTANCE_STATE_NOT_SUPPLIED"


def _queue_next_phase(queue_status: dict[str, Any]) -> dict[str, Any]:
    next_phase = queue_status.get("next_phase")
    if not isinstance(next_phase, dict):
        return {
            "workflow_id": "queue_next_phase",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_available",
            "phase": None,
            "title": "Queue next phase not available",
            "summary": "No queue next phase was available to 27A.",
            "run_started": False,
        }
    value = {
        "workflow_id": "queue_next_phase",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "planned_not_started",
        "phase": next_phase.get("phase"),
        "title": next_phase.get("title"),
        "summary": next_phase.get("summary") or "Queue next phase recorded for launch-control review only.",
        "run_started": False,
    }
    _validate_json_value("queue_next_phase", value)
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
        "summary": "Master plan queue read for 27A launch control gate context only.",
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
            "summary": "Safety scanner status was not supplied to 27A.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 27A."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "records_only": True,
        "read_only": True,
        "dry_run_only": True,
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


def _final_summary(
    *,
    launch_control_gate_state: str,
    source_artifacts: list[dict[str, Any]],
    planned_steps: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    launch_control_criteria: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
    required_human_review_actions: list[dict[str, Any]],
) -> str:
    present = len([item for item in source_artifacts if item["status"] == "present"])
    return (
        f"Next-cycle Launch-Control Gate State is {launch_control_gate_state}. "
        f"Source artifact status: {present}/{len(source_artifacts)} present. "
        f"Planned dry-run steps: {len(planned_steps)}. "
        f"Inert command hints: {len(command_hints)}. "
        f"Skipped steps: {len(skipped_steps)}. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Operator review items: {len(operator_review_items)}. "
        f"Safety findings: {len(safety_findings)}. "
        f"Launch-Control Criteria: {len(launch_control_criteria)}. "
        f"Unresolved items: {len(unresolved_items)}. "
        f"Required human-review actions: {len(required_human_review_actions)}. "
        "Safety boundary confirmed: 27A is read-only and records-only and does not execute commands, run the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, grant execution permissions, or submit any order path. "
        "LIVE TRADING: DISABLED."
    )


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
        if item.get("phase") == "27A":
            return item
    return items[0] if items else None


def _refresh(refresh_id: str, artifact_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "refresh_id": refresh_id,
        "artifact_id": artifact_id,
        "label": label,
        "status": "required_before_acceptance",
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
        "status": "launch_control_required",
        "summary": summary,
    }


def _action(action_id: str, summary: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "open_review_item",
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
    gate_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for item in source_artifacts:
        if item["status"] != "present":
            continue
        age_days = _age_days(gate_day, item.get("generated_date"))
        if age_days is None or age_days > max_source_age_days:
            stale.append(
                {
                    "artifact_id": item["artifact_id"],
                    "name": item["name"],
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "stale_or_unknown_date",
                    "summary": f"{item['name']} is stale or has no recognized generated date.",
                    "path": item["path"],
                    "generated_date": item.get("generated_date"),
                    "age_days": age_days,
                }
            )
    return _dedupe_by_id(stale, "artifact_id")


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_gate_path(path)
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
            item.get("step_id")
            or item.get("hint_id")
            or item.get("artifact_id")
            or item.get("skipped_step_id")
            or item.get("prerequisite_id")
            or item.get("refresh_id")
            or item.get("review_item_id")
            or item.get("finding_id")
            or item.get("criterion_id")
            or item.get("unresolved_item_id")
            or item.get("action_id")
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
            or item.get("unresolved_item_id")
            or item.get("action_id")
            or item.get("workflow_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_gate_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research Next Cycle Launch Control Gate cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research Next Cycle Launch Control Gate cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research Next Cycle Launch Control Gate paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research Next Cycle Launch Control Gate paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_LAUNCH_CONTROL_LABELS:
            raise ValueError(f"unsafe research Next Cycle Launch Control Gate label: {label}")
        state = value.get("launch_control_gate_state")
        if state is not None and state not in LAUNCH_CONTROL_STATES:
            raise ValueError(f"invalid research Next Cycle Launch Control Gate state: {state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research Next Cycle Launch Control Gate cannot set {unsafe_field}")
        for mutation_field in ("artifact_delete_performed", "artifact_mutation_performed", "commands_executed"):
            if value.get(mutation_field) is True:
                raise ValueError(f"research Next Cycle Launch Control Gate cannot set {mutation_field}")
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
        if value in DISALLOWED_LAUNCH_CONTROL_LABELS:
            raise ValueError(f"disallowed research Next Cycle Launch Control Gate text: {value}")
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
