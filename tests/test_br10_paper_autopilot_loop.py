from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.paper_autopilot_loop import (
    PaperAutopilotLoopConfig,
    paper_autopilot_loop_payload,
    render_markdown_paper_autopilot_loop,
    run_paper_autopilot_loop,
    safety_manifest,
    write_paper_autopilot_loop_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def test_br10_safety_manifest_is_local_paper_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-10"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["local_workflow_only"] is True
    assert manifest["candidate_scanning_enabled"] is True
    assert manifest["scoring_enabled"] is True
    assert manifest["paper_portfolio_updates_enabled"] is True
    assert manifest["monitor_alerts_enabled"] is True
    assert manifest["analyst_context_packaging_enabled"] is True
    assert manifest["dashboard_refresh_enabled"] is True
    assert manifest["simulated_fills_only"] is True
    assert manifest["local_marks_only"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br10_runs_scan_score_paper_update_monitor_analyst_context_and_dashboard() -> None:
    report = run_paper_autopilot_loop()
    payload = paper_autopilot_loop_payload(report)

    assert payload["phase"] == "BR-10"
    assert payload["label"] == PAPER_ONLY
    assert payload["metrics"] == {
        "candidate_count": 5,
        "included_candidate_count": 3,
        "chain_count": 2,
        "contract_score_count": 6,
        "risk_gate_decision_count": 6,
        "generated_fill_count": 2,
        "generated_mark_count": 2,
        "paper_position_count": 2,
        "monitor_alert_count": 0,
        "dashboard_candidate_count": 5,
        "analyst_prompt_package_count": 1,
        "analyst_thesis_record_count": 1,
    }
    assert [fill["contract_id"] for fill in payload["paper_updates"]["fills"]] == [
        "NVDA-20271217-C-140",
        "NVDA-20271217-C-180",
    ]
    assert {fill["label"] for fill in payload["paper_updates"]["fills"]} == {PAPER_ONLY}
    assert all(fill["simulated_fill"] is True for fill in payload["paper_updates"]["fills"])
    assert all(mark["local_mark"] is True for mark in payload["paper_updates"]["marks"])
    assert report.paper_options_portfolio_report.positions
    assert report.daily_position_monitor_report.alerts == ()
    assert report.local_operator_dashboard_report.paper_options_portfolio_report is report.paper_options_portfolio_report
    assert payload["safety"]["live_trading_enabled"] is False
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br10_respects_max_new_paper_positions() -> None:
    report = run_paper_autopilot_loop(PaperAutopilotLoopConfig(max_new_paper_positions=1))
    payload = paper_autopilot_loop_payload(report)

    assert payload["metrics"]["generated_fill_count"] == 1
    assert payload["metrics"]["paper_position_count"] == 1
    assert payload["paper_updates"]["fills"][0]["contract_id"] == "NVDA-20271217-C-140"


def test_br10_markdown_and_report_files_are_local_paper_outputs() -> None:
    report = run_paper_autopilot_loop()
    markdown = render_markdown_paper_autopilot_loop(report)

    assert "BR-10 Paper Autopilot Loop" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Generated fills are simulated paper fills only." in markdown
    assert "No broker routing, broker calls, live trading, or order submission." in markdown

    out_dir = Path(".codex_pytest_tmp/br10_paper_autopilot_loop_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_paper_autopilot_loop_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-10"
    assert "Workflow Metrics" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br10_validation_rejects_bad_config_and_enabled_safety_state() -> None:
    with pytest.raises(ValueError, match="max_new_paper_positions must be positive"):
        PaperAutopilotLoopConfig(max_new_paper_positions=0).validate()

    with pytest.raises(ValueError, match="starting_cash must be positive"):
        PaperAutopilotLoopConfig(starting_cash=0).validate()

    report = run_paper_autopilot_loop()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()
