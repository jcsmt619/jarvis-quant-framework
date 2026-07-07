from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_plan import (
    BLOCKED_BY_SAFETY_GATE,
    NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW,
    ResearchNextCyclePlanInput,
    build_default_research_next_cycle_plan_input,
    build_research_next_cycle_plan_payload,
    render_research_next_cycle_plan_markdown,
    write_research_next_cycle_plan,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 45, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_plan_tests") / uuid.uuid4().hex


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


def _plan_input(root: Path) -> ResearchNextCyclePlanInput:
    return ResearchNextCyclePlanInput(
        next_cycle_plan_id="24B-RESEARCH-NEXT-CYCLE-PLAN-2026-07-07",
        next_cycle_plan_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
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


def _write_ready_inputs(root: Path) -> ResearchNextCyclePlanInput:
    plan_input = _plan_input(root)
    payloads = {
        plan_input.rollover_gate_path: {
            **_artifact_payload("24A", "Research Cycle Rollover Gate", "rollover_gate_date"),
            "rollover_state": "ROLLOVER_READY_FOR_HUMAN_REVIEW",
            "required_operator_actions": [],
            "safety_findings": [],
        },
        plan_input.archive_index_path: {
            **_artifact_payload("23B", "Research Cycle Archive Index", "archive_index_date"),
            "archive_index_state": "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY",
            "human_review_notes": [],
        },
        plan_input.operations_console_path: {
            **_artifact_payload("23A", "Research Operations Console", "console_date"),
            "console_state": "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY",
            "required_operator_actions": [],
            "open_items": [],
        },
        plan_input.operator_signoff_packet_path: {
            **_artifact_payload("22B", "Operator Signoff Packet", "signoff_date"),
            "signoff_state": "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY",
        },
        plan_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        plan_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [],
            "dry_run_manifest": [],
        },
        plan_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        plan_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        plan_input.safety_scanner_path: {
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
        plan_input.queue_status_path,
        [
            {
                "phase": "24B",
                "title": "Next Research Cycle Plan",
                "spec": "Build deterministic planning reports.",
            },
            {
                "phase": "24C",
                "title": "Next Records-Only Research Drill",
                "spec": "Plan-only queued research/report workflow.",
            },
        ],
    )
    return plan_input


def test_24b_builds_deterministic_records_only_next_cycle_plan() -> None:
    root = _root()
    try:
        plan_input = _write_ready_inputs(root)

        first = build_research_next_cycle_plan_payload(plan_input)
        second = build_research_next_cycle_plan_payload(plan_input)

        assert first == second
        assert first["phase"] == "24B"
        assert first["workflow"] == "Next Research Cycle Plan"
        assert first["next_cycle_plan_state"] == NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW
        assert first["summary"]["source_artifact_count"] == 9
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["planned_workflow_count"] == 1
        assert first["planned_research_report_workflows"][0]["phase"] == "24C"
        assert first["planned_research_report_workflows"][0]["run_started"] is False
        assert first["summary"]["required_refreshed_artifact_count"] == 3
        assert first["summary"]["blocked_prerequisite_count"] == 0
        assert first["safety_boundary"]["records_only"] is True
        assert first["safety_boundary"]["next_cycle_started"] is False
        assert first["safety_boundary"]["artifact_mutation_performed"] is False
        assert first["safety_boundary"]["trade_instructions_created"] is False
        assert first["safety_boundary"]["broker_actions_created"] is False
        assert first["safety_boundary"]["execution_permissions_created"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["broker_order_routing_enabled"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        assert all("payload" not in item for item in first["source_artifacts"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24b_writes_json_and_markdown_next_cycle_plan() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_plan(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_plan.json"
        assert markdown_path.name == "research_next_cycle_plan.md"
        assert payload["next_cycle_plan_id"] == "24B-RESEARCH-NEXT-CYCLE-PLAN-2026-07-07"
        assert "24B Next Research Cycle Plan" in markdown
        assert "Planned Research and Report Workflows" in markdown
        assert "Next-Cycle Acceptance Criteria" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24b_classifies_blocked_for_missing_rollover_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        plan_input = _write_ready_inputs(root)
        plan_input.rollover_gate_path.unlink()
        _write_json(
            plan_input.safety_scanner_path,
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

        payload = build_research_next_cycle_plan_payload(plan_input)
        markdown = render_research_next_cycle_plan_markdown(payload)

        assert payload["next_cycle_plan_state"] == BLOCKED_BY_SAFETY_GATE
        assert "rollover_gate" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_rollover_gate" in {item["prerequisite_id"] for item in payload["blocked_prerequisites"]}
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "24B-PREFLIGHT-SAFETY-SCANNER" in {
            item["preflight_id"] for item in payload["safety_preflight_items"] if item["label"] == BLOCKED_BY_SAFETY_GATE
        }
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCyclePlanInput(
                next_cycle_plan_id="24B-UNSAFE",
                next_cycle_plan_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                rollover_gate_path=Path(".env"),
            ).validate()

        plan_input = _write_ready_inputs(root)
        rollover = json.loads(plan_input.rollover_gate_path.read_text(encoding="utf-8"))
        rollover["label"] = "BUY" + "_NOW"
        _write_json(plan_input.rollover_gate_path, rollover)
        with pytest.raises(ValueError, match="unsafe research next cycle plan label"):
            build_research_next_cycle_plan_payload(plan_input)

        rollover["label"] = HUMAN_REVIEW_REQUIRED
        rollover["live_trading_" + "enabled"] = True
        _write_json(plan_input.rollover_gate_path, rollover)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_plan_payload(plan_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24b_default_input_uses_phase_next_cycle_plan_id() -> None:
    plan_input = build_default_research_next_cycle_plan_input(now=FIXED_NOW)

    assert plan_input.next_cycle_plan_id == "24B-RESEARCH-NEXT-CYCLE-PLAN-2026-07-07"
    assert plan_input.next_cycle_plan_date == "2026-07-07"


def test_24b_cli_writes_research_next_cycle_plan() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        plan_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_plan.py",
                "--out-dir",
                str(out_dir),
                "--next-cycle-plan-date",
                "2026-07-07",
                "--rollover-gate-path",
                str(plan_input.rollover_gate_path),
                "--archive-index-path",
                str(plan_input.archive_index_path),
                "--operations-console-path",
                str(plan_input.operations_console_path),
                "--operator-signoff-packet-path",
                str(plan_input.operator_signoff_packet_path),
                "--readiness-gate-path",
                str(plan_input.readiness_gate_path),
                "--retention-policy-path",
                str(plan_input.retention_policy_path),
                "--report-index-path",
                str(plan_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(plan_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(plan_input.queue_status_path),
                "--safety-scanner-path",
                str(plan_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 24B NEXT RESEARCH CYCLE PLAN: COMPLETE" in completed.stdout
        assert "Next-cycle plan is read-only and records-only" in completed.stdout
        assert "The next cycle is not run and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions are created" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_plan.json").exists()
        assert (out_dir / "research_next_cycle_plan.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
