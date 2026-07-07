from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.report_index import (
    ReportIndexInput,
    ReportIndexTarget,
    build_default_report_index_input,
    build_report_index_payload,
    render_report_index_markdown,
    write_report_index,
)
from risk.policies import HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _target(root: Path, report_id: str = "daily") -> ReportIndexTarget:
    return ReportIndexTarget(
        report_id=report_id,
        report_type="Daily Research Command Center",
        json_path=root / report_id / "report.json",
        markdown_path=root / report_id / "report.md",
    )


def _index_input(*targets: ReportIndexTarget) -> ReportIndexInput:
    return ReportIndexInput(
        index_id="17A-REPORT-INDEX-2026-07-07",
        index_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        targets=targets,
    )


def test_17a_builds_deterministic_report_index_payload() -> None:
    root = Path("reports/report_index_tests") / uuid.uuid4().hex
    target = _target(root)
    target.json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.json_path.write_text(
            json.dumps(
                {
                    "phase": "15A",
                    "workflow": "Daily Research Command Center",
                    "report_date": "2026-07-07",
                    "generated_at_utc": FIXED_NOW.isoformat(),
                    "safety_boundary": {
                        "label": HUMAN_REVIEW_REQUIRED,
                        "live_trading_enabled": False,
                        "broker_order_call_performed": False,
                        "status": "LIVE TRADING: DISABLED",
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        target.markdown_path.write_text("# report\n", encoding="utf-8")

        first = build_report_index_payload(_index_input(target))
        second = build_report_index_payload(_index_input(target))

        assert first == second
        assert first["phase"] == "17A"
        assert first["workflow"] == "Report Index"
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["real_paper_order_submitted"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        assert first["summary"]["present_report_count"] == 1
        assert first["summary"]["missing_report_count"] == 0
        assert first["reports"][0]["generated_date"] == "2026-07-07"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17a_records_missing_reports_without_opening_unrelated_files() -> None:
    root = Path("reports/report_index_tests") / uuid.uuid4().hex
    target = _target(root, "missing_report")

    payload = build_report_index_payload(_index_input(target))

    assert payload["summary"]["present_report_count"] == 0
    assert payload["summary"]["missing_report_count"] == 1
    assert payload["reports"][0]["label"] == "BLOCKED_BY_SAFETY_GATE"
    assert payload["reports"][0]["safety_status"] == "missing_report"
    assert payload["missing_reports"][0]["missing_paths"] == [
        (root / "missing_report" / "report.json").as_posix(),
        (root / "missing_report" / "report.md").as_posix(),
    ]


def test_17a_writes_json_and_markdown_reports() -> None:
    root = Path("reports/report_index_tests") / uuid.uuid4().hex
    out_dir = root / "out"
    target = _target(root, "present_report")
    target.json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.json_path.write_text(
            json.dumps(
                {
                    "workflow": "Weekly Review",
                    "week_end": "2026-07-07",
                    "generated_at_utc": FIXED_NOW.isoformat(),
                    "safety_boundary": {"label": HUMAN_REVIEW_REQUIRED},
                }
            ),
            encoding="utf-8",
        )
        target.markdown_path.write_text("# report\n", encoding="utf-8")

        json_path, markdown_path = write_report_index(_index_input(target), out_dir=out_dir)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "report_index.json"
        assert markdown_path.name == "report_index.md"
        assert payload["index_id"] == "17A-REPORT-INDEX-2026-07-07"
        assert "17A Report Index" in markdown
        assert "HUMAN_REVIEW_REQUIRED" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17a_rejects_unsafe_labels_execution_flags_and_secret_paths() -> None:
    root = Path("reports/report_index_tests") / uuid.uuid4().hex
    target = _target(root, "unsafe_report")
    target.json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.json_path.write_text(
            json.dumps({"label": "BUY" + "_NOW"}),
            encoding="utf-8",
        )
        target.markdown_path.write_text("# report\n", encoding="utf-8")

        with pytest.raises(ValueError, match="unsafe report index label"):
            build_report_index_payload(_index_input(target))

        target.json_path.write_text(
            json.dumps(
                {
                    "label": HUMAN_REVIEW_REQUIRED,
                    "live_trading_enabled": True,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_report_index_payload(_index_input(target))

        with pytest.raises(ValueError, match="secret files"):
            build_report_index_payload(
                _index_input(
                    ReportIndexTarget(
                        report_id="secret",
                        report_type="Secret",
                        json_path=Path(".env"),
                        markdown_path=Path("reports/report_index/secret.md"),
                    )
                )
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_17a_markdown_lists_missing_reports() -> None:
    root = Path("reports/report_index_tests") / uuid.uuid4().hex
    payload = build_report_index_payload(_index_input(_target(root, "missing_report")))

    markdown = render_report_index_markdown(payload)

    assert "- Missing reports: 1" in markdown
    assert "missing_report | BLOCKED_BY_SAFETY_GATE | missing_report" in markdown


def test_17a_default_targets_include_major_reports() -> None:
    payload = build_report_index_payload(build_default_report_index_input(now=FIXED_NOW))
    report_ids = {item["report_id"] for item in payload["reports"]}

    assert {
        "daily_research_command_center",
        "weekly_review",
        "operator_runbook",
        "research_evidence_pack",
        "decision_journal",
        "promotion_gate_outputs",
        "champion_challenger_outcomes",
        "safety_scanner_status",
    } <= report_ids


def test_17a_runner_writes_reports() -> None:
    out_dir = Path("reports/report_index_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_report_index.py",
                "--out-dir",
                str(out_dir),
                "--index-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 17A REPORT INDEX: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "report_index.json").exists()
        assert (out_dir / "report_index.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
