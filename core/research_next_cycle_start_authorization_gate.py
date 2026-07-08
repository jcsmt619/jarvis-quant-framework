from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.report_index import REPORT_INDEX_JSON
from core.research_next_cycle_acceptance_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_JSON,
)
from core.research_next_cycle_dry_run_manifest import (
    DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR,
    RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON,
)
from core.research_next_cycle_launch_control_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_DIR,
    RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_JSON,
)
from core.research_next_cycle_operator_handoff_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_JSON,
)
from core.research_next_cycle_plan import (
    DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
    RESEARCH_NEXT_CYCLE_PLAN_JSON,
)
from core.research_next_cycle_safety_preflight import (
    DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR,
    RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON,
)
from core.research_next_cycle_start_preconditions_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_DIR,
    RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_JSON,
    _age_days,
    _artifact_summary,
    _count_by,
    _dedupe_by_id,
    _items_from_payload,
    _normalize_json_value,
    _parse_iso_date,
    _parse_iso_datetime,
    _read_json_object,
    _read_json_value,
    _section,
    _summary_line,
    _validate_gate_path,
    _validate_json_value,
    _without_payload,
)
from core.research_next_cycle_start_checklist_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR = Path(
    "reports/research_next_cycle_start_authorization_gate"
)
RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_JSON = "research_next_cycle_start_authorization_gate.json"
RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_MARKDOWN = "research_next_cycle_start_authorization_gate.md"

START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW = "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"

SAFE_START_AUTHORIZATION_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
START_AUTHORIZATION_GATE_STATES = (
    START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)


