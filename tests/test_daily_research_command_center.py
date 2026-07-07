from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from automation.safety_scanner import scan_paths
from core.daily_research_command_center import (
    DailyResearchInput,
    build_daily_research_payload,
    build_default_daily_research_input,
    render_daily_research_markdown,
    write_daily_research_summary,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def test_15a_builds_deterministic_daily_research_payload() -> None:
    report_input = build_default_daily_research_input(now=FIXED_NOW)

    first = build_daily_research_payload(report_input)
    second = build_daily_research_payload(report_input)

    assert first == second
    assert first["phase"] == "15A"
    assert first["workflow"] == "Daily Research Command Center"
    assert first["safety_boundary"]["real_paper_wrapper_connected"] is False
    assert first["safety_boundary"]["real_paper_wrapper_attempted"] is False
    assert first["safety_boundary"]["real_paper_order_submitted"] is False
    assert first["safety_boundary"]["broker_order_call_performed"] is False
    assert first["safety_boundary"]["live_trading_enabled"] is False
    assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    assert first["summary"]["wealth_strategy_card_count"] >= 2
    assert first["summary"]["moonshot_strategy_card_count"] >= 2
    assert first["summary"]["experiment_count"] == len(first["experiments"])
    assert first["weekly_review"]["phase"] == "14B"


def test_15a_writes_json_and_markdown_reports() -> None:
    out_dir = Path("reports/daily_research_tests") / uuid.uuid4().hex
    try:
        report_input = build_default_daily_research_input(now=FIXED_NOW)
        json_path, markdown_path = write_daily_research_summary(report_input, out_dir=out_dir)

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "daily_research_summary.json"
        assert markdown_path.name == "daily_research_summary.md"
        assert payload["report_date"] == "2026-07-07"
        assert "15A Daily Research Command Center" in markdown
        assert "HUMAN_REVIEW_REQUIRED" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No broker routing, broker calls, order submission, or secrets are used." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_15a_rejects_unsafe_labels_and_execution_flags() -> None:
    unsafe_label = "SELL" + "_NOW"
    base = build_default_daily_research_input(now=FIXED_NOW)

    with pytest.raises(ValueError, match="unsafe daily research label"):
        build_daily_research_payload(
            DailyResearchInput(
                report_date=base.report_date,
                generated_at_utc=base.generated_at_utc,
                experiments=(
                    {
                        "experiment_id": "EXP-UNSAFE",
                        "engine": "wealth",
                        "label": unsafe_label,
                        "summary": "Unsafe label fixture.",
                    },
                ),
            )
        )

    with pytest.raises(ValueError, match="live_trading_enabled"):
        build_daily_research_payload(
            DailyResearchInput(
                report_date=base.report_date,
                generated_at_utc=base.generated_at_utc,
                experiments=(
                    {
                        "experiment_id": "EXP-UNSAFE",
                        "engine": "wealth",
                        "label": RESEARCH_ONLY,
                        "summary": "Unsafe execution flag fixture.",
                        "live_trading_enabled": True,
                    },
                ),
            )
        )


def test_15a_includes_supplied_safety_scanner_status() -> None:
    candidate = Path("reports/daily_research_tests") / f"{uuid.uuid4().hex}_candidate.py"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        candidate.write_text("print('research fixture')\n", encoding="utf-8")
        result = scan_paths([candidate])

        payload = build_daily_research_payload(
            DailyResearchInput(
                report_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                safety_scan_result=result,
            )
        )

        assert payload["safety_scanner"]["passed"] is True
        assert payload["safety_scanner"]["label"] == HUMAN_REVIEW_REQUIRED
        assert payload["summary"]["safety_scanner_finding_count"] == 0
    finally:
        candidate.unlink(missing_ok=True)


def test_15a_markdown_lists_empty_optional_sections() -> None:
    payload = build_daily_research_payload(
        DailyResearchInput(
            report_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            strategy_cards=(),
            experiments=(),
            promotion_gates=(),
            champion_challenger_outcomes=(),
            weekly_review_payload=None,
        )
    )

    markdown = render_daily_research_markdown(payload)

    assert "- Wealth strategy cards: 0" in markdown
    assert markdown.count("- None recorded.") == 6


def test_15a_runner_writes_reports() -> None:
    out_dir = Path("reports/daily_research_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_daily_research_command_center.py",
                "--out-dir",
                str(out_dir),
                "--report-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 15A DAILY RESEARCH COMMAND CENTER: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "daily_research_summary.json").exists()
        assert (out_dir / "daily_research_summary.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
