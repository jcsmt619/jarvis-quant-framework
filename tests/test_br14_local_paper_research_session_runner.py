from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br14_local_paper_research_session_runner import (
    DEFAULT_REPORT_DIR,
    FORBIDDEN_RUNTIME_FLAGS,
    MODULE_NAME,
    PHASE_ID,
    local_paper_research_session_payload,
    render_markdown_local_paper_research_session,
    run_local_paper_research_session,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br14_local_paper_research_session_runner.py")
SCRIPT_PATH = Path("scripts/run_br14_local_paper_research_session.py")
DOC_PATH = Path("docs/brendan_strategy/br14_local_paper_research_session_runner.md")


def test_br14_safety_manifest_is_local_paper_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["module"] == MODULE_NAME
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["local_fixture_data_default"] is True
    assert manifest["end_to_end_dry_run_only"] is True
    assert manifest["static_artifacts_only"] is True
    assert manifest["paper_portfolio_updates_simulated"] is True
    for field_name in FORBIDDEN_RUNTIME_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br14_runs_full_fixture_session_and_keeps_all_runtime_boundaries_disabled() -> None:
    out_dir = Path(".codex_pytest_tmp/br14_session_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    report = run_local_paper_research_session(out_dir=out_dir)
    payload = local_paper_research_session_payload(report)

    assert payload["phase"] == "BR-14"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["session_flow"] == (
        "BR-10C",
        "BR-02",
        "BR-03",
        "BR-04",
        "BR-05",
        "BR-06",
        "BR-07",
        "BR-08",
        "BR-09",
    )
    assert payload["metrics"]["screener_queue_count"] == 3
    assert payload["metrics"]["candidate_count"] == 5
    assert payload["metrics"]["chain_count"] == 2
    assert payload["metrics"]["contract_count"] == 6
    assert payload["metrics"]["analyst_prompt_package_count"] == 1
    assert payload["metrics"]["risk_gate_decision_count"] == 6
    assert payload["metrics"]["simulated_paper_fill_count"] == 2
    assert payload["metrics"]["paper_position_count"] == 2
    assert payload["metrics"]["monitor_alert_count"] == 0
    assert payload["paper_contract_ids"] == ("NVDA-20271217-C-140", "NVDA-20271217-C-180")
    assert report.artifacts.paper_options_portfolio_report.label == PAPER_ONLY
    assert report.artifacts.daily_position_monitor_report.label == MONITOR_ONLY
    assert report.artifacts.local_operator_dashboard_report.label == MONITOR_ONLY
    for field_name in FORBIDDEN_RUNTIME_FLAGS:
        assert payload["safety"][field_name] is False
    assert payload["safety"]["LIVE TRADING"] == "DISABLED"
    assert Path(payload["written_artifacts"]["session"][0]).exists()
    assert Path(payload["written_artifacts"]["operator_dashboard"][1]).exists()

    shutil.rmtree(out_dir)


def test_br14_markdown_and_script_are_local_static_outputs() -> None:
    out_dir = Path(".codex_pytest_tmp/br14_markdown_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    report = run_local_paper_research_session(out_dir=out_dir)
    markdown = render_markdown_local_paper_research_session(report)
    session_json = Path(local_paper_research_session_payload(report)["written_artifacts"]["session"][0])

    assert "BR-14 Local Paper Research Session Runner" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "No credentials are loaded" in markdown
    assert "No broker connection, broker routing, broker calls, live trading, or order submission." in markdown
    assert json.loads(session_json.read_text(encoding="utf-8"))["phase"] == "BR-14"
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1

    shutil.rmtree(out_dir)


def test_br14_validation_rejects_unsafe_runtime_mutations() -> None:
    out_dir = Path(".codex_pytest_tmp/br14_validation_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    report = run_local_paper_research_session(out_dir=out_dir)

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(report, safety={**report.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(report, label=MONITOR_ONLY).validate()

    shutil.rmtree(out_dir)


def test_br14_doc_records_scope_artifacts_and_safety_flags() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-14 Local Paper Research Session Runner" in text
    assert "LIVE TRADING: DISABLED" in text
    assert "BR-10C Track B Config Driven Screener Pipeline" in text
    assert "BR-04 Greeks IV Spread DTE Scoring" in text
    assert "BR-05 LLM Analyst Thesis Generator" in text
    assert "BR-09 Local Operator Dashboard" in text
    assert "credential_loading_attempted=false" in text
    assert "broker_connection_attempted=false" in text
    assert "broker_read_call_performed=false" in text
    assert "broker_order_call_performed=false" in text
    assert "broker_order_submitted=false" in text
    assert "broker_order_routing_enabled=false" in text
    assert "live_trading_enabled=false" in text
    assert "does not load credentials" in text
    assert "does not connect to Alpaca, IBKR, TradeStation, or any broker" in text
    assert "does not submit broker orders" in text


def test_br14_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
