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
from core.research_next_cycle_frozen_launch_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_LAUNCH_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_FROZEN_LAUNCH_PACKET_JSON,
    _blocked_prerequisites,
    _inert_command_hints,
    _required_refreshed_artifacts,
    _safety_findings,
    _source_state,
    _stale_artifacts,
    _unresolved_review_items,
)
from core.research_next_cycle_launch_control_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_DIR,
    RESEARCH_NEXT_CYCLE_LAUNCH_CONTROL_GATE_JSON,
)
from core.research_next_cycle_operator_handoff_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_OPERATOR_HANDOFF_PACKET_JSON,
)
from core.research_next_cycle_start_authorization_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR,
    RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_JSON,
)
from core.research_next_cycle_start_checklist_packet import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_DIR,
    RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_JSON,
)
from core.research_next_cycle_start_preconditions_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_DIR,
    RESEARCH_NEXT_CYCLE_START_PRECONDITIONS_GATE_JSON,
    _artifact_summary,
    _count_by,
    _dedupe_by_id,
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
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_DIR = Path(
    "reports/research_next_cycle_frozen_start_review_gate"
)
RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_JSON = "research_next_cycle_frozen_start_review_gate.json"
RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_MARKDOWN = "research_next_cycle_frozen_start_review_gate.md"

FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW = "FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"

SAFE_FROZEN_START_REVIEW_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
FROZEN_START_REVIEW_STATES = (
    FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)


