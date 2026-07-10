from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br13_full_system_integration_audit import (
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    IntegrationComponent,
    IntegrationHandoff,
    build_integration_audit_report,
    default_components,
    default_handoffs,
    integration_audit_payload,
    runtime_notes,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br13_full_system_integration_audit.py")
DOC_PATH = Path("docs/brendan_strategy/br13_brendan_full_system_integration_audit.md")


def test_br13_safety_manifest_is_audit_only_and_disabled() -> None:
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
    assert manifest["integration_audit_only"] is True
    assert manifest["conceptual_connectivity_verified"] is True
    assert manifest["deterministic_interfaces_verified"] is True
    assert manifest["read_only_broker_sync_design_only"] is True
    assert manifest["human_approved_safety_design_only"] is True
    assert manifest["credential_loading_required"] is False
    assert manifest["broker_connection_attempted"] is False
    assert manifest["broker_read_call_performed"] is False
    assert manifest["account_state_imported"] is False
    assert manifest["manual_confirmations_recorded"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br13_default_components_cover_full_research_pipeline_and_design_boundaries() -> None:
    components = default_components()
    phases = tuple(component.phase for component in components)

    assert phases == (
        "BR-10C",
        "BR-02",
        "BR-03",
        "BR-04",
        "BR-05",
        "BR-06",
        "BR-07",
        "BR-08",
        "BR-09",
        "BR-10",
        "BR-11",
        "BR-12",
    )
    assert {component.pathway for component in components} == {
        "deterministic",
        "non_deterministic_analyst",
        "safety_design",
    }
    for component in components:
        component.validate()
        assert component.manifest["live_trading_enabled"] is False
        assert component.manifest["broker_order_call_performed"] is False
        assert component.manifest["LIVE TRADING"] == "DISABLED"


def test_br13_handoffs_verify_conceptual_and_deterministic_connectivity() -> None:
    report = build_integration_audit_report()
    handoffs = default_handoffs()

    assert tuple(handoff.name for handoff in handoffs) == (
        "track_b_screener_to_candidate_universe",
        "candidate_universe_to_chain_quality",
        "chain_quality_to_contract_scoring",
        "contract_scoring_to_llm_thesis",
        "llm_thesis_to_risk_gate",
        "risk_gate_to_paper_portfolio",
        "paper_portfolio_to_monitor",
        "monitor_to_dashboard",
        "dashboard_to_read_only_broker_sync_design",
        "risk_gate_and_dashboard_to_human_approved_safety_design",
        "paper_autopilot_loop_to_full_audit",
    )
    assert all(handoff.human_review_required for handoff in handoffs)
    assert {handoff.expected_label for handoff in handoffs} <= {
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    }
    assert report.decision == "INTEGRATION_AUDIT_COMPLETE_RESEARCH_ONLY"
    assert report.live_trading_status == "LIVE TRADING: DISABLED"


def test_br13_payload_and_runtime_notes_record_disabled_integration_state() -> None:
    report = build_integration_audit_report()
    payload = integration_audit_payload(report)
    notes = runtime_notes(report)

    assert payload["phase"] == "BR-13"
    assert payload["metrics"] == {
        "component_count": 13,
        "handoff_count": 11,
        "human_review_required_handoff_count": 11,
        "disabled_component_count": 13,
    }
    assert payload["safety"]["broker_order_call_performed"] is False
    assert payload["safety"]["live_trading_enabled"] is False
    assert "conceptual_connectivity_verified=true" in notes
    assert "deterministic_interfaces_verified=true" in notes
    assert "broker_order_call_performed=false" in notes
    assert "broker_order_submitted=false" in notes
    assert "broker_order_routing_enabled=false" in notes
    assert "live_trading_enabled=false" in notes
    assert "LIVE TRADING: DISABLED" in notes


def test_br13_validation_rejects_unsafe_component_handoff_and_report_mutations() -> None:
    report = build_integration_audit_report()

    with pytest.raises(ValueError, match="cannot enable live trading"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="cannot perform broker order calls"):
        replace(
            report.components[0],
            manifest={**report.components[0].manifest, "broker_order_call_performed": True},
        ).validate()

    with pytest.raises(ValueError, match="must require human review"):
        IntegrationHandoff(
            name="bad_handoff",
            source_phase="BR-10C",
            target_phase="BR-02",
            deterministic_interface="bad_interface",
            expected_label=MONITOR_ONLY,
            human_review_required=False,
            broker_boundary="none",
        ).validate(tuple(component.phase for component in report.components))

    with pytest.raises(ValueError, match="pathway is not recognized"):
        IntegrationComponent(
            phase="BR-X",
            module="Bad Component",
            pathway="execution",
            interface_kind="bad_interface",
            manifest=safety_manifest(),
        ).validate()


def test_br13_doc_records_scope_handoffs_and_safety_flags() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-13 Brendan Full System Integration Audit" in text
    assert "LIVE TRADING: DISABLED" in text
    assert "BR-10C Track B Config Driven Screener Pipeline" in text
    assert "BR-04 Greeks IV Spread DTE Scoring" in text
    assert "BR-05 LLM Analyst Thesis Generator" in text
    assert "BR-11 Read Only Broker Account Sync Design" in text
    assert "BR-12 Human Approved Execution Safety Design" in text
    assert "track_b_screener_to_candidate_universe" in text
    assert "risk_gate_to_paper_portfolio" in text
    assert "dashboard_to_read_only_broker_sync_design" in text
    assert "credential_loading_required=false" in text
    assert "broker_connection_attempted=false" in text
    assert "broker_read_call_performed=false" in text
    assert "broker_order_call_performed=false" in text
    assert "broker_order_submitted=false" in text
    assert "broker_order_routing_enabled=false" in text
    assert "live_trading_enabled=false" in text
    assert "does not load credentials" in text
    assert "does not connect to Alpaca, IBKR, TradeStation, or any broker" in text
    assert "does not submit broker orders" in text


def test_br13_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
