from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br18_fixture_scenario_expansion_matrix import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    PIPELINE_STAGES,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_SCENARIO_TYPES,
    build_fixture_scenario_expansion_matrix_report,
    fixture_scenario_expansion_matrix_payload,
    render_markdown_fixture_scenario_expansion_matrix,
    run_fixture_scenario_expansion_matrix,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br18_fixture_scenario_expansion_matrix.py")
SCRIPT_PATH = Path("scripts/run_br18_fixture_scenario_expansion_matrix.py")
DOC_PATH = Path("docs/brendan_strategy/br18_fixture_scenario_expansion_matrix.md")


def test_br18_safety_manifest_is_fixture_only_offline_and_disabled() -> None:
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
    assert manifest["fixture_only"] is True
    assert manifest["offline_only"] is True
    assert manifest["deterministic_matrix_only"] is True
    assert manifest["paper_portfolio_updates_simulated"] is True
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br18_builds_required_scenario_matrix_from_fixture() -> None:
    report = build_fixture_scenario_expansion_matrix_report()
    payload = fixture_scenario_expansion_matrix_payload(report)

    assert DEFAULT_FIXTURE_PATH.exists()
    assert payload["phase"] == "BR-18"
    assert payload["module"] == "Fixture Scenario Expansion Matrix"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["required_scenario_types"] == REQUIRED_SCENARIO_TYPES
    assert payload["pipeline_stages"] == PIPELINE_STAGES
    assert payload["metrics"]["scenario_count"] == 10
    assert payload["metrics"]["pipeline_stage_count"] == 8
    assert payload["metrics"]["matrix_cell_count"] == 80
    assert payload["metrics"]["paper_hold_scenario_count"] == 2
    assert payload["metrics"]["blocked_scenario_count"] == 6
    assert payload["metrics"]["human_review_scenario_count"] == 2
    assert payload["metrics"]["monitor_alert_scenario_count"] == 8
    assert payload["metrics"]["dashboard_summary_count"] == 10
    assert all(payload["acceptance_criteria"].values())
    assert tuple(item["scenario_type"] for item in payload["scenarios"]) == REQUIRED_SCENARIO_TYPES
    assert set(payload["scenarios"][0]["expected_behavior"]) == set(PIPELINE_STAGES)


def test_br18_scenario_outcomes_cover_expected_behaviors() -> None:
    report = build_fixture_scenario_expansion_matrix_report()
    payload = fixture_scenario_expansion_matrix_payload(report)
    by_type = {item["scenario_type"]: item for item in payload["scenario_outcomes"]}

    assert by_type["bullish"]["risk_gate_label"] == PAPER_ONLY
    assert by_type["bullish"]["paper_simulation_status"] == "simulated_hold"
    assert by_type["bearish"]["risk_gate_label"] == HUMAN_REVIEW_REQUIRED
    assert by_type["neutral"]["risk_gate_label"] == HUMAN_REVIEW_REQUIRED
    assert by_type["stale-data"]["risk_gate_label"] == BLOCKED_BY_SAFETY_GATE
    assert by_type["poor-liquidity"]["risk_gate_label"] == BLOCKED_BY_SAFETY_GATE
    assert by_type["no-candidate"]["risk_gate_status"] == "no_decision"
    assert by_type["thesis-missing"]["risk_gate_status"] == "rejected"
    assert by_type["chain-quality-failed"]["risk_gate_label"] == BLOCKED_BY_SAFETY_GATE
    assert by_type["risk-rejected"]["risk_gate_label"] == BLOCKED_BY_SAFETY_GATE
    assert by_type["paper-hold"]["risk_gate_label"] == PAPER_ONLY
    assert payload["stage_status_counts"]["candidate_selection"]["selected"] == 4
    assert payload["stage_status_counts"]["paper_only_portfolio_simulation"]["no_fill"] == 8


def test_br18_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br18_matrix_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    report = run_fixture_scenario_expansion_matrix(out_dir=out_dir)
    payload = fixture_scenario_expansion_matrix_payload(report)

    assert payload["acceptance_criteria"]["fixture_only_offline"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br18_markdown_script_and_doc_record_required_sections() -> None:
    report = build_fixture_scenario_expansion_matrix_report()
    markdown = render_markdown_fixture_scenario_expansion_matrix(report)
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-18 Fixture Scenario Expansion Matrix" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Scenario Matrix" in markdown
    assert "## Scenario Outcomes" in markdown
    assert "## Stage Status Counts" in markdown
    assert "bullish" in markdown
    assert "paper-hold" in markdown
    assert "candidate selection, chain quality, contract scoring, thesis packaging" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1


def test_br18_validation_rejects_unsafe_matrix_mutations() -> None:
    report = build_fixture_scenario_expansion_matrix_report()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(report, safety={**report.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(report, safety={**report.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(report, safety={**report.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(report, safety={**report.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(report, label=MONITOR_ONLY).validate()


def test_br18_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
    assert "from broker" not in source
    assert "import broker" not in source
