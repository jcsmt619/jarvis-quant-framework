from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from automation.safety_scanner import SafetyScanResult
from core.research_cycle_audit_summary import (
    ResearchCycleAuditSummaryInput,
    build_default_research_cycle_audit_summary_input,
    build_research_cycle_audit_summary_payload,
    render_research_cycle_audit_summary_markdown,
    write_research_cycle_audit_summary,
)
from core.research_cycle_runner import build_default_research_cycle_runner_input, run_research_cycle
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_cycle_audit_summary_tests") / uuid.uuid4().hex


def _passed_scan(paths: list[Path]) -> SafetyScanResult:
    return SafetyScanResult(findings=[], scanned_files=len(paths), skipped_files=[])


def _write_19a_cycle(root: Path) -> Path:
    cycle_input = build_default_research_cycle_runner_input(
        now=FIXED_NOW,
        report_root=root,
        manifest_dir=root / "research_cycle_runner",
    )
    _, json_path, _ = run_research_cycle(cycle_input, safety_scanner=_passed_scan)
    return json_path


def test_19b_builds_deterministic_audit_summary_from_19a_manifest() -> None:
    root = _root()
    try:
        manifest_path = _write_19a_cycle(root)
        audit_input = build_default_research_cycle_audit_summary_input(
            now=FIXED_NOW,
            manifest_path=manifest_path,
        )

        first = build_research_cycle_audit_summary_payload(audit_input)
        second = build_research_cycle_audit_summary_payload(audit_input)

        assert first == second
        assert first["phase"] == "19B"
        assert first["workflow"] == "Research Cycle Audit Summary"
        assert first["cycle_manifest_status"]["status"] == "present"
        assert first["summary"]["generated_report_count"] == 8
        assert first["summary"]["missing_artifact_count"] == 1
        assert first["summary"]["skipped_step_count"] == 1
        assert first["summary"]["safety_scanner_status"] == "passed"
        assert first["release_bundle_status"]["workflow_id"] == "research_release_bundle"
        assert first["dashboard_status"]["workflow_id"] == "operator_dashboard_snapshot"
        assert first["queue_status"]["status"] == "read_only"
        assert "review_cycle_manifest" in {
            item["workflow_id"] for item in first["allowed_human_review_workflows"]
        }
        assert "live_trading" in {item["workflow_id"] for item in first["blocked_workflows"]}
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


def test_19b_writes_json_and_markdown_audit_summary() -> None:
    root = _root()
    out_dir = root / "audit"
    try:
        manifest_path = _write_19a_cycle(root)

        json_path, markdown_path = write_research_cycle_audit_summary(
            build_default_research_cycle_audit_summary_input(
                now=FIXED_NOW,
                manifest_path=manifest_path,
            ),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_cycle_audit_summary.json"
        assert markdown_path.name == "research_cycle_audit_summary.md"
        assert payload["audit_id"] == "19B-RESEARCH-CYCLE-AUDIT-SUMMARY-2026-07-07"
        assert "19B Research Cycle Audit Summary" in markdown
        assert "Generated Reports" in markdown
        assert "Allowed Human-Review Workflows" in markdown
        assert "Blocked Workflows" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19b_records_missing_manifest_as_blocked_without_execution() -> None:
    root = _root()
    try:
        payload = build_research_cycle_audit_summary_payload(
            build_default_research_cycle_audit_summary_input(
                now=FIXED_NOW,
                manifest_path=root / "missing" / "research_cycle_manifest.json",
            )
        )
        markdown = render_research_cycle_audit_summary_markdown(payload)

        assert payload["cycle_manifest_status"]["label"] == BLOCKED_BY_SAFETY_GATE
        assert payload["cycle_manifest_status"]["status"] == "missing"
        assert "research_cycle_manifest" in {
            item["workflow_id"] for item in payload["blocked_workflows"]
        }
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19b_rejects_secret_paths_and_unsafe_payloads() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchCycleAuditSummaryInput(
                audit_id="19B-UNSAFE",
                audit_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                manifest_path=Path(".env"),
            ).validate()

        manifest_path = root / "research_cycle_runner" / "research_cycle_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "phase": "19A",
                    "workflow": "Research Cycle Runner",
                    "cycle_id": "19A-UNSAFE",
                    "cycle_date": "2026-07-07",
                    "generated_at_utc": FIXED_NOW.isoformat(),
                    "safety_boundary": {"label": HUMAN_REVIEW_REQUIRED},
                    "summary": {},
                    "command_outcomes": [
                        {
                            "step_id": "unsafe",
                            "status": "completed",
                            "label": HUMAN_REVIEW_REQUIRED,
                            "json_path": str(root / "unsafe.json"),
                            "markdown_path": str(root / "unsafe.md"),
                        }
                    ],
                    "live_trading_" + "enabled": True,
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_cycle_audit_summary_payload(
                build_default_research_cycle_audit_summary_input(
                    now=FIXED_NOW,
                    manifest_path=manifest_path,
                )
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19b_cli_writes_audit_summary() -> None:
    root = _root()
    out_dir = root / "audit"
    try:
        manifest_path = _write_19a_cycle(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_cycle_audit_summary.py",
                "--out-dir",
                str(out_dir),
                "--manifest-path",
                str(manifest_path),
                "--audit-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 19B RESEARCH CYCLE AUDIT SUMMARY: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Allowed human-review workflows are separated from BLOCKED_BY_SAFETY_GATE workflows" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used" in completed.stdout
        assert (out_dir / "research_cycle_audit_summary.json").exists()
        assert (out_dir / "research_cycle_audit_summary.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
