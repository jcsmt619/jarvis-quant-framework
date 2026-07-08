from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_frozen_launch_packet import (
    BLOCKED_BY_SAFETY_GATE,
    FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW,
    ResearchNextCycleFrozenLaunchPacketInput,
    build_default_research_next_cycle_frozen_launch_packet_input,
    build_research_next_cycle_frozen_launch_packet_payload,
    render_research_next_cycle_frozen_launch_packet_markdown,
    write_research_next_cycle_frozen_launch_packet,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 59, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_frozen_launch_packet_tests") / uuid.uuid4().hex


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_payload(
    phase: str,
    workflow: str,
    date_key: str,
    *,
    day: str = "2026-07-07",
    label: str = HUMAN_REVIEW_REQUIRED,
) -> dict[str, object]:
    return {
        "phase": phase,
        "workflow": workflow,
        date_key: day,
        "generated_at_utc": f"{day}T23:00:00+00:00",
        "safety_boundary": {
            "label": label,
            "research_only": True,
            "monitor_only": True,
            "paper_only": True,
            "human_review_required": True,
            "records_only": True,
            "read_only": True,
            "next_cycle_started": False,
            "research_workflow_run_started": False,
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
        },
        "summary": {
            "artifact_count": 0,
            "completed_item_count": 0,
            "open_item_count": 0,
            "blocked_item_count": 0,
            "missing_artifact_count": 0,
        },
    }


def _packet_input(root: Path) -> ResearchNextCycleFrozenLaunchPacketInput:
    return ResearchNextCycleFrozenLaunchPacketInput(
        frozen_launch_packet_id="29B-RESEARCH-NEXT-CYCLE-FROZEN-LAUNCH-PACKET-2026-07-07",
        frozen_launch_packet_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        start_authorization_gate_path=root
        / "research_next_cycle_start_authorization_gate"
        / "research_next_cycle_start_authorization_gate.json",
        start_checklist_packet_path=root
        / "research_next_cycle_start_checklist_packet"
        / "research_next_cycle_start_checklist_packet.json",
        start_preconditions_gate_path=root
        / "research_next_cycle_start_preconditions_gate"
        / "research_next_cycle_start_preconditions_gate.json",
        operator_handoff_packet_path=root
        / "research_next_cycle_operator_handoff_packet"
        / "research_next_cycle_operator_handoff_packet.json",
        launch_control_gate_path=root
        / "research_next_cycle_launch_control_gate"
        / "research_next_cycle_launch_control_gate.json",
        acceptance_packet_path=root
        / "research_next_cycle_acceptance_packet"
        / "research_next_cycle_acceptance_packet.json",
        dry_run_manifest_path=root / "research_next_cycle_dry_run_manifest" / "research_next_cycle_dry_run_manifest.json",
        next_cycle_plan_path=root / "research_next_cycle_plan" / "research_next_cycle_plan.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleFrozenLaunchPacketInput:
    packet_input = _packet_input(root)
    common_empty = {
        "blocked_prerequisites": [],
        "required_refreshed_artifacts": [],
        "operator_review_items": [],
        "operator_checklist_items": [],
        "required_operator_actions": [],
        "required_human_review_actions": [],
        "unresolved_review_items": [],
        "unresolved_items": [],
        "planned_records_only_steps": [],
        "inert_command_hints": [],
        "safety_findings": [],
    }
    payloads = {
        packet_input.start_authorization_gate_path: {
            **_artifact_payload("29A", "Next Cycle Start Authorization Gate", "start_authorization_gate_date"),
            **common_empty,
            "start_authorization_gate_state": "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.start_checklist_packet_path: {
            **_artifact_payload("28B", "Next Cycle Start Checklist Packet", "start_checklist_packet_date"),
            **common_empty,
            "start_checklist_packet_state": "START_CHECKLIST_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.start_preconditions_gate_path: {
            **_artifact_payload("28A", "Next Cycle Start Preconditions Gate", "start_preconditions_gate_date"),
            **common_empty,
            "start_preconditions_gate_state": "START_PRECONDITIONS_READY_FOR_HUMAN_REVIEW",
            "planned_records_only_steps": [
                {
                    "step_id": "28A-STEP-28C",
                    "phase": "28C",
                    "title": "Next Cycle Records Review",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "recorded_not_started",
                    "summary": "Queued records-only review workflow.",
                    "would_run": False,
                    "run_started": False,
                    "executed": False,
                }
            ],
            "inert_command_hints": [
                {
                    "hint_id": "28A-HINT-28C",
                    "step_id": "28A-STEP-28C",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "summary": "Review next cycle records.",
                    "command_hint": "python scripts/run_research_next_cycle_records_review.py --dry-run",
                    "would_run": False,
                    "executed": False,
                }
            ],
        },
        packet_input.operator_handoff_packet_path: {
            **_artifact_payload("27B", "Next Cycle Operator Handoff Packet", "operator_handoff_packet_date"),
            **common_empty,
            "operator_handoff_packet_state": "OPERATOR_HANDOFF_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.launch_control_gate_path: {
            **_artifact_payload("27A", "Next Cycle Launch Control Gate", "launch_control_gate_date"),
            **common_empty,
            "launch_control_gate_state": "LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.acceptance_packet_path: {
            **_artifact_payload("26B", "Next Cycle Acceptance Packet", "acceptance_packet_date"),
            **common_empty,
            "acceptance_state": "ACCEPTANCE_PACKET_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.dry_run_manifest_path: {
            **_artifact_payload("25B", "Next Cycle Dry Run Manifest", "dry_run_manifest_date"),
            **common_empty,
            "dry_run_manifest_state": "DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.next_cycle_plan_path: {
            **_artifact_payload("24B", "Next Research Cycle Plan", "next_cycle_plan_date"),
            **common_empty,
            "next_cycle_plan_state": "NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW",
        },
        packet_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        packet_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        packet_input.safety_scanner_path: {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "passed",
            "summary": "Safety scanner passed.",
            "passed": True,
            "finding_count": 0,
            "findings": [],
            "generated_at_utc": FIXED_NOW.isoformat(),
        },
    }
    for path, payload in payloads.items():
        _write_json(path, payload)
    _write_json(
        packet_input.queue_status_path,
        [
            {
                "phase": "29B",
                "title": "Next Cycle Frozen Launch Packet",
                "spec": "Build deterministic frozen launch records.",
            },
            {
                "phase": "28C",
                "title": "Next Cycle Records Review",
                "spec": "Queued records-only review workflow.",
            },
        ],
    )
    return packet_input


def test_29B_builds_deterministic_frozen_launch_packet() -> None:
    root = _root()
    try:
        packet_input = _write_ready_inputs(root)

        first = build_research_next_cycle_frozen_launch_packet_payload(packet_input)
        second = build_research_next_cycle_frozen_launch_packet_payload(packet_input)

        assert first == second
        assert first["phase"] == "29B"
        assert first["workflow"] == "Next Cycle Frozen Launch Packet"
        assert first["frozen_launch_packet_state"] == FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW
        assert first["authorization_state"] == "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW"
        assert first["checklist_state"] == "START_CHECKLIST_READY_FOR_HUMAN_REVIEW"
        assert first["precondition_state"] == "START_PRECONDITIONS_READY_FOR_HUMAN_REVIEW"
        assert first["summary"]["source_artifact_count"] == 10
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["planned_records_only_step_count"] == 1
        assert first["summary"]["command_hint_count"] == 1
        assert first["queue_next_phase"]["phase"] == "29B"
        assert first["planned_records_only_steps"][0]["phase"] == "28C"
        assert first["planned_records_only_steps"][0]["would_run"] is False
        assert first["planned_records_only_steps"][0]["executed"] is False
        assert first["inert_command_hints"][0]["executed"] is False
        assert first["inert_command_hints"][0]["would_run"] is False
        assert first["operator_checklist_items"][0]["run_started"] is False
        assert first["required_human_review_actions"][0]["execution_permission_granted"] is False
        assert first["safety_boundary"]["records_only"] is True
        assert first["safety_boundary"]["commands_executed"] is False
        assert first["safety_boundary"]["next_cycle_started"] is False
        assert first["safety_boundary"]["artifact_mutation_performed"] is False
        assert first["safety_boundary"]["trade_instructions_created"] is False
        assert first["safety_boundary"]["broker_actions_created"] is False
        assert first["safety_boundary"]["execution_permissions_created"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        assert all("payload" not in item for item in first["source_artifacts"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_29B_writes_json_and_markdown_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_frozen_launch_packet(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_frozen_launch_packet.json"
        assert markdown_path.name == "research_next_cycle_frozen_launch_packet.md"
        assert payload["frozen_launch_packet_id"] == "29B-RESEARCH-NEXT-CYCLE-FROZEN-LAUNCH-PACKET-2026-07-07"
        assert "29B Next Cycle Frozen Launch Packet" in markdown
        assert "Final Frozen Launch Summary" in markdown
        assert "Authorization State" in markdown
        assert "Checklist State" in markdown
        assert "Precondition State" in markdown
        assert "Source Artifact Status" in markdown
        assert "Planned Records-Only Steps" in markdown
        assert "Inert Command Hints" in markdown
        assert "Blocked Prerequisites" in markdown
        assert "Unresolved Review Items" in markdown
        assert "Required Refreshed Artifacts" in markdown
        assert "Safety Findings" in markdown
        assert "Queue Next Phase" in markdown
        assert "Operator Checklist Items" in markdown
        assert "Frozen Acceptance Criteria" in markdown
        assert "Required Human-Review Actions" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_29B_classifies_blocked_for_missing_source_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        packet_input = _write_ready_inputs(root)
        packet_input.start_authorization_gate_path.unlink()
        _write_json(
            packet_input.safety_scanner_path,
            {
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Safety scanner found a blocked condition.",
                "passed": False,
                "finding_count": 1,
                "findings": [{"rule_id": "blocked_scanner_fixture", "summary": "Scanner fixture."}],
                "generated_at_utc": FIXED_NOW.isoformat(),
            },
        )

        payload = build_research_next_cycle_frozen_launch_packet_payload(packet_input)
        markdown = render_research_next_cycle_frozen_launch_packet_markdown(payload)

        assert payload["frozen_launch_packet_state"] == BLOCKED_BY_SAFETY_GATE
        assert "start_authorization_gate" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_start_authorization_gate" in {
            item["prerequisite_id"] for item in payload["blocked_prerequisites"]
        }
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_29B_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleFrozenLaunchPacketInput(
                frozen_launch_packet_id="29B-UNSAFE",
                frozen_launch_packet_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                start_authorization_gate_path=Path(".env"),
            ).validate()

        packet_input = _write_ready_inputs(root)
        plan = json.loads(packet_input.next_cycle_plan_path.read_text(encoding="utf-8"))
        plan["label"] = "BUY" + "_NOW"
        _write_json(packet_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="unsafe|disallowed"):
            build_research_next_cycle_frozen_launch_packet_payload(packet_input)

        plan["label"] = HUMAN_REVIEW_REQUIRED
        plan["live_trading_" + "enabled"] = True
        _write_json(packet_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_frozen_launch_packet_payload(packet_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_29B_default_input_uses_phase_packet_id() -> None:
    packet_input = build_default_research_next_cycle_frozen_launch_packet_input(now=FIXED_NOW)

    assert packet_input.frozen_launch_packet_id == "29B-RESEARCH-NEXT-CYCLE-FROZEN-LAUNCH-PACKET-2026-07-07"
    assert packet_input.frozen_launch_packet_date == "2026-07-07"


def test_29B_cli_writes_next_cycle_frozen_launch_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        packet_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_frozen_launch_packet.py",
                "--out-dir",
                str(out_dir),
                "--frozen-launch-packet-date",
                "2026-07-07",
                "--start-authorization-gate-path",
                str(packet_input.start_authorization_gate_path),
                "--start-checklist-packet-path",
                str(packet_input.start_checklist_packet_path),
                "--start-preconditions-gate-path",
                str(packet_input.start_preconditions_gate_path),
                "--operator-handoff-packet-path",
                str(packet_input.operator_handoff_packet_path),
                "--launch-control-gate-path",
                str(packet_input.launch_control_gate_path),
                "--acceptance-packet-path",
                str(packet_input.acceptance_packet_path),
                "--dry-run-manifest-path",
                str(packet_input.dry_run_manifest_path),
                "--next-cycle-plan-path",
                str(packet_input.next_cycle_plan_path),
                "--report-index-path",
                str(packet_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(packet_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(packet_input.queue_status_path),
                "--safety-scanner-path",
                str(packet_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 29B NEXT CYCLE FROZEN LAUNCH PACKET: COMPLETE" in completed.stdout
        assert "Frozen launch packet is read-only and records-only" in completed.stdout
        assert "Inert command hints are records only and are not executed" in completed.stdout
        assert "The next cycle is not run and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created" in completed.stdout
        assert "Frozen launch records do not grant execution permission" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_frozen_launch_packet.json").exists()
        assert (out_dir / "research_next_cycle_frozen_launch_packet.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
