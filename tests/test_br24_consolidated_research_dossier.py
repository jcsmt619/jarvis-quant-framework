from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br24_consolidated_research_dossier import (
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    DOSSIER_SECTIONS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    build_consolidated_research_dossier,
    consolidated_research_dossier_payload,
    render_markdown_consolidated_research_dossier,
    run_consolidated_research_dossier,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br24_consolidated_research_dossier.py")
SCRIPT_PATH = Path("scripts/run_br24_consolidated_research_dossier.py")
DOC_PATH = Path("docs/brendan_strategy/br24_consolidated_research_dossier.md")


def test_br24_safety_manifest_is_read_only_offline_and_disabled() -> None:
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
    assert manifest["read_only"] is True
    assert manifest["offline_only"] is True
    assert manifest["committed_report_inputs_only"] is True
    assert manifest["deterministic_dossier_records_only"] is True
    assert manifest["live_trading_authorized"] is False
    assert manifest["broker_actions_authorized"] is False
    assert manifest["order_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["paper_state_mutation_allowed"] is False
    assert manifest["trading_state_mutation_allowed"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br24_builds_dossier_from_committed_br14_through_br23_evidence() -> None:
    dossier = build_consolidated_research_dossier()
    payload = consolidated_research_dossier_payload(dossier)

    assert all(path.exists() for path in DEFAULT_SOURCE_PATHS.values())
    assert payload["phase"] == "BR-24"
    assert payload["module"] == "Consolidated Research Dossier"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["source_paths"]) == set(DEFAULT_SOURCE_PATHS)
    assert payload["dossier_sections"] == DOSSIER_SECTIONS
    assert payload["metrics"]["source_phase_count"] == 10
    assert payload["metrics"]["dossier_section_count"] == len(DOSSIER_SECTIONS)
    assert payload["metrics"]["unresolved_blocker_count"] >= 20
    assert payload["metrics"]["required_human_review_action_count"] >= 20
    assert payload["metrics"]["acceptance_criteria_passed_count"] == payload["metrics"]["acceptance_criteria_count"]
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["operator_packet_ready"] is True
    assert payload["readiness_state"]["manual_review_required"] is True
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert payload["readiness_state"]["order_paths_allowed"] is False
    assert payload["readiness_state"]["data_provider_calls_allowed"] is False
    assert payload["readiness_state"]["paper_state_mutation_allowed"] is False
    assert payload["readiness_state"]["trading_state_mutation_allowed"] is False


def test_br24_sections_cover_operator_packet_requirements() -> None:
    payload = consolidated_research_dossier_payload(build_consolidated_research_dossier())
    sections = payload["sections"]

    assert set(sections) == set(DOSSIER_SECTIONS)
    assert sections["source_evidence"]["label"] == RESEARCH_ONLY
    assert set(sections["source_evidence"]["phases"]) == set(DEFAULT_SOURCE_PATHS)
    assert sections["candidate_universe"]["candidate_count"] == 5
    assert sections["candidate_universe"]["label"] == RESEARCH_ONLY
    assert sections["option_chain_quality"]["chain_count"] == 2
    assert sections["option_chain_quality"]["label"] == MONITOR_ONLY
    assert sections["contract_scoring"]["contract_count"] == 6
    assert sections["thesis_package_context"]["label"] == HUMAN_REVIEW_REQUIRED
    assert sections["risk_gate_outcomes"]["risk_gate_decision_count"] == 6
    assert sections["risk_gate_outcomes"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert sections["paper_only_portfolio_records"]["simulated_paper_fill_count"] == 2
    assert sections["paper_only_portfolio_records"]["label"] == PAPER_ONLY
    assert sections["monitor_observations"]["label"] == MONITOR_ONLY
    assert sections["manual_review_packet"]["label"] == HUMAN_REVIEW_REQUIRED
    assert sections["scenario_matrix"]["source_phase"] == "BR-18"
    assert sections["replay_evidence"]["source_phase"] == "BR-19"
    assert sections["paper_decision_journal"]["source_phase"] == "BR-20"
    assert sections["human_review_resolution_ledger"]["source_phase"] == "BR-21"
    assert sections["paper_outcome_tracker"]["source_phase"] == "BR-22"
    assert sections["promotion_gate_checklist"]["source_phase"] == "BR-23"
    assert sections["immutable_safety_boundaries"]["br24_safety"]["LIVE TRADING"] == "DISABLED"


def test_br24_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br24_consolidated_research_dossier_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    dossier = run_consolidated_research_dossier(out_dir=out_dir)
    payload = consolidated_research_dossier_payload(dossier)

    assert payload["acceptance_criteria"]["source_paths_cover_br14_through_br23"] is True
    assert payload["acceptance_criteria"]["immutable_safety_boundaries_recorded"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br24_markdown_script_and_doc_record_required_sections() -> None:
    markdown = render_markdown_consolidated_research_dossier(build_consolidated_research_dossier())
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-24 Consolidated Research Dossier" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Source Evidence" in markdown
    assert "## Dossier Sections" in markdown
    assert "## Unresolved Blockers" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "## Immutable Safety Boundaries" in markdown
    for section_name in DOSSIER_SECTIONS:
        assert section_name in markdown
        assert section_name in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "paper_state_mutation_allowed=false" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br24_validation_rejects_unsafe_dossier_mutations() -> None:
    dossier = build_consolidated_research_dossier()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(dossier, safety={**dossier.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(dossier, safety={**dossier.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(dossier, safety={**dossier.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(dossier, safety={**dossier.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(dossier, safety={**dossier.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot allow live_trading_authorized"):
        replace(dossier, safety={**dossier.safety, "live_trading_authorized": True}).validate()

    with pytest.raises(ValueError, match="cannot allow broker_actions_authorized"):
        replace(dossier, safety={**dossier.safety, "broker_actions_authorized": True}).validate()

    with pytest.raises(ValueError, match="cannot allow order_paths_authorized"):
        replace(dossier, safety={**dossier.safety, "order_paths_authorized": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(dossier, safety={**dossier.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(dossier, label=MONITOR_ONLY).validate()


def test_br24_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
