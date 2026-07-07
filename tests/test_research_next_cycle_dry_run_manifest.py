from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_next_cycle_dry_run_manifest import (
    BLOCKED_BY_SAFETY_GATE,
    DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW,
    ResearchNextCycleDryRunManifestInput,
    build_default_research_next_cycle_dry_run_manifest_input,
    build_research_next_cycle_dry_run_manifest_payload,
    render_research_next_cycle_dry_run_manifest_markdown,
    write_research_next_cycle_dry_run_manifest,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 59, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_next_cycle_dry_run_manifest_tests") / uuid.uuid4().hex


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


def _manifest_input(root: Path) -> ResearchNextCycleDryRunManifestInput:
    return ResearchNextCycleDryRunManifestInput(
        dry_run_manifest_id="25B-RESEARCH-NEXT-CYCLE-DRY-RUN-MANIFEST-2026-07-07",
        dry_run_manifest_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        safety_preflight_path=root / "research_next_cycle_safety_preflight" / "research_next_cycle_safety_preflight.json",
        next_cycle_plan_path=root / "research_next_cycle_plan" / "research_next_cycle_plan.json",
        rollover_gate_path=root / "research_cycle_rollover_gate" / "research_cycle_rollover_gate.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchNextCycleDryRunManifestInput:
    manifest_input = _manifest_input(root)
    payloads = {
        manifest_input.safety_preflight_path: {
            **_artifact_payload("25A", "Next Cycle Safety Preflight", "preflight_date"),
            "preflight_state": "PREFLIGHT_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "required_operator_actions": [],
            "safety_preflight_items": [],
            "safety_findings": [],
        },
        manifest_input.next_cycle_plan_path: {
            **_artifact_payload("24B", "Next Research Cycle Plan", "next_cycle_plan_date"),
            "next_cycle_plan_state": "NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW",
            "blocked_prerequisites": [],
            "required_refreshed_artifacts": [],
            "operator_review_items": [],
            "planned_research_report_workflows": [
                {
                    "workflow_id": "planned_25c",
                    "phase": "25C",
                    "title": "Next Records-Only Research Report",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "planned_not_started",
                    "summary": "Queued records-only reporting workflow.",
                    "run_started": False,
                }
            ],
            "safety_findings": [],
        },
        manifest_input.rollover_gate_path: {
            **_artifact_payload("24A", "Research Cycle Rollover Gate", "rollover_gate_date"),
            "rollover_state": "ROLLOVER_READY_FOR_HUMAN_REVIEW",
            "blocked_items": [],
            "required_operator_actions": [],
            "safety_findings": [],
        },
        manifest_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        manifest_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        manifest_input.safety_scanner_path: {
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
        manifest_input.queue_status_path,
        [
            {
                "phase": "25B",
                "title": "Next Cycle Dry Run Manifest",
                "spec": "Build deterministic dry-run manifest records.",
            },
            {
                "phase": "25C",
                "title": "Next Records-Only Research Report",
                "spec": "Queued records-only reporting workflow.",
            },
        ],
    )
    return manifest_input


def test_25b_builds_deterministic_dry_run_manifest() -> None:
    root = _root()
    try:
        manifest_input = _write_ready_inputs(root)

        first = build_research_next_cycle_dry_run_manifest_payload(manifest_input)
        second = build_research_next_cycle_dry_run_manifest_payload(manifest_input)

        assert first == second
        assert first["phase"] == "25B"
        assert first["workflow"] == "Next Cycle Dry Run Manifest"
        assert first["dry_run_manifest_state"] == DRY_RUN_MANIFEST_READY_FOR_HUMAN_REVIEW
        assert first["summary"]["source_artifact_count"] == 5
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["planned_step_count"] == 1
        assert first["planned_next_cycle_steps"][0]["phase"] == "25C"
        assert first["planned_next_cycle_steps"][0]["would_run"] is False
        assert first["command_hints"][0]["executed"] is False
        assert first["command_hints"][0]["would_run"] is False
        assert first["skipped_steps"][0]["executed"] is False
        assert first["safety_boundary"]["dry_run_only"] is True
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


def test_25b_writes_json_and_markdown_manifest() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_next_cycle_dry_run_manifest(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_next_cycle_dry_run_manifest.json"
        assert markdown_path.name == "research_next_cycle_dry_run_manifest.md"
        assert payload["dry_run_manifest_id"] == "25B-RESEARCH-NEXT-CYCLE-DRY-RUN-MANIFEST-2026-07-07"
        assert "25B Next Cycle Dry Run Manifest" in markdown
        assert "Planned Next-Cycle Steps" in markdown
        assert "Command Hints" in markdown
        assert "Expected Output Artifacts" in markdown
        assert "Skipped Steps" in markdown
        assert "Acceptance Criteria" in markdown
        assert "records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25b_classifies_blocked_for_missing_preflight_and_failed_safety_scanner() -> None:
    root = _root()
    try:
        manifest_input = _write_ready_inputs(root)
        manifest_input.safety_preflight_path.unlink()
        _write_json(
            manifest_input.safety_scanner_path,
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

        payload = build_research_next_cycle_dry_run_manifest_payload(manifest_input)
        markdown = render_research_next_cycle_dry_run_manifest_markdown(payload)

        assert payload["dry_run_manifest_state"] == BLOCKED_BY_SAFETY_GATE
        assert "safety_preflight" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "missing_safety_preflight" in {item["prerequisite_id"] for item in payload["blocked_prerequisites"]}
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert payload["skipped_steps"][0]["label"] == BLOCKED_BY_SAFETY_GATE
        assert BLOCKED_BY_SAFETY_GATE in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchNextCycleDryRunManifestInput(
                dry_run_manifest_id="25B-UNSAFE",
                dry_run_manifest_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                safety_preflight_path=Path(".env"),
            ).validate()

        manifest_input = _write_ready_inputs(root)
        plan = json.loads(manifest_input.next_cycle_plan_path.read_text(encoding="utf-8"))
        plan["label"] = "BUY" + "_NOW"
        _write_json(manifest_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="unsafe research next cycle dry-run manifest label"):
            build_research_next_cycle_dry_run_manifest_payload(manifest_input)

        plan["label"] = HUMAN_REVIEW_REQUIRED
        plan["live_trading_" + "enabled"] = True
        _write_json(manifest_input.next_cycle_plan_path, plan)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_next_cycle_dry_run_manifest_payload(manifest_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_25b_default_input_uses_phase_manifest_id() -> None:
    manifest_input = build_default_research_next_cycle_dry_run_manifest_input(now=FIXED_NOW)

    assert manifest_input.dry_run_manifest_id == "25B-RESEARCH-NEXT-CYCLE-DRY-RUN-MANIFEST-2026-07-07"
    assert manifest_input.dry_run_manifest_date == "2026-07-07"


def test_25b_cli_writes_next_cycle_dry_run_manifest() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        manifest_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_next_cycle_dry_run_manifest.py",
                "--out-dir",
                str(out_dir),
                "--dry-run-manifest-date",
                "2026-07-07",
                "--safety-preflight-path",
                str(manifest_input.safety_preflight_path),
                "--next-cycle-plan-path",
                str(manifest_input.next_cycle_plan_path),
                "--rollover-gate-path",
                str(manifest_input.rollover_gate_path),
                "--report-index-path",
                str(manifest_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(manifest_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(manifest_input.queue_status_path),
                "--safety-scanner-path",
                str(manifest_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 25B NEXT CYCLE DRY RUN MANIFEST: COMPLETE" in completed.stdout
        assert "Next-cycle dry-run manifest is read-only and records-only" in completed.stdout
        assert "Command hints are inert records only and are not executed" in completed.stdout
        assert "The next cycle is not run and artifacts are not mutated or deleted" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, or order paths are created" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_next_cycle_dry_run_manifest.json").exists()
        assert (out_dir / "research_next_cycle_dry_run_manifest.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
