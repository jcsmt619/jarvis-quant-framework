from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.operator_dashboard_snapshot import (
    OperatorDashboardSnapshotInput,
    build_operator_dashboard_snapshot_payload,
    build_default_operator_dashboard_snapshot_input,
    render_operator_dashboard_snapshot_markdown,
    write_operator_dashboard_snapshot,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _snapshot_input(root: Path) -> OperatorDashboardSnapshotInput:
    return OperatorDashboardSnapshotInput(
        snapshot_id="17B-OPERATOR-DASHBOARD-SNAPSHOT-2026-07-07",
        snapshot_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        report_index_path=root / "report_index.json",
        queue_path=root / "queue.json",
        daily_research_path=root / "daily_research.json",
        weekly_review_path=root / "weekly_review.json",
        evidence_pack_path=root / "evidence_pack.json",
        decision_journal_path=root / "decision_journal.json",
        operator_runbook_path=root / "operator_runbook.json",
        safety_scanner_path=root / "safety_scanner.json",
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _workflow_payload(phase: str, workflow: str, date_key: str = "report_date") -> dict[str, object]:
    return {
        "phase": phase,
        "workflow": workflow,
        date_key: "2026-07-07",
        "generated_at_utc": FIXED_NOW.isoformat(),
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
            "live_trading_enabled": False,
            "broker_order_call_performed": False,
            "real_paper_order_submitted": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "experiment_count": 2,
            "blocked_decision_count": 0,
            "safety_scanner_finding_count": 0,
        },
    }


def _write_fixture_reports(root: Path) -> OperatorDashboardSnapshotInput:
    snapshot_input = _snapshot_input(root)
    _write_json(
        snapshot_input.report_index_path,
        {
            "phase": "17A",
            "workflow": "Report Index",
            "index_id": "17A-REPORT-INDEX-2026-07-07",
            "index_date": "2026-07-07",
            "generated_at_utc": FIXED_NOW.isoformat(),
            "safety_boundary": {
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "LIVE TRADING: DISABLED",
                "live_trading_enabled": False,
            },
            "reports": [
                {
                    "report_id": "daily_research_command_center",
                    "report_type": "Daily Research Command Center",
                    "workflow": "Daily Research Command Center",
                    "phase": "15A",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "present",
                    "safety_status": "LIVE TRADING: DISABLED",
                    "generated_date": "2026-07-07",
                    "generated_at_utc": FIXED_NOW.isoformat(),
                    "json_path": snapshot_input.daily_research_path.as_posix(),
                    "markdown_path": "reports/fixture/daily.md",
                    "missing_paths": [],
                },
                {
                    "report_id": "missing_report",
                    "report_type": "Missing Fixture",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "missing",
                    "safety_status": "missing_report",
                    "missing_paths": ["reports/fixture/missing.json"],
                },
            ],
        },
    )
    _write_json(snapshot_input.daily_research_path, _workflow_payload("15A", "Daily Research Command Center"))
    _write_json(snapshot_input.weekly_review_path, _workflow_payload("14B", "Weekly Review", "week_end"))
    _write_json(
        snapshot_input.evidence_pack_path,
        _workflow_payload("16A", "Research Evidence Pack", "evidence_date"),
    )
    _write_json(
        snapshot_input.decision_journal_path,
        {
            **_workflow_payload("16B", "Decision Journal", "journal_date"),
            "allowed_review_workflows": [
                {
                    "workflow_id": "record_human_review_outcome",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "allowed_review_only",
                    "summary": "Record human review without execution state changes.",
                },
            ],
            "blocked_workflows": [
                {
                    "workflow_id": "order_execution",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": "Order execution is blocked.",
                },
            ],
        },
    )
    _write_json(
        snapshot_input.operator_runbook_path,
        {
            **_workflow_payload("15B", "Operator Runbook", "runbook_date"),
            "allowed_human_review_workflows": [
                {
                    "workflow_id": "review_daily_research",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "allowed_review_only",
                    "summary": "Review daily research only.",
                },
            ],
            "blocked_workflows": [
                {
                    "workflow_id": "live_trading",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": "Live trading remains disabled.",
                },
            ],
        },
    )
    _write_json(
        snapshot_input.queue_path,
        [
            {
                "phase": "17B",
                "title": "Operator Dashboard Snapshot",
                "spec": "Build deterministic operator snapshot.",
            },
            {
                "phase": "17C",
                "title": "Future Research Phase",
                "spec": "Placeholder.",
            },
        ],
    )
    _write_json(
        snapshot_input.safety_scanner_path,
        {
            "status": "passed",
            "label": HUMAN_REVIEW_REQUIRED,
            "passed": True,
            "finding_count": 0,
            "findings": [],
            "summary": "Safety scanner passed.",
        },
    )
    return snapshot_input


def test_17b_builds_deterministic_operator_dashboard_snapshot_payload() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    try:
        snapshot_input = _write_fixture_reports(root)

        first = build_operator_dashboard_snapshot_payload(snapshot_input)
        second = build_operator_dashboard_snapshot_payload(snapshot_input)

        assert first == second
        assert first["phase"] == "17B"
        assert first["workflow"] == "Operator Dashboard Snapshot"
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
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        assert first["summary"]["latest_report_index_entry_count"] == 2
        assert first["summary"]["present_report_count"] == 1
        assert first["summary"]["missing_report_count"] == 1
        assert first["summary"]["queue_item_count"] == 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17b_separates_allowed_human_review_from_blocked_workflows() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    try:
        payload = build_operator_dashboard_snapshot_payload(_write_fixture_reports(root))

        allowed = payload["allowed_human_review_workflows"]
        blocked = payload["blocked_workflows"]

        assert {item["label"] for item in allowed} == {HUMAN_REVIEW_REQUIRED}
        assert {item["status"] for item in allowed} == {"allowed_review_only"}
        assert "review_daily_research" in {item["workflow_id"] for item in allowed}
        assert "record_human_review_outcome" in {item["workflow_id"] for item in allowed}
        assert {item["label"] for item in blocked} == {BLOCKED_BY_SAFETY_GATE}
        assert "live_trading" in {item["workflow_id"] for item in blocked}
        assert "order_execution" in {item["workflow_id"] for item in blocked}
        assert "missing_report" in {item["workflow_id"] for item in blocked}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17b_records_missing_inputs_as_blocked_statuses() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    snapshot_input = _snapshot_input(root)

    payload = build_operator_dashboard_snapshot_payload(snapshot_input)

    assert payload["workflow_status"]["daily_research"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["workflow_status"]["daily_research"]["status"] == "missing"
    assert payload["workflow_status"]["queue"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["summary"]["blocked_workflow_count"] >= 6


def test_17b_writes_json_and_markdown_reports() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_operator_dashboard_snapshot(
            _write_fixture_reports(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "operator_dashboard_snapshot.json"
        assert markdown_path.name == "operator_dashboard_snapshot.md"
        assert payload["snapshot_date"] == "2026-07-07"
        assert "17B Operator Dashboard Snapshot" in markdown
        assert "Allowed Human-Review Workflows" in markdown
        assert "Blocked Workflows" in markdown
        assert "Latest Report Index Entries" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17b_rejects_unsafe_labels_execution_flags_and_secret_paths() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    try:
        snapshot_input = _write_fixture_reports(root)
        _write_json(
            snapshot_input.daily_research_path,
            {
                "label": "BUY" + "_NOW",
                "summary": "Unsafe fixture.",
            },
        )

        with pytest.raises(ValueError, match="unsafe operator dashboard label"):
            build_operator_dashboard_snapshot_payload(snapshot_input)

        _write_json(
            snapshot_input.daily_research_path,
            {
                "label": HUMAN_REVIEW_REQUIRED,
                "live_trading_" + "enabled": True,
            },
        )
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_operator_dashboard_snapshot_payload(snapshot_input)

        with pytest.raises(ValueError, match="secret files"):
            build_operator_dashboard_snapshot_payload(
                OperatorDashboardSnapshotInput(
                    snapshot_id="17B-UNSAFE",
                    snapshot_date="2026-07-07",
                    generated_at_utc=FIXED_NOW.isoformat(),
                    report_index_path=Path(".env"),
                )
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17b_markdown_lists_empty_or_missing_sections() -> None:
    root = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    payload = build_operator_dashboard_snapshot_payload(_snapshot_input(root))

    markdown = render_operator_dashboard_snapshot_markdown(payload)

    assert "- Missing reports:" in markdown
    assert "daily_research | BLOCKED_BY_SAFETY_GATE | blocked" in markdown
    assert "Allowed Human-Review Workflows" in markdown


def test_17b_default_input_uses_phase_snapshot_id() -> None:
    snapshot_input = build_default_operator_dashboard_snapshot_input(now=FIXED_NOW)

    assert snapshot_input.snapshot_id == "17B-OPERATOR-DASHBOARD-SNAPSHOT-2026-07-07"
    assert snapshot_input.snapshot_date == "2026-07-07"


def test_17b_runner_writes_reports() -> None:
    out_dir = Path("reports/operator_dashboard_snapshot_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_operator_dashboard_snapshot.py",
                "--out-dir",
                str(out_dir),
                "--snapshot-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 17B OPERATOR DASHBOARD SNAPSHOT: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE workflows remain separated" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "operator_dashboard_snapshot.json").exists()
        assert (out_dir / "operator_dashboard_snapshot.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
