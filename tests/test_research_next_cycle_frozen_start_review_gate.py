from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_frozen_start_review_gate import (
    BLOCKED_BY_SAFETY_GATE,
    FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW,
    ResearchNextCycleFrozenStartReviewGateInput,
    build_default_research_next_cycle_frozen_start_review_gate_input,
    build_research_next_cycle_frozen_start_review_gate_payload,
    render_research_next_cycle_frozen_start_review_gate_markdown,
    write_research_next_cycle_frozen_start_review_gate,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 59, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_frozen_start_review_gate_tests") / uuid.uuid4().hex


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
        "blocked_prerequisites": [],
        "required_refreshed_artifacts": [],
        "operator_review_items": [],
        "operator_checklist_items": [],
        "required_operator_actions": [],
        "required_human_review_actions": [],
        "unresolved_review_items": [],
        "unresolved_items": [],
        "inert_command_hints": [],
        "safety_findings": [],
        "summary": {
            "artifact_count": 0,
            "completed_item_count": 0,
            "open_item_count": 0,
            "blocked_item_count": 0,
            "missing_artifact_count": 0,
        },
    }


def _gate_input(root: Path) -> ResearchNextCycleFrozenStartReviewGateInput:
    return ResearchNextCycleFrozenStartReviewGateInput(
        frozen_start_review_gate_id="30A-RESEARCH-NEXT-CYCLE-FROZEN-START-REVIEW-GATE-2026-07-07",
        frozen_start_review_gate_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        frozen_launch_packet_path=root
        / "research_next_cycle_frozen_launch_packet"
        / "research_next_cycle_frozen_launch_packet.json",
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
        launch_control_gate_path=root / "research_next_cycle_launch_control_gate" / "research_next_cycle_launch_control_gate.json",
        acceptance_packet_path=root / "research_next_cycle_acceptance_packet" / "research_next_cycle_acceptance_packet.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleFrozenStartReviewGateInput:
    gate_input = _gate_input(root)
    payloads = {
        gate_input.frozen_launch_packet_path: {
            **_artifact_payload("29B", "Next Cycle Frozen Launch Packet", "frozen_launch_packet_date"),
            "frozen_launch_packet_state": "FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW",
            "inert_command_hints": [
                {
                    "hint_id": "29B-HINT-30A",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "summary": "Review frozen start state.",
                    "command_hint": "python scripts/run_research_next_cycle_frozen_start_review_gate.py --dry-run",
                    "would_run": False,
                    "executed": False,
                }
            ],
        },
        gate_input.start_authorization_gate_path: {
            **_artifact_payload("29A", "Next Cycle Start Authorization Gate", "start_authorization_gate_date"),
            "start_authorization_gate_state": "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.start_checklist_packet_path: {
            **_artifact_payload("28B", "Next Cycle Start Checklist Packet", "start_checklist_packet_date"),
            "start_checklist_packet_state": "START_CHECKLIST_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.start_preconditions_gate_path: {
            **_artifact_payload("28A", "Next Cycle Start Preconditions Gate", "start_preconditions_gate_date"),
            "start_preconditions_gate_state": "START_PRECONDITIONS_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.operator_handoff_packet_path: {
            **_artifact_payload("27B", "Next Cycle Operator Handoff Packet", "operator_handoff_packet_date"),
            "operator_handoff_packet_state": "OPERATOR_HANDOFF_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.launch_control_gate_path: {
            **_artifact_payload("27A", "Next Cycle Launch Control Gate", "launch_control_gate_date"),
            "launch_control_gate_state": "LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.acceptance_packet_path: {
            **_artifact_payload("26B", "Next Cycle Acceptance Packet", "acceptance_packet_date"),
            "acceptance_state": "ACCEPTANCE_PACKET_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        gate_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        gate_input.safety_scanner_path: {
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
        gate_input.queue_status_path,
        [
            {
                "phase": "30A",
                "title": "Next Cycle Frozen Start Review Gate",
                "spec": "Build deterministic frozen start review records.",
            },
            {
                "phase": "30B",
                "title": "Next Cycle Frozen Start Evidence Packet",
                "spec": "Queued records-only evidence workflow.",
            },
        ],
    )
    return gate_input


def test_30A_builds_deterministic_frozen_start_review_gate() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)

        first = build_research_next_cycle_frozen_start_review_gate_payload(gate_input)
        second = build_research_next_cycle_frozen_start_review_gate_payload(gate_input)

        assert first == second
        assert first["phase"] == "30A"
        assert first["workflow"] == "Next Cycle Frozen Start Review Gate"
        assert first["frozen_start_review_state"] == FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW
        assert first["frozen_launch_state"] == "FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW"
        assert first["authorization_state"] == "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW"
        assert first["checklist_state"] == "START_CHECKLIST_READY_FOR_HUMAN_REVIEW"
        assert first["precondition_state"] == "START_PRECONDITIONS_READY_FOR_HUMAN_REVIEW"
        assert first["handoff_state"] == "OPERATOR_HANDOFF_READY_FOR_HUMAN_REVIEW"
        assert first["launch_control_state"] == "LAUNCH_CONTROL_READY_FOR_HUMAN_REVIEW"
        assert first["summary"]["source_artifact_count"] == 9
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["inert_command_hint_count"] == 1
        assert first["queue_next_phase"]["phase"] == "30A"
        assert first["inert_command_hints"][0]["executed"] is False
        assert first["inert_command_hints"][0]["would_run"] is False
        assert first["required_operator_actions"][0]["run_started"] is False
        assert first["required_operator_actions"][0]["execution_permission_granted"] is False
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


def test_30A_writes_json_and_markdown_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_frozen_start_review_gate(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_frozen_start_review_gate.json"
        assert markdown_path.name == "research_next_cycle_frozen_start_review_gate.md"
        assert payload["frozen_start_review_gate_id"] == "30A-RESEARCH-NEXT-CYCLE-FROZEN-START-REVIEW-GATE-2026-07-07"
        assert "30A Next Cycle Frozen Start Review Gate" in markdown
        assert "Final Frozen Start Review Summary" in markdown
        assert "Frozen Launch State" in markdown
        assert "Authorization State" in markdown
        assert "Checklist State" in markdown
        assert "Precondition State" in markdown
        assert "Handoff State" in markdown
        assert "Launch-Control State" in markdown
        assert "Source Artifact Status" in markdown
        assert "Blocked Prerequisites" in markdown
        assert "Unresolved Review Items" in markdown
        assert "Required Refreshed Artifacts" in markdown
        assert "Safety Findings" in markdown
        assert "Inert Command Hints" in markdown
        assert "Queue Next Phase" in markdown
        assert "Required Operator Actions" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_30A_classifies_blocked_for_missing_source_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)
        gate_input.frozen_launch_packet_path.unlink()
        _write_json(
            gate_input.safety_scanner_path,
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

        payload = build_research_next_cycle_frozen_start_review_gate_payload(gate_input)
        markdown = render_research_next_cycle_frozen_start_review_gate_markdown(payload)

        assert payload["frozen_start_review_state"] == BLOCKED_BY_SAFETY_GATE
        assert "frozen_launch_packet" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_frozen_launch_packet" in {
            item["prerequisite_id"] for item in payload["blocked_prerequisites"]
        }
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_30A_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleFrozenStartReviewGateInput(
                frozen_start_review_gate_id="30A-UNSAFE",
                frozen_start_review_gate_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                frozen_launch_packet_path=Path(".env"),
            ).validate()

        gate_input = _write_ready_inputs(root)
        packet = json.loads(gate_input.frozen_launch_packet_path.read_text(encoding="utf-8"))
        packet["label"] = "BUY" + "_NOW"
        _write_json(gate_input.frozen_launch_packet_path, packet)
        with pytest.raises(ValueError, match="unsafe|disallowed"):
            build_research_next_cycle_frozen_start_review_gate_payload(gate_input)

        packet["label"] = HUMAN_REVIEW_REQUIRED
        packet["live_trading_" + "enabled"] = True
        _write_json(gate_input.frozen_launch_packet_path, packet)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_frozen_start_review_gate_payload(gate_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_30A_default_input_uses_phase_gate_id() -> None:
    gate_input = build_default_research_next_cycle_frozen_start_review_gate_input(now=FIXED_NOW)

    assert gate_input.frozen_start_review_gate_id == "30A-RESEARCH-NEXT-CYCLE-FROZEN-START-REVIEW-GATE-2026-07-07"
    assert gate_input.frozen_start_review_gate_date == "2026-07-07"


def test_30A_cli_writes_next_cycle_frozen_start_review_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        gate_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_frozen_start_review_gate.py",
                "--out-dir",
                str(out_dir),
                "--frozen-start-review-gate-date",
                "2026-07-07",
                "--frozen-launch-packet-path",
                str(gate_input.frozen_launch_packet_path),
                "--start-authorization-gate-path",
                str(gate_input.start_authorization_gate_path),
                "--start-checklist-packet-path",
                str(gate_input.start_checklist_packet_path),
                "--start-preconditions-gate-path",
                str(gate_input.start_preconditions_gate_path),
                "--operator-handoff-packet-path",
                str(gate_input.operator_handoff_packet_path),
                "--launch-control-gate-path",
                str(gate_input.launch_control_gate_path),
                "--acceptance-packet-path",
                str(gate_input.acceptance_packet_path),
                "--report-index-path",
                str(gate_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(gate_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(gate_input.queue_status_path),
                "--safety-scanner-path",
                str(gate_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 30A NEXT CYCLE FROZEN START REVIEW GATE: COMPLETE" in completed.stdout
        assert "Frozen start review gate is read-only and records-only" in completed.stdout
        assert "Inert command hints are records only and are not executed" in completed.stdout
        assert "The next cycle is not started and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created" in completed.stdout
        assert "Frozen start review records do not grant execution permission" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_frozen_start_review_gate.json").exists()
        assert (out_dir / "research_next_cycle_frozen_start_review_gate.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
