from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_safety_preflight import (
    BLOCKED_BY_SAFETY_GATE,
    NEEDS_OPERATOR_REVIEW,
    PREFLIGHT_READY_FOR_HUMAN_REVIEW,
    ResearchNextCycleSafetyPreflightInput,
    build_default_research_next_cycle_safety_preflight_input,
    build_research_next_cycle_safety_preflight_payload,
    render_research_next_cycle_safety_preflight_markdown,
    write_research_next_cycle_safety_preflight,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 55, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_safety_preflight_tests") / uuid.uuid4().hex


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


def _preflight_input(root: Path) -> ResearchNextCycleSafetyPreflightInput:
    return ResearchNextCycleSafetyPreflightInput(
        preflight_id="25A-RESEARCH-NEXT-CYCLE-SAFETY-PREFLIGHT-2026-07-07",
        preflight_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        next_cycle_plan_path=root / "research_next_cycle_plan" / "research_next_cycle_plan.json",
        rollover_gate_path=root / "research_cycle_rollover_gate" / "research_cycle_rollover_gate.json",
        archive_index_path=root / "research_cycle_archive_index" / "research_cycle_archive_index.json",
        operations_console_path=root / "research_operations_console" / "research_operations_console.json",
        operator_signoff_packet_path=root / "operator_signoff_packet" / "operator_signoff_packet.json",
        readiness_gate_path=root / "research_cycle_readiness_gate" / "research_cycle_readiness_gate.json",
        retention_policy_path=root / "research_artifact_retention_policy" / "research_artifact_retention_policy.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleSafetyPreflightInput:
    preflight_input = _preflight_input(root)
    payloads = {
        preflight_input.next_cycle_plan_path: {
            **_artifact_payload("24B", "Next Research Cycle Plan", "next_cycle_plan_date"),
            "next_cycle_plan_state": "NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "operator_review_items": [],
            "planned_research_report_workflows": [
                {
                    "workflow_id": "planned_25b",
                    "phase": "25B",
                    "title": "Records-Only Follow-On",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "planned_not_started",
                    "summary": "Queued records-only follow-on.",
                    "run_started": False,
                }
            ],
            "safety_findings": [],
        },
        preflight_input.rollover_gate_path: {
            **_artifact_payload("24A", "Research Cycle Rollover Gate", "rollover_gate_date"),
            "rollover_state": "ROLLOVER_READY_FOR_HUMAN_REVIEW",
            "required_operator_actions": [],
            "safety_findings": [],
        },
        preflight_input.archive_index_path: {
            **_artifact_payload("23B", "Research Cycle Archive Index", "archive_index_date"),
            "archive_index_state": "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY",
            "human_review_notes": [],
        },
        preflight_input.operations_console_path: {
            **_artifact_payload("23A", "Research Operations Console", "console_date"),
            "console_state": "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY",
            "required_operator_actions": [],
            "open_items": [],
        },
        preflight_input.operator_signoff_packet_path: {
            **_artifact_payload("22B", "Operator Signoff Packet", "signoff_date"),
            "signoff_state": "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY",
        },
        preflight_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        preflight_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [],
            "dry_run_manifest": [],
        },
        preflight_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        preflight_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        preflight_input.safety_scanner_path: {
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
        preflight_input.queue_status_path,
        [
            {
                "phase": "25A",
                "title": "Next Cycle Safety Preflight",
                "spec": "Build deterministic safety preflight reports.",
            },
            {
                "phase": "25B",
                "title": "Records-Only Follow-On",
                "spec": "Queued records-only next phase.",
            },
        ],
    )
    return preflight_input


def test_25a_builds_deterministic_ready_preflight() -> None:
    root = _root()
    try:
        preflight_input = _write_ready_inputs(root)

        first = build_research_next_cycle_safety_preflight_payload(preflight_input)
        second = build_research_next_cycle_safety_preflight_payload(preflight_input)

        assert first == second
        assert first["phase"] == "25A"
        assert first["workflow"] == "Next Cycle Safety Preflight"
        assert first["preflight_state"] == PREFLIGHT_READY_FOR_HUMAN_REVIEW
        assert first["summary"]["source_artifact_count"] == 10
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["blocked_prerequisite_count"] == 0
        assert first["summary"]["unresolved_operator_review_item_count"] == 0
        assert first["queue_next_phase"]["phase"] == "25B"
        assert first["queue_next_phase"]["run_started"] is False
        assert first["safety_boundary"]["records_only"] is True
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


def test_25a_writes_json_and_markdown_preflight() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_safety_preflight(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_safety_preflight.json"
        assert markdown_path.name == "research_next_cycle_safety_preflight.md"
        assert payload["preflight_id"] == "25A-RESEARCH-NEXT-CYCLE-SAFETY-PREFLIGHT-2026-07-07"
        assert "25A Next Cycle Safety Preflight" in markdown
        assert "Blocked Prerequisites" in markdown
        assert "Required Refreshed Artifacts" in markdown
        assert "Unresolved Operator Review Items" in markdown
        assert "Queue Next Phase" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25a_classifies_needs_operator_review_for_stale_and_open_items() -> None:
    root = _root()
    try:
        preflight_input = _write_ready_inputs(root)
        plan = json.loads(preflight_input.next_cycle_plan_path.read_text(encoding="utf-8"))
        plan["next_cycle_plan_date"] = "2026-07-05"
        plan["generated_at_utc"] = "2026-07-05T23:00:00+00:00"
        plan["operator_review_items"] = [
            {
                "review_item_id": "confirm_next_phase",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Operator must confirm next phase.",
            }
        ]
        _write_json(preflight_input.next_cycle_plan_path, plan)

        payload = build_research_next_cycle_safety_preflight_payload(preflight_input)

        assert payload["preflight_state"] == NEEDS_OPERATOR_REVIEW
        assert "next_cycle_plan" in {item["artifact_id"] for item in payload["stale_artifacts"]}
        assert "next_cycle_plan_confirm_next_phase" in {
            item["review_item_id"] for item in payload["unresolved_operator_review_items"]
        }
        assert payload["summary"]["required_operator_action_count"] >= 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25a_classifies_blocked_for_missing_plan_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        preflight_input = _write_ready_inputs(root)
        preflight_input.next_cycle_plan_path.unlink()
        _write_json(
            preflight_input.safety_scanner_path,
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

        payload = build_research_next_cycle_safety_preflight_payload(preflight_input)
        markdown = render_research_next_cycle_safety_preflight_markdown(payload)

        assert payload["preflight_state"] == BLOCKED_BY_SAFETY_GATE
        assert "next_cycle_plan" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_next_cycle_plan" in {item["prerequisite_id"] for item in payload["blocked_prerequisites"]}
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "25A-PREFLIGHT-SAFETY-SCANNER" in {
            item["preflight_id"] for item in payload["safety_preflight_items"] if item["label"] == BLOCKED_BY_SAFETY_GATE
        }
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25a_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleSafetyPreflightInput(
                preflight_id="25A-UNSAFE",
                preflight_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                next_cycle_plan_path=Path(".env"),
            ).validate()

        preflight_input = _write_ready_inputs(root)
        plan = json.loads(preflight_input.next_cycle_plan_path.read_text(encoding="utf-8"))
        plan["label"] = "BUY" + "_NOW"
        _write_json(preflight_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="unsafe research next cycle safety preflight label"):
            build_research_next_cycle_safety_preflight_payload(preflight_input)

        plan["label"] = HUMAN_REVIEW_REQUIRED
        plan["live_trading_" + "enabled"] = True
        _write_json(preflight_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_safety_preflight_payload(preflight_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25a_default_input_uses_phase_preflight_id() -> None:
    preflight_input = build_default_research_next_cycle_safety_preflight_input(now=FIXED_NOW)

    assert preflight_input.preflight_id == "25A-RESEARCH-NEXT-CYCLE-SAFETY-PREFLIGHT-2026-07-07"
    assert preflight_input.preflight_date == "2026-07-07"


def test_25a_cli_writes_next_cycle_safety_preflight() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        preflight_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_safety_preflight.py",
                "--out-dir",
                str(out_dir),
                "--preflight-date",
                "2026-07-07",
                "--next-cycle-plan-path",
                str(preflight_input.next_cycle_plan_path),
                "--rollover-gate-path",
                str(preflight_input.rollover_gate_path),
                "--archive-index-path",
                str(preflight_input.archive_index_path),
                "--operations-console-path",
                str(preflight_input.operations_console_path),
                "--operator-signoff-packet-path",
                str(preflight_input.operator_signoff_packet_path),
                "--readiness-gate-path",
                str(preflight_input.readiness_gate_path),
                "--retention-policy-path",
                str(preflight_input.retention_policy_path),
                "--report-index-path",
                str(preflight_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(preflight_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(preflight_input.queue_status_path),
                "--safety-scanner-path",
                str(preflight_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 25A NEXT CYCLE SAFETY PREFLIGHT: COMPLETE" in completed.stdout
        assert "Next-cycle safety preflight is read-only and records-only" in completed.stdout
        assert "research workflows are not run" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions are created" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_safety_preflight.json").exists()
        assert (out_dir / "research_next_cycle_safety_preflight.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
