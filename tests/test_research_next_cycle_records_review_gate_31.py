from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_records_review_gate_31 import (
    BLOCKED_BY_SAFETY_GATE,
    RECORDS_REVIEW_GATE_31_READY_FOR_HUMAN_REVIEW,
    ResearchNextCycleRecordsReviewGate31Input,
    build_default_research_next_cycle_records_review_gate_31_input,
    build_research_next_cycle_records_review_gate_31_payload,
    render_research_next_cycle_records_review_gate_31_markdown,
    write_research_next_cycle_records_review_gate_31,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 59, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_records_review_gate_31_tests") / uuid.uuid4().hex


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
        "planned_records_only_steps": [],
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


def _gate_input(root: Path) -> ResearchNextCycleRecordsReviewGate31Input:
    return ResearchNextCycleRecordsReviewGate31Input(
        records_review_gate_31_id="31A-RESEARCH-NEXT-CYCLE-RECORDS-REVIEW-GATE-31-2026-07-07",
        records_review_gate_31_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        frozen_start_evidence_packet_path=root
        / "research_next_cycle_frozen_start_evidence_packet"
        / "research_next_cycle_frozen_start_evidence_packet.json",
        frozen_start_review_gate_path=root
        / "research_next_cycle_frozen_start_review_gate"
        / "research_next_cycle_frozen_start_review_gate.json",
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
        launch_control_gate_path=root
        / "research_next_cycle_launch_control_gate"
        / "research_next_cycle_launch_control_gate.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleRecordsReviewGate31Input:
    gate_input = _gate_input(root)
    payloads = {
        gate_input.frozen_start_evidence_packet_path: {
            **_artifact_payload("30B", "Next Cycle Frozen Start Evidence Packet", "frozen_start_evidence_packet_date"),
            "frozen_start_evidence_packet_state": "FROZEN_START_EVIDENCE_READY_FOR_HUMAN_REVIEW",
            "evidence_references": [
                {
                    "reference_id": "30B-EVIDENCE-31A",
                    "artifact_id": "frozen_start_evidence_packet",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "present",
                    "summary": "Evidence reference fixture.",
                    "records_only": True,
                    "execution_permission_granted": False,
                    "run_started": False,
                }
            ],
            "inert_command_hints": [
                {
                    "hint_id": "30B-HINT-31A",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "summary": "Review records gate.",
                    "command_hint": "python scripts/run_research_next_cycle_records_review_gate_31.py",
                    "would_run": False,
                    "executed": False,
                }
            ],
        },
        gate_input.frozen_start_review_gate_path: {
            **_artifact_payload("30A", "Next Cycle Frozen Start Review Gate", "frozen_start_review_gate_date"),
            "frozen_start_review_state": "FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW",
        },
        gate_input.frozen_launch_packet_path: {
            **_artifact_payload("29B", "Next Cycle Frozen Launch Packet", "frozen_launch_packet_date"),
            "frozen_launch_packet_state": "FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW",
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
                "phase": "31A",
                "title": "Next Cycle Records Review Gate 31",
                "spec": "Build deterministic records review gate records.",
            },
            {
                "phase": "31B",
                "title": "Next Cycle Records Review Evidence Packet",
                "spec": "Queued records-only evidence workflow.",
            },
        ],
    )
    return gate_input


def test_31A_builds_deterministic_records_review_gate_31() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)

        first = build_research_next_cycle_records_review_gate_31_payload(gate_input)
        second = build_research_next_cycle_records_review_gate_31_payload(gate_input)

        assert first == second
        assert first["phase"] == "31A"
        assert first["workflow"] == "Next Cycle Records Review Gate 31"
        assert first["records_review_gate_31_state"] == RECORDS_REVIEW_GATE_31_READY_FOR_HUMAN_REVIEW
        assert first["evidence_state"] == "FROZEN_START_EVIDENCE_READY_FOR_HUMAN_REVIEW"
        assert first["review_state"] == "FROZEN_START_REVIEW_READY_FOR_HUMAN_REVIEW"
        assert first["frozen_launch_state"] == "FROZEN_LAUNCH_READY_FOR_HUMAN_REVIEW"
        assert first["authorization_state"] == "START_AUTHORIZATION_READY_FOR_HUMAN_REVIEW"
        assert first["checklist_state"] == "START_CHECKLIST_READY_FOR_HUMAN_REVIEW"
        assert first["precondition_state"] == "START_PRECONDITIONS_READY_FOR_HUMAN_REVIEW"
        assert first["summary"]["source_artifact_count"] == 10
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["inert_command_hint_count"] == 1
        assert first["summary"]["evidence_reference_count"] == 12
        assert first["queue_next_phase"]["phase"] == "31A"
        assert first["inert_command_hints"][0]["executed"] is False
        assert first["inert_command_hints"][0]["would_run"] is False
        assert first["operator_checklist_items"][0]["run_started"] is False
        assert first["required_human_review_actions"][0]["execution_permission_granted"] is False
        assert first["evidence_references"][0]["execution_permission_granted"] is False
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


