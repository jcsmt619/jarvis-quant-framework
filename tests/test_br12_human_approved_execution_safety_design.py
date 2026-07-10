from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from broker import get_broker
from broker.human_approved_execution_safety_design import (
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_APPROVAL_GATES,
    REQUIRED_AUDIT_FIELDS,
    REQUIRED_KILL_SWITCHES,
    REQUIRED_MANUAL_CONFIRMATIONS,
    ApprovalGateDesign,
    AuditTrailDesign,
    BrokerAdapterBoundaryDesign,
    KillSwitchDesign,
    PositionLimitDesign,
    default_approval_gates,
    default_kill_switches,
    default_manual_confirmations,
    default_position_limits,
    evaluate_human_approved_execution_safety_design,
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


MODULE_PATH = Path("broker/human_approved_execution_safety_design.py")
DOC_PATH = Path("docs/brendan_strategy/br12_human_approved_execution_safety_design.md")


def test_br12_safety_manifest_is_design_only_and_disabled() -> None:
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
    assert manifest["approval_design_only"] is True
    assert manifest["approval_gates"] == REQUIRED_APPROVAL_GATES
    assert manifest["kill_switches"] == REQUIRED_KILL_SWITCHES
    assert manifest["manual_confirmations"] == REQUIRED_MANUAL_CONFIRMATIONS
    assert manifest["audit_fields"] == REQUIRED_AUDIT_FIELDS
    assert manifest["manual_confirmations_recorded"] is False
    assert manifest["credential_loading_required"] is False
    assert manifest["broker_connection_attempted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br12_disabled_by_default_defines_boundaries_without_broker_work() -> None:
    state = evaluate_human_approved_execution_safety_design()

    assert state.requested is False
    assert state.approval_gates_defined is True
    assert state.broker_adapter_boundaries_defined is True
    assert state.kill_switches_defined is True
    assert state.position_limits_defined is True
    assert state.audit_trails_defined is True
    assert state.manual_confirmations_defined is True
    assert state.manual_confirmations_recorded is False
    assert state.broker_order_routing_enabled is False
    assert state.broker_order_call_performed is False
    assert state.broker_order_submitted is False
    assert state.live_trading_enabled is False
    assert state.decision == "DESIGN_ONLY_DISABLED_BY_DEFAULT"


def test_br12_requested_future_path_remains_disabled() -> None:
    state = evaluate_human_approved_execution_safety_design(request_future_approval_path=True)

    assert state.requested is True
    assert state.manual_confirmations_recorded is False
    assert state.broker_order_routing_enabled is False
    assert state.broker_order_call_performed is False
    assert state.broker_order_submitted is False
    assert state.live_trading_enabled is False
    assert state.decision == "DESIGN_READY_APPROVAL_PATH_DISABLED"
    assert state.blocked_reasons == ("future approval path remains disabled in BR-12",)


def test_br12_rejects_live_manual_confirmation_recording() -> None:
    with pytest.raises(ValueError, match="cannot record live manual confirmations"):
        evaluate_human_approved_execution_safety_design(manual_confirmations_recorded=True)


def test_br12_runtime_notes_include_required_disabled_flags() -> None:
    notes = runtime_notes(evaluate_human_approved_execution_safety_design(request_future_approval_path=True))

    assert "approval_gates_defined=true" in notes
    assert "broker_adapter_boundaries_defined=true" in notes
    assert "kill_switches_defined=true" in notes
    assert "position_limits_defined=true" in notes
    assert "audit_trails_defined=true" in notes
    assert "manual_confirmations_defined=true" in notes
    assert "manual_confirmations_recorded=false" in notes
    assert "broker_order_routing_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "broker_order_submitted=false" in notes
    assert "live_trading_enabled=false" in notes
    assert "LIVE TRADING: DISABLED" in notes


def test_br12_default_components_validate_required_gate_boundary_kill_limit_audit_and_confirmation_design() -> None:
    for gate in default_approval_gates():
        gate.validate()
        assert gate.required is True
        assert gate.human_review_required is True
        assert gate.blocks_on_failure is True
        assert gate.label == HUMAN_REVIEW_REQUIRED

    BrokerAdapterBoundaryDesign(adapter_name="future_boundary").validate()

    for kill_switch in default_kill_switches():
        kill_switch.validate()
        assert kill_switch.default_state == "ENGAGED_UNTIL_CLEARED"
        assert kill_switch.label == BLOCKED_BY_SAFETY_GATE

    for position_limit in default_position_limits():
        position_limit.validate()
        assert position_limit.maximum > 0
        assert position_limit.blocks_on_breach is True

    for confirmation in default_manual_confirmations():
        confirmation.validate()
        assert confirmation.operator_entered is False

    AuditTrailDesign().validate()


def test_br12_validation_rejects_unsafe_design_mutations() -> None:
    with pytest.raises(ValueError, match="approval gates must be required"):
        replace(default_approval_gates()[0], required=False).validate()

    with pytest.raises(ValueError, match="cannot enable order routing"):
        BrokerAdapterBoundaryDesign(adapter_name="future_boundary", broker_order_routing_enabled=True).validate()

    with pytest.raises(ValueError, match="cannot perform broker order calls"):
        BrokerAdapterBoundaryDesign(adapter_name="future_boundary", broker_order_call_performed=True).validate()

    with pytest.raises(ValueError, match="cannot enable live trading"):
        BrokerAdapterBoundaryDesign(adapter_name="future_boundary", **{"live_trading_" + "enabled": True}).validate()

    with pytest.raises(ValueError, match="default to engaged"):
        replace(default_kill_switches()[0], default_state="CLEARED").validate()

    with pytest.raises(ValueError, match="must be positive"):
        PositionLimitDesign(name="bad_limit", maximum=0.0, unit="pct").validate()

    with pytest.raises(ValueError, match="cannot allow secret values"):
        AuditTrailDesign(secret_values_allowed=True).validate()

    with pytest.raises(ValueError, match="cannot record live operator confirmations"):
        replace(default_manual_confirmations()[0], operator_entered=True).validate()


def test_br12_is_not_registered_as_a_broker_adapter() -> None:
    with pytest.raises(KeyError):
        get_broker("human_approved_execution_safety_design")


def test_br12_design_doc_records_scope_and_safety_flags() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-12 Human Approved Execution Safety Design" in text
    assert "LIVE TRADING: DISABLED" in text
    assert "approval gates" in text
    assert "broker adapter boundaries" in text
    assert "kill switches" in text
    assert "position limits" in text
    assert "audit trails" in text
    assert "manual confirmations" in text
    assert "credential_loading_required=false" in text
    assert "broker_connection_attempted=false" in text
    assert "broker_order_routing_enabled=false" in text
    assert "broker_order_call_performed=false" in text
    assert "broker_order_submitted=false" in text
    assert "live_trading_enabled=false" in text
    assert "does not load credentials" in text
    assert "does not connect to Alpaca, IBKR, TradeStation, or any broker" in text
    assert "does not submit broker orders" in text


def test_br12_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