@dataclass(frozen=True)
class ResearchNextCycleFrozenStartReviewGateInput:
    frozen_start_review_gate_id: str
    frozen_start_review_gate_date: str
    generated_at_utc: str
    frozen_launch_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_LAUNCH_PACKET_DIR / RESEARCH_NEXT_CYCLE_FROZEN_LAUNCH_PACKET_JSON
    )
    start_authorization_gate_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR
        / RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_JSON
    )
    start_checklist_packet_path: Path = (
        DEFAULT_RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_DIR / RESEARCH_NEXT_CYCLE_START_CHECKLIST_PACKET_JSON
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
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("frozen_start_review_gate_id", "frozen_start_review_gate_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research Next Cycle Frozen Start Review Gate requires {field_name}")
        _parse_iso_date("frozen_start_review_gate_date", self.frozen_start_review_gate_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.frozen_launch_packet_path,
            self.start_authorization_gate_path,
            self.start_checklist_packet_path,
            self.start_preconditions_gate_path,
            self.operator_handoff_packet_path,
            self.launch_control_gate_path,
            self.acceptance_packet_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_gate_path(path)


def build_default_research_next_cycle_frozen_start_review_gate_input(
    *,
    frozen_start_review_gate_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCycleFrozenStartReviewGateInput:
    generated = now or datetime.now(tz=UTC)
    day = frozen_start_review_gate_date or generated.date()
    return ResearchNextCycleFrozenStartReviewGateInput(
        frozen_start_review_gate_id=f"30A-RESEARCH-NEXT-CYCLE-FROZEN-START-REVIEW-GATE-{day.isoformat()}",
        frozen_start_review_gate_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_frozen_start_review_gate_payload(
    gate_input: ResearchNextCycleFrozenStartReviewGateInput,
) -> dict[str, Any]:
    gate_input.validate()
    gate_day = datetime.strptime(gate_input.frozen_start_review_gate_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(gate_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    queue_status = _queue_status(gate_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(gate_input.safety_scanner_path)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, gate_day, gate_input.max_source_age_days)
    source_artifact_status = _source_artifact_status(source_artifacts)
    frozen_launch_state = _source_state(
        source_payloads,
        "frozen_launch_packet",
        "frozen_launch_packet_state",
        "FROZEN_LAUNCH_STATE_NOT_SUPPLIED",
    )
    authorization_state = _source_state(
        source_payloads,
        "start_authorization_gate",
        "start_authorization_gate_state",
        "START_AUTHORIZATION_STATE_NOT_SUPPLIED",
    )
    checklist_state = _source_state(
        source_payloads,
        "start_checklist_packet",
        "start_checklist_packet_state",
        "START_CHECKLIST_STATE_NOT_SUPPLIED",
    )
    precondition_state = _source_state(
        source_payloads,
        "start_preconditions_gate",
        "start_preconditions_gate_state",
        "START_PRECONDITIONS_STATE_NOT_SUPPLIED",
    )
    handoff_state = _source_state(
        source_payloads,
        "operator_handoff_packet",
        "operator_handoff_packet_state",
        "OPERATOR_HANDOFF_STATE_NOT_SUPPLIED",
    )
    launch_control_state = _source_state(
        source_payloads,
        "launch_control_gate",
        "launch_control_gate_state",
        "LAUNCH_CONTROL_STATE_NOT_SUPPLIED",
    )
    blocked_prerequisites = _blocked_prerequisites(source_payloads, missing_artifacts, safety_scanner_status)
    unresolved_review_items = _unresolved_review_items(source_payloads, blocked_prerequisites, stale_artifacts)
    required_refreshed_artifacts = _required_refreshed_artifacts(missing_artifacts, stale_artifacts, source_payloads)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    inert_command_hints = _inert_command_hints(source_payloads, _planned_record_placeholder(queue_status))
    queue_next_phase = _queue_next_phase(queue_status)
    required_operator_actions = _required_operator_actions(
        frozen_launch_state=frozen_launch_state,
        authorization_state=authorization_state,
        checklist_state=checklist_state,
        precondition_state=precondition_state,
        handoff_state=handoff_state,
        launch_control_state=launch_control_state,
        source_artifact_status=source_artifact_status,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_review_items=unresolved_review_items,
        required_refreshed_artifacts=required_refreshed_artifacts,
        safety_findings=safety_findings,
        inert_command_hints=inert_command_hints,
        queue_next_phase=queue_next_phase,
    )
    frozen_start_review_state = _frozen_start_review_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_review_items=unresolved_review_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    payload = {
        "phase": "30A",
        "workflow": "Next Cycle Frozen Start Review Gate",
        "frozen_start_review_gate_id": gate_input.frozen_start_review_gate_id,
        "frozen_start_review_gate_date": gate_input.frozen_start_review_gate_date,
        "generated_at_utc": gate_input.generated_at_utc,
        "frozen_launch_state": frozen_launch_state,
        "authorization_state": authorization_state,
        "checklist_state": checklist_state,
        "precondition_state": precondition_state,
        "handoff_state": handoff_state,
        "launch_control_state": launch_control_state,
        "frozen_start_review_state": frozen_start_review_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_FROZEN_START_REVIEW_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "unresolved_review_item_count": len(unresolved_review_items),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "safety_finding_count": len(safety_findings),
            "inert_command_hint_count": len(inert_command_hints),
            "required_operator_action_count": len(required_operator_actions),
            "queue_next_phase": queue_next_phase.get("phase"),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *source_artifact_status,
                    *blocked_prerequisites,
                    *unresolved_review_items,
                    *required_refreshed_artifacts,
                    *safety_findings,
                    *inert_command_hints,
                    *required_operator_actions,
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
        "blocked_prerequisites": blocked_prerequisites,
        "unresolved_review_items": unresolved_review_items,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "safety_findings": safety_findings,
        "inert_command_hints": inert_command_hints,
        "queue_next_phase": queue_next_phase,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "required_operator_actions": required_operator_actions,
        "final_frozen_start_review_summary": _final_summary(
            frozen_start_review_state=frozen_start_review_state,
            frozen_launch_state=frozen_launch_state,
            authorization_state=authorization_state,
            checklist_state=checklist_state,
            precondition_state=precondition_state,
            handoff_state=handoff_state,
            launch_control_state=launch_control_state,
            source_artifacts=source_artifacts,
            blocked_prerequisites=blocked_prerequisites,
            unresolved_review_items=unresolved_review_items,
            required_refreshed_artifacts=required_refreshed_artifacts,
            safety_findings=safety_findings,
            inert_command_hints=inert_command_hints,
            queue_next_phase=queue_next_phase,
            required_operator_actions=required_operator_actions,
        ),
    }
    _validate_frozen_start_review_payload(payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_frozen_start_review_gate(
    gate_input: ResearchNextCycleFrozenStartReviewGateInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_frozen_start_review_gate_payload(gate_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_frozen_start_review_gate_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_frozen_start_review_gate_markdown(payload: dict[str, Any]) -> str:
    _validate_frozen_start_review_payload(payload)
    lines = [
        "# 30A Next Cycle Frozen Start Review Gate",
        "",
        f"Frozen Start Review Gate ID: {payload['frozen_start_review_gate_id']}",
        f"Frozen Start Review Gate Date: {payload['frozen_start_review_gate_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Frozen Launch State: {payload['frozen_launch_state']}",
        f"Authorization State: {payload['authorization_state']}",
        f"Checklist State: {payload['checklist_state']}",
        f"Precondition State: {payload['precondition_state']}",
        f"Handoff State: {payload['handoff_state']}",
        f"Launch-Control State: {payload['launch_control_state']}",
        f"Frozen Start Review State: {payload['frozen_start_review_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Frozen-start-review gate records are read-only and records-only.",
        "Inert command hints are records only; commands are not executed and the next cycle is not started.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Frozen Start Review Summary",
        "",
        payload["final_frozen_start_review_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Unresolved review items", payload["summary"]["unresolved_review_item_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Inert command hints", payload["summary"]["inert_command_hint_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        "",
    ]
    lines.extend(
        _section(
            "Source States",
            [
                {"workflow_id": "frozen_launch_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["frozen_launch_state"], "summary": "29B frozen launch state recorded."},
                {"workflow_id": "authorization_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["authorization_state"], "summary": "29A authorization state recorded."},
                {"workflow_id": "checklist_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["checklist_state"], "summary": "28B checklist state recorded."},
                {"workflow_id": "precondition_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["precondition_state"], "summary": "28A precondition state recorded."},
                {"workflow_id": "handoff_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["handoff_state"], "summary": "27B handoff state recorded."},
                {"workflow_id": "launch_control_state", "label": HUMAN_REVIEW_REQUIRED, "status": payload["launch_control_state"], "summary": "27A launch-control state recorded."},
            ],
        )
    )
    lines.extend(_section("Source Artifact Status", payload["source_artifact_status"]))
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Unresolved Review Items", payload["unresolved_review_items"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Inert Command Hints", payload["inert_command_hints"]))
    lines.extend(_section("Queue Next Phase", [payload["queue_next_phase"]]))
    lines.extend(_section("Required Operator Actions", payload["required_operator_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY frozen-start-review gate generation only.",
            "- MONITOR_ONLY and PAPER_ONLY workflows are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only gate; no command execution, next-cycle start, artifact mutation, artifact deletion, broker action, trade instruction, execution permission, live-trading enablement, broker route, broker call, or order path submission is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(gate_input: ResearchNextCycleFrozenStartReviewGateInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("frozen_launch_packet", "29B Next Cycle Frozen Launch Packet", gate_input.frozen_launch_packet_path),
        ("start_authorization_gate", "29A Next Cycle Start Authorization Gate", gate_input.start_authorization_gate_path),
        ("start_checklist_packet", "28B Next Cycle Start Checklist Packet", gate_input.start_checklist_packet_path),
        ("start_preconditions_gate", "28A Next Cycle Start Preconditions Gate", gate_input.start_preconditions_gate_path),
        ("operator_handoff_packet", "27B Next Cycle Operator Handoff Packet", gate_input.operator_handoff_packet_path),
        ("launch_control_gate", "27A Next Cycle Launch Control Gate", gate_input.launch_control_gate_path),
        ("acceptance_packet", "26B Next Cycle Acceptance Packet", gate_input.acceptance_packet_path),
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


def _required_operator_actions(
    *,
    frozen_launch_state: str,
    authorization_state: str,
    checklist_state: str,
    precondition_state: str,
    handoff_state: str,
    launch_control_state: str,
    source_artifact_status: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    inert_command_hints: list[dict[str, Any]],
    queue_next_phase: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [
        _action("30A-ACTION-FROZEN-LAUNCH-STATE", f"Review 29B frozen launch state: {frozen_launch_state}."),
        _action("30A-ACTION-AUTHORIZATION-STATE", f"Review 29A authorization state: {authorization_state}."),
        _action("30A-ACTION-CHECKLIST-STATE", f"Review 28B checklist state: {checklist_state}."),
        _action("30A-ACTION-PRECONDITION-STATE", f"Review 28A precondition state: {precondition_state}."),
        _action("30A-ACTION-HANDOFF-STATE", f"Review 27B handoff state: {handoff_state}."),
        _action("30A-ACTION-LAUNCH-CONTROL-STATE", f"Review 27A launch-control state: {launch_control_state}."),
        _action("30A-ACTION-SOURCE-ARTIFACTS", f"Review {len(source_artifact_status)} source artifact statuses."),
        _action("30A-ACTION-BLOCKED-PREREQUISITES", f"Resolve or continue blocking {len(blocked_prerequisites)} blocked prerequisites.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
        _action("30A-ACTION-UNRESOLVED-REVIEW", f"Resolve or accept {len(unresolved_review_items)} unresolved review items."),
        _action("30A-ACTION-REFRESHED-ARTIFACTS", f"Refresh or accept {len(required_refreshed_artifacts)} source artifact requirements."),
        _action("30A-ACTION-SAFETY-FINDINGS", f"Review {len(safety_findings)} safety findings.", BLOCKED_BY_SAFETY_GATE if safety_findings else HUMAN_REVIEW_REQUIRED),
        _action("30A-ACTION-INERT-COMMAND-HINTS", f"Confirm {len(inert_command_hints)} inert command hints have executed=false."),
        _action("30A-ACTION-QUEUE-NEXT-PHASE", f"Confirm queue next phase remains not started: {queue_next_phase.get('phase')}."),
        _action("30A-ACTION-LIVE-TRADING-DISABLED", "Confirm LIVE TRADING: DISABLED and no execution permission is granted."),
    ]
    return _dedupe_by_id(actions, "action_id")


def _frozen_start_review_state(
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
    return FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW


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
        "summary": "Master plan queue read for 30A Frozen Start Review Gate context only.",
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
            "summary": "No queue next phase was available to 30A.",
            "run_started": False,
        }
    value = {
        "workflow_id": "queue_next_phase",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "frozen_planned_not_started",
        "phase": next_phase.get("phase"),
        "title": next_phase.get("title"),
        "summary": next_phase.get("summary") or "Queue next phase recorded for Frozen Start review only.",
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
            "summary": "Safety scanner status was not supplied to 30A.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 30A."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _planned_record_placeholder(queue_status: dict[str, Any]) -> list[dict[str, Any]]:
    next_phase = queue_status.get("next_phase")
    if not isinstance(next_phase, dict):
        return []
    return [
        {
            "step_id": f"30A-FROZEN-REVIEW-PLACEHOLDER-{next_phase.get('phase') or 'NEXT'}",
            "source_artifact_id": "master_plan_queue",
            "phase": next_phase.get("phase"),
            "title": next_phase.get("title", "Queued next phase"),
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "queue_frozen_not_started",
            "summary": "Queued next phase is recorded as inert context only.",
            "would_run": False,
            "run_started": False,
            "executed": False,
        }
    ]


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
    frozen_start_review_state: str,
    frozen_launch_state: str,
    authorization_state: str,
    checklist_state: str,
    precondition_state: str,
    handoff_state: str,
    launch_control_state: str,
    source_artifacts: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_review_items: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    inert_command_hints: list[dict[str, Any]],
    queue_next_phase: dict[str, Any],
    required_operator_actions: list[dict[str, Any]],
) -> str:
    present = len([item for item in source_artifacts if item["status"] == "present"])
    return (
        f"Next-cycle Frozen Start Review Gate State is {frozen_start_review_state}. "
        f"Frozen launch state is {frozen_launch_state}. "
        f"Authorization state is {authorization_state}. "
        f"Checklist state is {checklist_state}. "
        f"Precondition state is {precondition_state}. "
        f"Handoff state is {handoff_state}. "
        f"Launch-control state is {launch_control_state}. "
        f"Source artifact status: {present}/{len(source_artifacts)} present. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Unresolved review items: {len(unresolved_review_items)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Safety findings: {len(safety_findings)}. "
        f"Inert command hints: {len(inert_command_hints)}. "
        f"Queue next phase: {queue_next_phase.get('phase')}. "
        f"Required operator actions: {len(required_operator_actions)}. "
        "Safety boundary confirmed: 30A is read-only and records-only and does not execute commands, start the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, grant execution permissions, route broker orders, call broker endpoints, or submit any order path. "
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
        if item.get("phase") == "30A":
            return item
    return items[0] if items else None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "frozen_start_review_gate_date",
        "frozen_launch_packet_date",
        "start_authorization_gate_date",
        "start_checklist_packet_date",
        "start_preconditions_gate_date",
        "operator_handoff_packet_date",
        "launch_control_gate_date",
        "acceptance_packet_date",
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


def _action(action_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": label,
        "status": "frozen_start_review_required",
        "summary": summary,
        "records_only": True,
        "execution_permission_granted": False,
        "run_started": False,
    }


def _validate_frozen_start_review_payload(value: Any) -> None:
    _validate_json_value("research_next_cycle_frozen_start_review_gate_payload", value)
    _validate_frozen_start_review_state(value)


def _validate_frozen_start_review_state(value: Any) -> None:
    if isinstance(value, dict):
        state = value.get("frozen_start_review_state")
        if state is not None and state not in FROZEN_START_REVIEW_STATES:
            raise ValueError(f"invalid research Next Cycle Frozen Start Review Gate state: {state}")
        for item in value.values():
            _validate_frozen_start_review_state(item)
    elif isinstance(value, list):
        for item in value:
            _validate_frozen_start_review_state(item)
