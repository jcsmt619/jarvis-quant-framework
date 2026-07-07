from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_cycle_readiness_gate import (
    BLOCKED_BY_SAFETY_GATE,
    NEEDS_OPERATOR_REVIEW,
    READY_FOR_HUMAN_REVIEW,
    ResearchCycleReadinessGateInput,
    build_default_research_cycle_readiness_gate_input,
    build_research_cycle_readiness_gate_payload,
    render_research_cycle_readiness_gate_markdown,
    write_research_cycle_readiness_gate,
)
from risk.policies import HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_cycle_readiness_gate_tests") / uuid.uuid4().hex


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_payload(
    phase: str,
    workflow: str,
    date_key: str,
    *,
    day: str = "2026-07-07",
) -> dict[str, object]:
    return {
        "phase": phase,
        "workflow": workflow,
        date_key: day,
        "generated_at_utc": f"{day}T19:00:00+00:00",
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
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
            "secrets_required": False,
            "credential_file_used": False,
            "prohibited_trade_labels_present": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "missing_artifact_count": 0,
            "skipped_step_count": 0,
            "blocked_workflow_count": 0,
            "safety_scanner_finding_count": 0,
        },
    }


def _gate_input(root: Path) -> ResearchCycleReadinessGateInput:
    return ResearchCycleReadinessGateInput(
        gate_id="20A-RESEARCH-CYCLE-READINESS-GATE-2026-07-07",
        gate_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        manifest_path=root / "research_cycle_runner" / "research_cycle_manifest.json",
        audit_summary_path=root / "research_cycle_audit_summary" / "research_cycle_audit_summary.json",
        release_bundle_path=root / "research_release_bundle" / "research_release_bundle.json",
        operator_dashboard_snapshot_path=(
            root / "operator_dashboard_snapshot" / "operator_dashboard_snapshot.json"
        ),
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _write_ready_inputs(root: Path) -> ResearchCycleReadinessGateInput:
    gate_input = _gate_input(root)
    payloads = {
        gate_input.manifest_path: {
            **_artifact_payload("19A", "Research Cycle Runner", "cycle_date"),
            "cycle_id": "19A-RESEARCH-CYCLE-RUNNER-2026-07-07",
            "skipped_steps": [],
            "missing_artifacts": [],
            "blocked_workflows": [
                {
                    "workflow_id": "live_trading",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": "Live trading remains disabled.",
                }
            ],
            "safety_scanner_status": {
                "workflow_id": "safety_scanner",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "passed",
                "passed": True,
                "finding_count": 0,
                "findings": [],
            },
        },
        gate_input.audit_summary_path: _artifact_payload(
            "19B",
            "Research Cycle Audit Summary",
            "audit_date",
        ),
        gate_input.release_bundle_path: _artifact_payload(
            "18B",
            "Research Release Bundle",
            "bundle_date",
        ),
        gate_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
        ),
        gate_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date"),
        gate_input.safe_workflow_catalog_path: {
            **_artifact_payload("18A", "Safe Workflow Catalog", "catalog_date"),
            "workflows": [{"workflow_id": "report_index"}],
            "blocked_behaviors": ["enable live trading"],
        },
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
        gate_input.queue_path,
        [
            {
                "phase": "20A",
                "title": "Research Cycle Readiness Gate",
                "spec": "Build deterministic readiness gate.",
            }
        ],
    )
    return gate_input


