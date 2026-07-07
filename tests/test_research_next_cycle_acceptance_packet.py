from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_acceptance_packet import (
    ACCEPTANCE_PACKET_READY_FOR_HUMAN_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
    ResearchNextCycleAcceptancePacketInput,
    build_default_research_next_cycle_acceptance_packet_input,
    build_research_next_cycle_acceptance_packet_payload,
    render_research_next_cycle_acceptance_packet_markdown,
    write_research_next_cycle_acceptance_packet,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 59, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_acceptance_packet_tests") / uuid.uuid4().hex


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


def _packet_input(root: Path) -> ResearchNextCycleAcceptancePacketInput:
    return ResearchNextCycleAcceptancePacketInput(
        acceptance_packet_id="26B-RESEARCH-NEXT-CYCLE-ACCEPTANCE-PACKET-2026-07-07",
        acceptance_packet_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        operator_acceptance_gate_path=root
        / "research_next_cycle_operator_acceptance_gate"
        / "research_next_cycle_operator_acceptance_gate.json",
        dry_run_manifest_path=root / "research_next_cycle_dry_run_manifest" / "research_next_cycle_dry_run_manifest.json",
        safety_preflight_path=root / "research_next_cycle_safety_preflight" / "research_next_cycle_safety_preflight.json",
        next_cycle_plan_path=root / "research_next_cycle_plan" / "research_next_cycle_plan.json",
        rollover_gate_path=root / "research_cycle_rollover_gate" / "research_cycle_rollover_gate.json",
        archive_index_path=root / "research_cycle_archive_index" / "research_cycle_archive_index.json",
        operations_console_path=root / "research_operations_console" / "research_operations_console.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleAcceptancePacketInput:
    packet_input = _packet_input(root)
    payloads = {
        packet_input.operator_acceptance_gate_path: {
            **_artifact_payload("26A", "Next Cycle Operator Acceptance Gate", "operator_acceptance_gate_date"),
            "operator_acceptance_gate_state": "ACCEPTANCE_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "required_operator_review_items": [],
            "required_operator_actions": [],
            "planned_next_cycle_steps": [
                {
                    "step_id": "26A-STEP-26C",
                    "phase": "26C",
                    "title": "Next Records-Only Research Report",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "dry_run_planned_not_started",
                    "summary": "Queued records-only reporting workflow.",
                    "would_run": False,
                    "run_started": False,
                    "executed": False,
                }
            ],
            "command_hints": [
                {
                    "hint_id": "26A-HINT-26C",
                    "step_id": "26A-STEP-26C",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "summary": "Review next records-only report.",
                    "command_hint": "python scripts/run_research_report.py --dry-run",
                    "would_run": False,
                    "executed": False,
                }
            ],
            "safety_findings": [],
        },
        packet_input.dry_run_manifest_path: {
            **_artifact_payload("25B", "Next Cycle Dry Run Manifest", "dry_run_manifest_date"),
            "dry_run_manifest_state": "DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "required_operator_review_items": [],
            "planned_next_cycle_steps": [],
            "safety_findings": [],
        },
        packet_input.safety_preflight_path: {
            **_artifact_payload("25A", "Next Cycle Safety Preflight", "preflight_date"),
            "preflight_state": "PREFLIGHT_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "required_operator_actions": [],
            "safety_preflight_items": [],
            "safety_findings": [],
        },
        packet_input.next_cycle_plan_path: {
            **_artifact_payload("24B", "Next Research Cycle Plan", "next_cycle_plan_date"),
            "next_cycle_plan_state": "NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "operator_review_items": [],
            "planned_research_report_workflows": [],
            "safety_findings": [],
        },
        packet_input.rollover_gate_path: {
            **_artifact_payload("24A", "Research Cycle Rollover Gate", "rollover_gate_date"),
            "rollover_state": "ROLLOVER_READY_FOR_HUMAN_REVIEW",
            "blocked_items": [],
            "required_operator_actions": [],
            "safety_findings": [],
        },
        packet_input.archive_index_path: {
            **_artifact_payload("23B", "Research Cycle Archive Index", "archive_index_date"),
            "archive_index_state": "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY",
            "human_review_notes": [],
            "blocked_workflows": [],
        },
        packet_input.operations_console_path: {
            **_artifact_payload("23A", "Research Operations Console", "console_date"),
            "console_state": "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY",
            "open_items": [],
            "blocked_items": [],
            "required_operator_actions": [],
            "safety_findings": [],
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
                "phase": "26B",
                "title": "Next Cycle Acceptance Packet",
                "spec": "Build deterministic acceptance packet records.",
            },
            {
                "phase": "26C",
                "title": "Next Records-Only Research Report",
                "spec": "Queued records-only reporting workflow.",
            },
        ],
    )
    return packet_input


def test_26B_builds_deterministic_acceptance_packet() -> None:
    root = _root()
    try:
        packet_input = _write_ready_inputs(root)

        first = build_research_next_cycle_acceptance_packet_payload(packet_input)
        second = build_research_next_cycle_acceptance_packet_payload(packet_input)

        assert first == second
        assert first["phase"] == "26B"
        assert first["workflow"] == "Next Cycle Acceptance Packet"
        assert first["acceptance_state"] == ACCEPTANCE_PACKET_READY_FOR_HUMAN_REVIEW
        assert first["summary"]["source_artifact_count"] == 9
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["planned_dry_run_step_count"] == 1
        assert first["summary"]["command_hint_count"] == 1
        assert first["planned_dry_run_steps"][0]["phase"] == "26C"
        assert first["planned_dry_run_steps"][0]["would_run"] is False
        assert first["planned_dry_run_steps"][0]["executed"] is False
        assert first["inert_command_hints"][0]["executed"] is False
        assert first["inert_command_hints"][0]["would_run"] is False
        assert first["skipped_steps"][0]["executed"] is False
        assert first["safety_boundary"]["records_only"] is True
        assert first["safety_boundary"]["commands_executed"] is False
        assert first["safety_boundary"]["next_cycle_started"] is False
        assert first["safety_boundary"]["research_workflow_run_started"] is False
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


def test_26B_writes_json_and_markdown_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_acceptance_packet(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_acceptance_packet.json"
        assert markdown_path.name == "research_next_cycle_acceptance_packet.md"
        assert payload["acceptance_packet_id"] == "26B-RESEARCH-NEXT-CYCLE-ACCEPTANCE-PACKET-2026-07-07"
        assert "26B Next Cycle Acceptance Packet" in markdown
        assert "Final Next-Cycle Acceptance Summary" in markdown
        assert "Source Artifact Status" in markdown
        assert "Planned Dry-Run Steps" in markdown
        assert "Inert Command Hints" in markdown
        assert "Skipped Steps" in markdown
        assert "Blocked Prerequisites" in markdown
        assert "Required Refreshed Artifacts" in markdown
        assert "Operator Review Items" in markdown
        assert "Safety Findings" in markdown
        assert "Acceptance Criteria" in markdown
        assert "Unresolved Items" in markdown
        assert "Required Human-Review Actions" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_26B_classifies_blocked_for_missing_gate_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        packet_input = _write_ready_inputs(root)
        packet_input.operator_acceptance_gate_path.unlink()
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

        payload = build_research_next_cycle_acceptance_packet_payload(packet_input)
        markdown = render_research_next_cycle_acceptance_packet_markdown(payload)

        assert payload["acceptance_state"] == BLOCKED_BY_SAFETY_GATE
        assert "operator_acceptance_gate" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_operator_acceptance_gate" in {
            item["prerequisite_id"] for item in payload["blocked_prerequisites"]
        }
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert payload["skipped_steps"][0]["label"] == BLOCKED_BY_SAFETY_GATE
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_26B_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleAcceptancePacketInput(
                acceptance_packet_id="26B-UNSAFE",
                acceptance_packet_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                operator_acceptance_gate_path=Path(".env"),
            ).validate()

        packet_input = _write_ready_inputs(root)
        plan = json.loads(packet_input.next_cycle_plan_path.read_text(encoding="utf-8"))
        plan["label"] = "BUY" + "_NOW"
        _write_json(packet_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="unsafe research next cycle acceptance packet label"):
            build_research_next_cycle_acceptance_packet_payload(packet_input)

        plan["label"] = HUMAN_REVIEW_REQUIRED
        plan["live_trading_" + "enabled"] = True
        _write_json(packet_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_acceptance_packet_payload(packet_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_26B_default_input_uses_phase_packet_id() -> None:
    packet_input = build_default_research_next_cycle_acceptance_packet_input(now=FIXED_NOW)

    assert packet_input.acceptance_packet_id == "26B-RESEARCH-NEXT-CYCLE-ACCEPTANCE-PACKET-2026-07-07"
    assert packet_input.acceptance_packet_date == "2026-07-07"


def test_26B_cli_writes_next_cycle_acceptance_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        packet_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_acceptance_packet.py",
                "--out-dir",
                str(out_dir),
                "--acceptance-packet-date",
                "2026-07-07",
                "--operator-acceptance-gate-path",
                str(packet_input.operator_acceptance_gate_path),
                "--dry-run-manifest-path",
                str(packet_input.dry_run_manifest_path),
                "--safety-preflight-path",
                str(packet_input.safety_preflight_path),
                "--next-cycle-plan-path",
                str(packet_input.next_cycle_plan_path),
                "--rollover-gate-path",
                str(packet_input.rollover_gate_path),
                "--archive-index-path",
                str(packet_input.archive_index_path),
                "--operations-console-path",
                str(packet_input.operations_console_path),
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
        assert "JARVIS 26B NEXT CYCLE ACCEPTANCE PACKET: COMPLETE" in completed.stdout
        assert "Next-cycle acceptance packet is read-only and records-only" in completed.stdout
        assert "Inert command hints are records only and are not executed" in completed.stdout
        assert "The next cycle is not run and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, or order paths are created" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_acceptance_packet.json").exists()
        assert (out_dir / "research_next_cycle_acceptance_packet.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