@dataclass(frozen=True)
class ResearchNextCycleStartAuthorizationGateInput:
    start_authorization_gate_id: str
    start_authorization_gate_date: str
    generated_at_utc: str
    start_checklist_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_DIR
        / RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_JSON
    )
    start_preconditions_gate_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_DIR
        / RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_JSON
    )
    operator_handoff_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_DIR
        / RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_JSON
    )
    launch_control_gate_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_DIR / RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_JSON
    )
    acceptance_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_DIR / RESEARCH_NEXT_CYCLE_ACCEPTANCE_PACKET_JSON
    )
    dry_run_manifest_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR / RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_JSON
    )
    safety_preflight_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR / RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON
    )
    next_cycle_plan_path: Path = DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR / RESEARCH_NEXT_CYCLE_PLAN_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("start_authorization_gate_id", "start_authorization_gate_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research Next Cycle Start Authorization Gate requires {field_name}")
        _parse_iso_date("start_authorization_gate_date", self.start_authorization_gate_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.start_checklist_packet_path,
            self.start_preconditions_gate_path,
            self.operator_handoff_packet_path,
            self.launch_control_gate_path,
            self.acceptance_packet_path,
            self.dry_run_manifest_path,
            self.safety_preflight_path,
            self.next_cycle_plan_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_gate_path(path)


def build_default_research_next_cycle_start_authorization_gate_input(
    *,
    start_authorization_gate_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCycleStartAuthorizationGateInput:
    generated = now or datetime.now(tz=UTC)
    day = start_authorization_gate_date or generated.date()
    return ResearchNextCycleStartAuthorizationGateInput(
        start_authorization_gate_id=f"29A-RESEARCH-NEXT-CYCLE-START-AUTHORIZATION-GATE-{day.isoformat()}",
        start_authorization_gate_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_start_authorization_gate_payload(
    packet_input: ResearchNextCycleStartAuthorizationGateInput,
) -> dict[str, Any]:
    packet_input.validate()
    packet_day = datetime.strptime(packet_input.start_authorization_gate_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(packet_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    queue_status = _queue_status(packet_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(packet_input.safety_scanner_path)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, packet_day, packet_input.max_source_age_days)
    source_artifact_status = _source_artifact_status(source_artifacts)
    checklist_state = _checklist_state(source_payloads)
    precondition_state = _precondition_state(source_payloads)
    handoff_state = _handoff_state(source_payloads)
    launch_control_state = _launch_control_state(source_payloads)
    acceptance_state = _acceptance_state(source_payloads)
    dry_run_state = _dry_run_state(source_payloads)
    planned_steps = _planned_records_only_steps(source_payloads, queue_status)
    command_hints = _inert_command_hints(source_payloads, planned_steps)
    blocked_prerequisites = _blocked_prerequisites(source_payloads, missing_artifacts, safety_scanner_status)
    unresolved_review_items = _unresolved_review_items(source_payloads, blocked_prerequisites, stale_artifacts)
    required_refreshed_artifacts = _required_refreshed_artifacts(missing_artifacts, stale_artifacts, source_payloads)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    queue_next_phase = _queue_next_phase(queue_status)
    required_operator_actions = _required_operator_actions(
        checklist_state=checklist_state,
        precondition_state=precondition_state,
        handoff_state=handoff_state,
        launch_control_state=launch_control_state,
        acceptance_state=acceptance_state,
        dry_run_state=dry_run_state,
        source_artifact_status=source_artifact_status,
        command_hints=command_hints,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_review_items=unresolved_review_items,
        required_refreshed_artifacts=required_refreshed_artifacts,
        safety_findings=safety_findings,
        queue_next_phase=queue_next_phase,
    )
    acceptance_criteria = _acceptance_criteria(
        planned_steps=planned_steps,
        command_hints=command_hints,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_review_items=unresolved_review_items,
        required_refreshed_artifacts=required_refreshed_artifacts,
        safety_findings=safety_findings,
        required_operator_actions=required_operator_actions,
    )
    start_authorization_gate_state = _start_authorization_gate_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_review_items=unresolved_review_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "29A",
        "workflow": "Next Cycle Start Authorization Gate",
        "start_authorization_gate_id": packet_input.start_authorization_gate_id,
        "start_authorization_gate_date": packet_input.start_authorization_gate_date,
        "generated_at_utc": packet_input.generated_at_utc,
        "checklist_state": checklist_state,
        "precondition_state": precondition_state,
        "handoff_state": handoff_state,
        "launch_control_state": launch_control_state,
        "acceptance_state": acceptance_state,
        "dry_run_state": dry_run_state,
        "start_authorization_gate_state": start_authorization_gate_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_START_AUTHORIZATION_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "planned_records_only_step_count": len(planned_steps),
            "command_hint_count": len(command_hints),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "unresolved_review_item_count": len(unresolved_review_items),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "safety_finding_count": len(safety_findings),
            "required_operator_action_count": len(required_operator_actions),
            "acceptance_criteria_count": len(acceptance_criteria),
            "checklist_state": checklist_state,
            "precondition_state": precondition_state,
            "handoff_state": handoff_state,
            "launch_control_state": launch_control_state,
            "acceptance_state": acceptance_state,
            "dry_run_state": dry_run_state,
            "queue_next_phase": queue_next_phase.get("phase"),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *source_artifact_status,
                    *planned_steps,
                    *command_hints,
                    *blocked_prerequisites,
                    *unresolved_review_items,
                    *required_refreshed_artifacts,
                    *safety_findings,
                    *required_operator_actions,
                    *acceptance_criteria,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "source_artifact_status": source_artifact_status,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "planned_records_only_steps": planned_steps,
        "inert_command_hints": command_hints,
        "blocked_prerequisites": blocked_prerequisites,
        "unresolved_review_items": unresolved_review_items,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "safety_findings": safety_findings,
        "queue_next_phase": queue_next_phase,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "required_operator_actions": required_operator_actions,
        "acceptance_criteria": acceptance_criteria,
        "final_next_cycle_start_authorization": _final_authorization(
            start_authorization_gate_state=start_authorization_gate_state,
            checklist_state=checklist_state,
            precondition_state=precondition_state,
            handoff_state=handoff_state,
            launch_control_state=launch_control_state,
            acceptance_state=acceptance_state,
            dry_run_state=dry_run_state,
            source_artifacts=source_artifacts,
            planned_steps=planned_steps,
            command_hints=command_hints,
            blocked_prerequisites=blocked_prerequisites,
            unresolved_review_items=unresolved_review_items,
            required_refreshed_artifacts=required_refreshed_artifacts,
            safety_findings=safety_findings,
            queue_next_phase=queue_next_phase,
            required_operator_actions=required_operator_actions,
            acceptance_criteria=acceptance_criteria,
        ),
    }
    _validate_start_authorization_payload(payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_start_authorization_gate(
    packet_input: ResearchNextCycleStartAuthorizationGateInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_start_authorization_gate_payload(packet_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_start_authorization_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_start_authorization_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_start_authorization_payload(payload)
    lines = [
        "# 29A Next Cycle Start Authorization Gate",
        "",
        f"Start Authorization Gate ID: {payload['start_authorization_gate_id']}",
        f"Start Authorization Gate Date: {payload['start_authorization_gate_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Checklist State: {payload['checklist_state']}",
        f"Precondition State: {payload['precondition_state']}",
        f"Handoff State: {payload['handoff_state']}",
        f"Launch-Control State: {payload['launch_control_state']}",
        f"Acceptance State: {payload['acceptance_state']}",
        f"Dry-Run State: {payload['dry_run_state']}",
        f"Start Authorization Gate State: {payload['start_authorization_gate_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Next-cycle Start Authorization Gates are read-only and records-only.",
        "Inert command hints are records only; commands are not executed and the next cycle is not run.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Next-Cycle Start Authorization",
        "",
        payload["final_next_cycle_start_authorization"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Planned records-only steps", payload["summary"]["planned_records_only_step_count"]),
        _summary_line("Inert command hints", payload["summary"]["command_hint_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Unresolved review items", payload["summary"]["unresolved_review_item_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        _summary_line("Acceptance criteria", payload["summary"]["acceptance_criteria_count"]),
        "",
    ]
    lines.extend(
        _section(
            "Source States",
            [
                {"workflow_id": "checklist_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["checklist_state"], "summary": "28B checklist state recorded."},
                {"workflow_id": "precondition_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["precondition_state"], "summary": "28A precondition state recorded."},
                {"workflow_id": "handoff_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["handoff_state"], "summary": "27B handoff state recorded."},
                {"workflow_id": "launch_control_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["launch_control_state"], "summary": "27A launch-control state recorded."},
                {"workflow_id": "acceptance_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["acceptance_state"], "summary": "26B acceptance state recorded."},
                {"workflow_id": "dry_run_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["dry_run_state"], "summary": "25B dry-run state recorded."},
            ],
        )
    )
    lines.extend(_section("Source Artifact Status", payload["source_artifact_status"]))
    lines.extend(_section("Inert Command Hints", payload["inert_command_hints"]))
    lines.extend(_section("Planned Records-Only Steps", payload["planned_records_only_steps"]))
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Unresolved Review Items", payload["unresolved_review_items"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Queue Next Phase", [payload["queue_next_phase"]]))
    lines.extend(_section("Required Operator Actions", payload["required_operator_actions"]))
    lines.extend(_section("Acceptance Criteria", payload["acceptance_criteria"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY authorization gate generation only.",
            "- MONITOR_ONLY and PAPER_ONLY workflows are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only gate; no command execution, next-cycle start, artifact mutation, artifact deletion, broker action, trade instruction, execution permission, live-trading enablement, broker route, broker call, or order path submission is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(packet_input: ResearchNextCycleStartAuthorizationGateInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("start_checklist_packet", "28B Next Cycle Start Checklist Packet", packet_input.start_checklist_packet_path),
        ("start_preconditions_gate", "28A Next Cycle Start Preconditions Gate", packet_input.start_preconditions_gate_path),
        ("operator_handoff_packet", "27B Next Cycle Operator Handoff Packet", packet_input.operator_handoff_packet_path),
        ("launch_control_gate", "27A Next Cycle Launch Control Gate", packet_input.launch_control_gate_path),
        ("acceptance_packet", "26B Next Cycle Acceptance Packet", packet_input.acceptance_packet_path),
        ("dry_run_manifest", "25B Next Cycle Dry Run Manifest", packet_input.dry_run_manifest_path),
        ("safety_preflight", "25A Next Cycle Safety Preflight", packet_input.safety_preflight_path),
        ("next_cycle_plan", "24B Next Research Cycle Plan", packet_input.next_cycle_plan_path),
        ("report_index", "Report Index", packet_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", packet_input.safe_workflow_catalog_path),
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


def _source_artifact_status(source_artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            {
                "artifact_id": item["artifact_id"],
                "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                "status": item["status"],
                "summary": item["summary"],
                "path": item["path"],
                "phase": item.get("phase"),
                "workflow": item.get("workflow"),
            }
            for item in source_artifacts
        ],
        "artifact_id",
    )


def _planned_records_only_steps(
    source_payloads: dict[str, dict[str, Any]],
    queue_status: dict[str, Any],
) -> list[dict[str, Any]]:
    source_steps = []
    for artifact_id in ("start_preconditions_gate", "operator_handoff_packet", "launch_control_gate", "acceptance_packet", "dry_run_manifest"):
        payload = source_payloads.get(artifact_id, {})
        for key in ("planned_records_only_steps", "planned_dry_run_steps", "planned_next_cycle_steps"):
            values = payload.get(key, [])
            if isinstance(values, list):
                source_steps.extend((artifact_id, item) for item in values if isinstance(item, dict))
    steps = []
    for index, (artifact_id, item) in enumerate(source_steps, start=1):
        phase = item.get("phase") or f"planned_{index}"
        steps.append(
            {
                "step_id": f"29A-RECORDS-ONLY-STEP-{phase}-{index}",
                "source_artifact_id": artifact_id,
                "source_step_id": item.get("step_id"),
                "phase": phase,
                "title": item.get("title") or item.get("workflow") or "Planned records-only step",
                "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                "status": "recorded_not_started",
                "summary": item.get("summary", "Planned step recorded as inert checklist context only."),
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
                    "step_id": f"29A-RECORDS-ONLY-STEP-{next_phase.get('phase') or 'NEXT'}",
                    "source_artifact_id": "master_plan_queue",
                    "source_step_id": None,
                    "phase": next_phase.get("phase"),
                    "title": next_phase.get("title", "Queued next phase"),
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "queue_recorded_not_started",
                    "summary": next_phase.get("summary", "Queued next phase recorded as an inert records-only step."),
                    "would_run": False,
                    "run_started": False,
                    "executed": False,
                    "records_only": True,
                    "human_review_required": True,
                }
            )
    return _dedupe_by_id(steps, "step_id")


def _inert_command_hints(
    source_payloads: dict[str, dict[str, Any]],
    planned_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hints = []
    for artifact_id in ("start_preconditions_gate", "operator_handoff_packet", "launch_control_gate", "acceptance_packet", "dry_run_manifest"):
        values = source_payloads.get(artifact_id, {}).get("inert_command_hints", [])
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values, start=1):
            if not isinstance(item, dict):
                continue
            hints.append(
                {
                    "hint_id": f"29A-HINT-{artifact_id}-{index}",
                    "source_artifact_id": artifact_id,
                    "source_hint_id": item.get("hint_id"),
                    "step_id": item.get("step_id"),
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": "inert_record_only",
                    "summary": item.get("summary", "Inert command hint recorded for checklist context only."),
                    "command_hint": item.get("command_hint") or item.get("command") or "No command supplied.",
                    "would_run": False,
                    "executed": False,
                    "records_only": True,
                    "execution_permission_granted": False,
                }
            )
    if not hints:
        for index, step in enumerate(planned_steps, start=1):
            hints.append(
                {
                    "hint_id": f"29A-HINT-STEP-{index}",
                    "source_artifact_id": step.get("source_artifact_id"),
                    "source_hint_id": None,
                    "step_id": step["step_id"],
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "inert_record_only",
                    "summary": "No executable command is supplied; review the source artifact manually.",
                    "command_hint": "Review source artifact only; do not run a workflow from 29A.",
                    "would_run": False,
                    "executed": False,
                    "records_only": True,
                    "execution_permission_granted": False,
                }
            )
    return _dedupe_by_id(hints, "hint_id")


def _blocked_prerequisites(
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked = [
        _blocked(f"missing_{item['artifact_id']}", f"{item['name']} is required before start authorization.")
        for item in missing_artifacts
    ]
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "blocked_prerequisites"):
            blocked.append(
                _blocked(
                    f"{artifact_id}_{item.get('prerequisite_id', item.get('workflow_id', 'blocked'))}",
                    item.get("summary", "Source artifact reported a blocked prerequisite."),
                )
            )
    if safety_scanner_status.get("passed") is False:
        blocked.append(_blocked("safety_scanner_failed", "Safety scanner reported passed=false."))
    return _dedupe_by_id(blocked, "prerequisite_id")


def _unresolved_review_items(
    source_payloads: dict[str, dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in ("operator_review_items", "required_operator_actions", "required_human_review_actions", "unresolved_items"):
            for item in _items_from_payload(payload, key):
                items.append(
                    {
                        "review_item_id": f"29A-{artifact_id}-{key}-{item.get('review_item_id') or item.get('action_id') or item.get('unresolved_item_id') or len(items) + 1}",
                        "source_artifact_id": artifact_id,
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status", "open_review_item"),
                        "summary": item.get("summary", "Source artifact review item remains open."),
                    }
                )
    for item in blocked_prerequisites:
        items.append(
            {
                "review_item_id": f"29A-BLOCKED-{item['prerequisite_id']}",
                "source_artifact_id": "blocked_prerequisites",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "unresolved",
                "summary": item["summary"],
            }
        )
    for item in stale_artifacts:
        items.append(
            {
                "review_item_id": f"29A-STALE-{item['artifact_id']}",
                "source_artifact_id": item["artifact_id"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "refresh_required",
                "summary": item["summary"],
            }
        )
    return _dedupe_by_id(items, "review_item_id")


def _required_refreshed_artifacts(
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    refreshes = []
    for item in [*missing_artifacts, *stale_artifacts]:
        refreshes.append(
            {
                "refresh_id": f"29A-REFRESH-{item['artifact_id']}",
                "artifact_id": item["artifact_id"],
                "label": HUMAN_REVIEW_REQUIRED if item.get("status") != "missing" else BLOCKED_BY_SAFETY_GATE,
                "status": "required_before_acceptance",
                "summary": f"{item['name']} must be present and fresh before start authorization.",
            }
        )
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "required_refreshed_artifacts"):
            refreshes.append(
                {
                    "refresh_id": f"29A-SOURCE-REFRESH-{artifact_id}-{item.get('refresh_id', len(refreshes) + 1)}",
                    "artifact_id": item.get("artifact_id", artifact_id),
                    "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                    "status": item.get("status", "required_before_acceptance"),
                    "summary": item.get("summary", "Source artifact requires a refreshed artifact."),
                }
            )
    return _dedupe_by_id(refreshes, "refresh_id")


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "safety_findings"):
            findings.append(
                {
                    "finding_id": f"29A-{artifact_id}-{item.get('finding_id') or item.get('rule_id') or len(findings) + 1}",
                    "source_artifact_id": artifact_id,
                    "label": item.get("label", BLOCKED_BY_SAFETY_GATE),
                    "status": item.get("status", "recorded"),
                    "summary": item.get("summary", "Source artifact safety finding."),
                }
            )
    for item in safety_scanner_status.get("findings", []):
        if isinstance(item, dict):
            findings.append(
                {
                    "finding_id": item.get("finding_id") or item.get("rule_id") or f"safety_scanner_{len(findings) + 1}",
                    "source_artifact_id": "safety_scanner",
                    "label": item.get("label", BLOCKED_BY_SAFETY_GATE),
                    "status": item.get("status", "recorded"),
                    "summary": item.get("summary", "Safety scanner finding."),
                }
            )
    return _dedupe_by_id(findings, "finding_id")


def _required_operator_actions(
    *,
    checklist_state: str,
    precondition_state: str,
    handoff_state: str,
    launch_control_state: str,
    acceptance_state: str,
    dry_run_state: str,
    source_artifact_status: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_next_phase: dict[str, Any],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _action("29A-ACTION-CHECKLIST-STATE", f"Human operator reviews 28B checklist state: {checklist_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-PRECONDITION-STATE", f"Human operator reviews 28A precondition state: {precondition_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-HANDOFF-STATE", f"Human operator reviews 27B handoff state: {handoff_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-LAUNCH-CONTROL-STATE", f"Human operator reviews 27A launch-control state: {launch_control_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-ACCEPTANCE-STATE", f"Human operator reviews 26B acceptance state: {acceptance_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-DRY-RUN-STATE", f"Human operator reviews 25B dry-run state: {dry_run_state}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-SOURCE-ARTIFACTS", f"Human operator reviews {len(source_artifact_status)} source artifact statuses.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-INERT-COMMAND-HINTS", f"Human operator reviews {len(command_hints)} inert command hints with executed=false.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-BLOCKED-PREREQUISITES", f"Human operator reviews {len(blocked_prerequisites)} blocked prerequisites.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-UNRESOLVED-REVIEW", f"Human operator resolves or accepts {len(unresolved_review_items)} unresolved review items.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-REFRESHED-ARTIFACTS", f"Human operator refreshes or accepts {len(required_refreshed_artifacts)} required artifacts.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-SAFETY-FINDINGS", f"Human operator reviews {len(safety_findings)} safety findings.", BLOCKED_BY_SAFETY_GATE if safety_findings else HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-QUEUE-NEXT-PHASE", f"Human operator confirms queue next phase remains not started: {queue_next_phase.get('phase')}.", HUMAN_REVIEW_REQUIRED),
            _action("29A-ACTION-LIVE-TRADING-DISABLED", "Human operator confirms LIVE TRADING: DISABLED; no execution permission, broker route, broker call, or order path is created.", HUMAN_REVIEW_REQUIRED),
        ],
        "action_id",
    )


def _acceptance_criteria(
    *,
    planned_steps: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    required_operator_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _criterion("29A-ACCEPT-RECORDS-ONLY", "29A produces deterministic JSON and Markdown records only.", RESEARCH_ONLY),
            _criterion("29A-ACCEPT-NO-WORKFLOW-START", "The next cycle is not run and no workflow is started.", HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-INERT-COMMAND-HINTS", f"{len(command_hints)} command hints are inert records with executed=false.", HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-PLANNED-STEPS", f"{len(planned_steps)} planned records-only steps are recorded with would_run=false.", PAPER_ONLY),
            _criterion("29A-ACCEPT-BLOCKED-PREREQUISITES", f"Blocked prerequisite count is {len(blocked_prerequisites)} and remains blocked.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-UNRESOLVED-REVIEW", f"Unresolved review item count is {len(unresolved_review_items)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-REFRESHED-ARTIFACTS", f"Required refreshed artifact count is {len(required_refreshed_artifacts)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-SAFETY-FINDINGS", f"Safety finding count is {len(safety_findings)}.", BLOCKED_BY_SAFETY_GATE if safety_findings else HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-OPERATOR-ACTIONS", f"Required operator action count is {len(required_operator_actions)}.", HUMAN_REVIEW_REQUIRED),
            _criterion("29A-ACCEPT-LIVE-TRADING-DISABLED", "LIVE TRADING: DISABLED is present and no broker/order path is created.", HUMAN_REVIEW_REQUIRED),
        ],
        "criterion_id",
    )


def _source_state(
    source_payloads: dict[str, dict[str, Any]],
    artifact_id: str,
    state_key: str,
    fallback: str,
) -> str:
    payload = source_payloads.get(artifact_id, {})
    value = payload.get(state_key)
    return value if isinstance(value, str) and value.strip() else fallback


def _checklist_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "start_checklist_packet",
        "start_checklist_packet_state",
        "START_CHECKLIST_STATE_NOT_SUPPLIED",
    )


def _precondition_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "start_preconditions_gate",
        "start_preconditions_gate_state",
        "START_PRECONDITIONS_STATE_NOT_SUPPLIED",
    )


def _handoff_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "operator_handoff_packet",
        "operator_handoff_packet_state",
        "OPERATOR_HANDOFF_STATE_NOT_SUPPLIED",
    )


def _launch_control_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "launch_control_gate",
        "launch_control_gate_state",
        "LAUNCH_CONTROL_STATE_NOT_SUPPLIED",
    )


def _acceptance_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "acceptance_packet",
        "acceptance_state",
        "ACCEPTANCE_STATE_NOT_SUPPLIED",
    )


def _dry_run_state(source_payloads: dict[str, dict[str, Any]]) -> str:
    return _source_state(
        source_payloads,
        "dry_run_manifest",
        "dry_run_manifest_state",
        "DRY_RUN_STATE_NOT_SUPPLIED",
    )


def _start_authorization_gate_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
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
    if stale_artifacts or unresolved_review_items:
        return NEEDS_OPERATOR_REVIEW
    return START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW


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
        "summary": "Master plan queue read for 29A Start Authorization Gate context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": _next_phase(items),
        "items": items,
    }
    _validate_json_value("queue_status", value)
    return _normalize_json_value(value)


def _queue_next_phase(queue_status: dict[str, Any]) -> dict[str, Any]:
    next_phase = queue_status.get("next_phase")
    if not isinstance(next_phase, dict):
        return {
            "workflow_id": "queue_next_phase",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_available",
            "phase": None,
            "title": "Queue next phase not available",
            "summary": "No queue next phase was available to 29A.",
            "run_started": False,
        }
    value = {
        "workflow_id": "queue_next_phase",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "planned_not_started",
        "phase": next_phase.get("phase"),
        "title": next_phase.get("title"),
        "summary": next_phase.get("summary") or "Queue next phase recorded for Start Authorization review only.",
        "run_started": False,
    }
    _validate_json_value("queue_next_phase", value)
    return _normalize_json_value(value)


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to 29A.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 29A."),
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


def _final_authorization(
    *,
    start_authorization_gate_state: str,
    checklist_state: str,
    precondition_state: str,
    handoff_state: str,
    launch_control_state: str,
    acceptance_state: str,
    dry_run_state: str,
    source_artifacts: list[dict[str, Any]],
    planned_steps: list[dict[str, Any]],
    command_hints: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_next_phase: dict[str, Any],
    required_operator_actions: list[dict[str, Any]],
    acceptance_criteria: list[dict[str, Any]],
) -> str:
    present = len([item for item in source_artifacts if item["status"] == "present"])
    return (
        f"Next-cycle Start Authorization Gate State is {start_authorization_gate_state}. "
        f"Checklist state is {checklist_state}. "
        f"Precondition state is {precondition_state}. "
        f"Handoff state is {handoff_state}. "
        f"Launch-control state is {launch_control_state}. "
        f"Acceptance state is {acceptance_state}. "
        f"Dry-run state is {dry_run_state}. "
        f"Source artifact status: {present}/{len(source_artifacts)} present. "
        f"Inert command hints: {len(command_hints)}. "
        f"Planned records-only steps: {len(planned_steps)}. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Unresolved review items: {len(unresolved_review_items)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Safety findings: {len(safety_findings)}. "
        f"Queue next phase: {queue_next_phase.get('phase')}. "
        f"Required operator actions: {len(required_operator_actions)}. "
        f"Acceptance criteria: {len(acceptance_criteria)}. "
        "Safety boundary confirmed: 29A is read-only and records-only and does not execute commands, start the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, grant execution permissions, route broker orders, call broker endpoints, or submit any order path. "
        "LIVE TRADING: DISABLED."
    )


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    packet_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for item in source_artifacts:
        if item["status"] != "present":
            continue
        age_days = _age_days(packet_day, item.get("generated_date"))
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
        if item.get("phase") == "29A":
            return item
    return items[0] if items else None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "start_authorization_gate_date",
        "start_checklist_packet_date",
        "start_preconditions_gate_date",
        "operator_handoff_packet_date",
        "launch_control_gate_date",
        "acceptance_packet_date",
        "dry_run_manifest_date",
        "preflight_date",
        "next_cycle_plan_date",
        "index_date",
        "catalog_date",
        "report_date",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value[:10]
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


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
        "status": "start_authorization_acceptance_required",
        "summary": summary,
    }


def _action(action_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": label,
        "status": "operator_authorization_review_required",
        "summary": summary,
        "records_only": True,
        "execution_permission_granted": False,
        "run_started": False,
    }


def _validate_start_authorization_payload(value: Any) -> None:
    _validate_json_value("research_next_cycle_start_authorization_gate_payload", value)
    _validate_start_authorization_state(value)


def _validate_start_authorization_state(value: Any) -> None:
    if isinstance(value, dict):
        state = value.get("start_authorization_gate_state")
        if state is not None and state not in START_AUTHORIZATION_GATE_STATES:
            raise ValueError(f"invalid research Next Cycle Start Authorization Gate state: {state}")
        for item in value.values():
            _validate_start_authorization_state(item)
    elif isinstance(value, list):
        for item in value:
            _validate_start_authorization_state(item)
