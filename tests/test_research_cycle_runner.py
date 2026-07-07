from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from automation.safety_scanner import SafetyFinding, SafetyScanResult
from core.research_cycle_runner import (
    ResearchCycleRunnerInput,
    build_default_research_cycle_runner_input,
    run_research_cycle,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_cycle_runner_tests") / uuid.uuid4().hex


def _passed_scan(paths: list[Path]) -> SafetyScanResult:
    return SafetyScanResult(findings=[], scanned_files=len(paths), skipped_files=[])


def test_19a_runs_cycle_in_order_and_writes_manifests() -> None:
    root = _root()
    try:
        cycle_input = build_default_research_cycle_runner_input(
            now=FIXED_NOW,
            report_root=root,
            manifest_dir=root / "research_cycle_runner",
        )

        manifest, json_path, markdown_path = run_research_cycle(
            cycle_input,
            safety_scanner=_passed_scan,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")
        step_ids = [item["step_id"] for item in payload["command_outcomes"]]

        assert manifest == payload
        assert payload["phase"] == "19A"
        assert payload["workflow"] == "Research Cycle Runner"
        assert step_ids == [
            "daily_research_command_center",
            "weekly_review",
            "operator_runbook",
            "research_evidence_pack",
            "decision_journal",
            "report_index",
            "operator_dashboard_snapshot",
            "safe_workflow_catalog",
            "research_release_bundle",
        ]
        assert payload["command_outcomes"][1]["status"] == "skipped"
        assert payload["summary"]["skipped_step_count"] == 1
        assert payload["summary"]["safety_scanner_status"] == "passed"
        assert "weekly_review" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "LIVE TRADING: DISABLED" in markdown
        assert (root / "daily_research_command_center" / "daily_research_summary.json").exists()
        assert (root / "research_release_bundle" / "research_release_bundle.json").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19a_can_write_requested_weekly_review() -> None:
    root = _root()
    try:
        cycle_input = build_default_research_cycle_runner_input(
            now=FIXED_NOW,
            report_root=root,
            manifest_dir=root / "research_cycle_runner",
            include_weekly_review=True,
        )

        manifest, _, _ = run_research_cycle(cycle_input, safety_scanner=_passed_scan)

        weekly = [item for item in manifest["command_outcomes"] if item["step_id"] == "weekly_review"][0]
        assert weekly["status"] == "completed"
        assert manifest["summary"]["skipped_step_count"] == 0
        assert not [item for item in manifest["missing_artifacts"] if item["artifact_id"] == "weekly_review"]
        assert (root / "weekly_review" / "weekly_review.json").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19a_records_blocked_safety_scanner_status() -> None:
    root = _root()

    def blocked_scan(paths: list[Path]) -> SafetyScanResult:
        return SafetyScanResult(
            findings=[
                SafetyFinding(
                    path="candidate.py",
                    line_number=1,
                    rule_id="LIVE_TRADING_ENABLEMENT",
                    description="Blocks live-trading enablement flags.",
                    excerpt="live_trading_" + "enabled = " + "True",
                )
            ],
            scanned_files=1,
            skipped_files=[],
        )

    try:
        cycle_input = build_default_research_cycle_runner_input(
            now=FIXED_NOW,
            report_root=root,
            manifest_dir=root / "research_cycle_runner",
        )

        manifest, _, _ = run_research_cycle(cycle_input, safety_scanner=blocked_scan)

        safety = manifest["safety_scanner_status"]
        blocked_ids = {item["workflow_id"] for item in manifest["blocked_workflows"]}
        assert safety["status"] == "blocked"
        assert safety["label"] == BLOCKED_BY_SAFETY_GATE
        assert safety["finding_count"] == 1
        assert "safety_scanner" in blocked_ids
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19a_safety_boundary_stays_disabled() -> None:
    cycle_input = build_default_research_cycle_runner_input(now=FIXED_NOW)

    assert cycle_input.cycle_id == "19A-RESEARCH-CYCLE-RUNNER-2026-07-07"

    root = _root()
    try:
        manifest, _, _ = run_research_cycle(
            build_default_research_cycle_runner_input(
                now=FIXED_NOW,
                report_root=root,
                manifest_dir=root / "research_cycle_runner",
            ),
            safety_scanner=_passed_scan,
        )

        boundary = manifest["safety_boundary"]
        assert boundary["label"] == HUMAN_REVIEW_REQUIRED
        assert boundary["research_only"] is True
        assert boundary["monitor_only"] is True
        assert boundary["paper_only"] is True
        assert boundary["human_review_required"] is True
        assert boundary["real_paper_wrapper_connected"] is False
        assert boundary["real_paper_wrapper_attempted"] is False
        assert boundary["real_paper_order_submitted"] is False
        assert boundary["broker_order_call_performed"] is False
        assert boundary["broker_order_routing_enabled"] is False
        assert boundary["live_trading_enabled"] is False
        assert boundary["secrets_required"] is False
        assert boundary["credential_file_used"] is False
        assert boundary["status"] == "LIVE TRADING: DISABLED"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_19a_rejects_secret_paths() -> None:
    with pytest.raises(ValueError, match="secret files"):
        ResearchCycleRunnerInput(
            cycle_id="19A-UNSAFE",
            cycle_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            report_root=Path(".env"),
        ).validate()


def test_19a_cli_writes_manifest() -> None:
    root = _root()
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_cycle_runner.py",
                "--report-root",
                str(root),
                "--manifest-dir",
                str(root / "research_cycle_runner"),
                "--cycle-date",
                "2026-07-07",
                "--include-weekly-review",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 19A RESEARCH CYCLE RUNNER: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used" in completed.stdout
        assert (root / "research_cycle_runner" / "research_cycle_manifest.json").exists()
        assert (root / "research_cycle_runner" / "research_cycle_manifest.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