def test_31A_writes_json_and_markdown_gate_31() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_records_review_gate_31(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_records_review_gate_31.json"
        assert markdown_path.name == "research_next_cycle_records_review_gate_31.md"
        assert payload["records_review_gate_31_id"] == "31A-RESEARCH-NEXT-CYCLE-RECORDS-REVIEW-GATE-31-2026-07-07"
        assert "31A Next Cycle Records Review Gate 31" in markdown
        assert "Final Records Review Gate 31 Summary" in markdown
        assert "Evidence State" in markdown
        assert "Review State" in markdown
        assert "Source Artifact Status" in markdown
        assert "Blocked Prerequisites" in markdown
        assert "Unresolved Review Items" in markdown
        assert "Required Refreshed Artifacts" in markdown
        assert "Safety Findings" in markdown
        assert "Inert Command Hints" in markdown
        assert "Queue Next Phase" in markdown
        assert "Operator Checklist Items" in markdown
        assert "Evidence References" in markdown
        assert "Required Human-Review Actions" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_31A_classifies_blocked_for_missing_source_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)
        gate_input.frozen_start_evidence_packet_path.unlink()
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

        payload = build_research_next_cycle_records_review_gate_31_payload(gate_input)
        markdown = render_research_next_cycle_records_review_gate_31_markdown(payload)

        assert payload["records_review_gate_31_state"] == BLOCKED_BY_SAFETY_GATE
        assert "frozen_start_evidence_packet" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_frozen_start_evidence_packet" in {
            item["prerequisite_id"] for item in payload["blocked_prerequisites"]
        }
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_31A_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleRecordsReviewGate31Input(
                records_review_gate_31_id="31A-UNSAFE",
                records_review_gate_31_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                frozen_start_evidence_packet_path=Path(".env"),
            ).validate()

        gate_input = _write_ready_inputs(root)
        evidence_packet = json.loads(gate_input.frozen_start_evidence_packet_path.read_text(encoding="utf-8"))
        evidence_packet["label"] = "BUY" + "_NOW"
        _write_json(gate_input.frozen_start_evidence_packet_path, evidence_packet)
        with pytest.raises(ValueError, match="unsafe|disallowed"):
            build_research_next_cycle_records_review_gate_31_payload(gate_input)

        evidence_packet["label"] = HUMAN_REVIEW_REQUIRED
        evidence_packet["live_trading_" + "enabled"] = True
        _write_json(gate_input.frozen_start_evidence_packet_path, evidence_packet)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_records_review_gate_31_payload(gate_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_31A_default_input_uses_phase_gate_id() -> None:
    gate_input = build_default_research_next_cycle_records_review_gate_31_input(now=FIXED_NOW)

    assert gate_input.records_review_gate_31_id == "31A-RESEARCH-NEXT-CYCLE-RECORDS-REVIEW-GATE-31-2026-07-07"
    assert gate_input.records_review_gate_31_date == "2026-07-07"


def test_31A_cli_writes_next_cycle_records_review_gate_31() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        gate_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_records_review_gate_31.py",
                "--out-dir",
                str(out_dir),
                "--records-review-gate-31-date",
                "2026-07-07",
                "--frozen-start-evidence-packet-path",
                str(gate_input.frozen_start_evidence_packet_path),
                "--frozen-start-review-gate-path",
                str(gate_input.frozen_start_review_gate_path),
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
        assert "JARVIS 31A NEXT CYCLE RECORDS REVIEW GATE 31: COMPLETE" in completed.stdout
        assert "Records Review Gate 31 is read-only and records-only" in completed.stdout
        assert "Inert command hints are records only and are not executed" in completed.stdout
        assert "The next cycle is not run and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created" in completed.stdout
        assert "Records Review Gate 31 records do not grant execution permission" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_records_review_gate_31.json").exists()
        assert (out_dir / "research_next_cycle_records_review_gate_31.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