def test_20a_builds_ready_for_human_review_gate() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)

        first = build_research_cycle_readiness_gate_payload(gate_input)
        second = build_research_cycle_readiness_gate_payload(gate_input)

        assert first == second
        assert first["phase"] == "20A"
        assert first["workflow"] == "Research Cycle Readiness Gate"
        assert first["decision"] == READY_FOR_HUMAN_REVIEW
        assert first["summary"]["required_artifact_count"] == 7
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["skipped_step_count"] == 0
        assert first["summary"]["stale_report_count"] == 0
        assert first["summary"]["failed_safety_finding_count"] == 0
        assert first["queue_status"]["next_phase"]["phase"] == "20A"
        assert first["safety_boundary"]["real_paper_wrapper_connected"] is False
        assert first["safety_boundary"]["real_paper_wrapper_attempted"] is False
        assert first["safety_boundary"]["real_paper_order_submitted"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["broker_order_routing_enabled"] is False
        assert first["safety_boundary"]["broker_routing_used"] is False
        assert first["safety_boundary"]["broker_call_used"] is False
        assert first["safety_boundary"]["order_execution_used"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["secrets_required"] is False
        assert first["safety_boundary"]["credential_file_used"] is False
        assert first["safety_boundary"]["prohibited_trade_labels_present"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20a_writes_json_and_markdown_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_cycle_readiness_gate(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_cycle_readiness_gate.json"
        assert markdown_path.name == "research_cycle_readiness_gate.md"
        assert payload["gate_id"] == "20A-RESEARCH-CYCLE-READINESS-GATE-2026-07-07"
        assert "20A Research Cycle Readiness Gate" in markdown
        assert "Decision: READY_FOR_HUMAN_REVIEW" in markdown
        assert "Missing Artifacts" in markdown
        assert "Skipped Steps" in markdown
        assert "Stale Reports" in markdown
        assert "Required Human-Review Actions" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20a_blocks_missing_artifacts_and_failed_safety_findings() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)
        gate_input.report_index_path.unlink()
        _write_json(
            gate_input.safety_scanner_path,
            {
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Safety scanner found a blocked condition.",
                "passed": False,
                "finding_count": 1,
                "findings": [{"rule_id": "unsafe_fixture", "summary": "Unsafe fixture."}],
            },
        )

        payload = build_research_cycle_readiness_gate_payload(gate_input)
        markdown = render_research_cycle_readiness_gate_markdown(payload)

        assert payload["decision"] == BLOCKED_BY_SAFETY_GATE
        assert payload["missing_artifacts"][0]["artifact_id"] == "report_index"
        assert "unsafe_fixture" in {
            item["finding_id"] for item in payload["failed_safety_findings"]
        }
        assert "BLOCKED_BY_SAFETY_GATE" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20a_needs_operator_review_for_skipped_steps_and_stale_reports() -> None:
    root = _root()
    try:
        gate_input = _write_ready_inputs(root)
        manifest = json.loads(gate_input.manifest_path.read_text(encoding="utf-8"))
        manifest["skipped_steps"] = [
            {
                "step_id": "weekly_review",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "skipped",
                "summary": "Weekly review was not requested.",
            }
        ]
        _write_json(gate_input.manifest_path, manifest)
        stale_dashboard = _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
            day="2026-07-01",
        )
        _write_json(gate_input.operator_dashboard_snapshot_path, stale_dashboard)

        payload = build_research_cycle_readiness_gate_payload(gate_input)

        assert payload["decision"] == NEEDS_OPERATOR_REVIEW
        assert payload["skipped_steps"][0]["step_id"] == "weekly_review"
        assert payload["stale_reports"][0]["artifact_id"] == "operator_dashboard_snapshot"
        assert "20A-REVIEW-SKIPPED-STEPS" in {
            item["action_id"] for item in payload["required_human_review_actions"]
        }
        assert "20A-REFRESH-STALE-REPORTS" in {
            item["action_id"] for item in payload["required_human_review_actions"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20a_rejects_secret_paths_and_unsafe_payloads() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchCycleReadinessGateInput(
                gate_id="20A-UNSAFE",
                gate_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                manifest_path=Path(".env"),
            ).validate()

        gate_input = _write_ready_inputs(root)
        manifest = json.loads(gate_input.manifest_path.read_text(encoding="utf-8"))
        manifest["live_trading_" + "enabled"] = True
        _write_json(gate_input.manifest_path, manifest)

        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_cycle_readiness_gate_payload(gate_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20a_default_input_uses_phase_gate_id() -> None:
    gate_input = build_default_research_cycle_readiness_gate_input(now=FIXED_NOW)

    assert gate_input.gate_id == "20A-RESEARCH-CYCLE-READINESS-GATE-2026-07-07"
    assert gate_input.gate_date == "2026-07-07"


def test_20a_cli_writes_readiness_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        gate_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_cycle_readiness_gate.py",
                "--out-dir",
                str(out_dir),
                "--gate-date",
                "2026-07-07",
                "--manifest-path",
                str(gate_input.manifest_path),
                "--audit-summary-path",
                str(gate_input.audit_summary_path),
                "--release-bundle-path",
                str(gate_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(gate_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(gate_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(gate_input.safe_workflow_catalog_path),
                "--queue-path",
                str(gate_input.queue_path),
                "--safety-scanner-path",
                str(gate_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 20A RESEARCH CYCLE READINESS GATE: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Decision is one of READY_FOR_HUMAN_REVIEW, BLOCKED_BY_SAFETY_GATE, NEEDS_OPERATOR_REVIEW" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used" in completed.stdout
        assert (out_dir / "research_cycle_readiness_gate.json").exists()
        assert (out_dir / "research_cycle_readiness_gate.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
