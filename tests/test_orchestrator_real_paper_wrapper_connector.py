from __future__ import annotations

import subprocess
import sys

from automation.orchestrator_real_paper_wrapper_connector import (
    REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION,
    build_real_paper_wrapper_connector_runtime_notes,
    evaluate_orchestrator_real_paper_wrapper_connector,
)


def test_disabled_by_default_state_is_safe():
    calls: list[str] = []

    def fake_wrapper() -> int:
        calls.append("called")
        return 0

    state = evaluate_orchestrator_real_paper_wrapper_connector(
        real_paper_wrapper_callable=fake_wrapper,
    )

    assert calls == []
    assert state.integrated is True
    assert state.real_paper_wrapper_requested is False
    assert state.real_paper_wrapper_connected is False
    assert state.real_paper_wrapper_attempted is False
    assert state.paper_arm_enabled is False
    assert state.real_paper_order_submitted is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False
    assert state.decision == "DISABLED_BY_DEFAULT"


def test_confirmation_missing_blocks_without_calling_wrapper():
    calls: list[str] = []

    def fake_wrapper() -> int:
        calls.append("called")
        return 0

    state = evaluate_orchestrator_real_paper_wrapper_connector(
        enable_real_paper_wrapper=True,
        real_paper_wrapper_confirmation="WRONG",
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_drill_completed=True,
        real_paper_wrapper_callable=fake_wrapper,
    )

    assert calls == []
    assert state.real_paper_wrapper_requested is True
    assert state.real_paper_wrapper_confirmation_accepted is False
    assert state.real_paper_wrapper_connected is False
    assert state.real_paper_wrapper_attempted is False
    assert state.real_paper_order_submitted is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False
    assert state.decision == "BLOCKED_CONFIRMATION_NOT_ACCEPTED"


def test_all_gates_pass_but_connector_still_never_calls_wrapper():
    calls: list[str] = []

    def fake_wrapper() -> int:
        calls.append("called")
        return 0

    state = evaluate_orchestrator_real_paper_wrapper_connector(
        enable_real_paper_wrapper=True,
        real_paper_wrapper_confirmation=REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION,
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_drill_completed=True,
        real_paper_wrapper_callable=fake_wrapper,
    )

    assert calls == []
    assert state.real_paper_wrapper_requested is True
    assert state.real_paper_wrapper_confirmation_accepted is True
    assert state.approval_receipt_gate_allowed is True
    assert state.paper_arm_bridge_allows_drill is True
    assert state.paper_arm_drill_completed is True
    assert state.real_paper_wrapper_callable_wired is True
    assert state.real_paper_wrapper_connected is False
    assert state.real_paper_wrapper_attempted is False
    assert state.paper_arm_enabled is False
    assert state.real_paper_order_submitted is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False
    assert state.decision == "CONNECTOR_SHAPE_READY_REAL_WRAPPER_DISCONNECTED_IN_PHASE_10C_21"


def test_runtime_notes_include_required_safety_flags():
    state = evaluate_orchestrator_real_paper_wrapper_connector(
        enable_real_paper_wrapper=True,
        real_paper_wrapper_confirmation=REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION,
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_drill_completed=True,
        real_paper_wrapper_callable=lambda: 0,
    )

    notes = build_real_paper_wrapper_connector_runtime_notes(state)

    assert "real_paper_wrapper_connected=false" in notes
    assert "real_paper_wrapper_attempted=false" in notes
    assert "real_paper_order_submitted=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_check_script_outputs_live_trading_disabled_and_false_safety_flags():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_orchestrator_real_paper_wrapper_connector.py",
            "--enable-real-paper-wrapper",
            "--real-paper-wrapper-confirmation",
            REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION,
            "--approval-receipt-gate-allowed",
            "--paper-arm-bridge-allows-drill",
            "--paper-arm-drill-completed",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    output = completed.stdout

    assert "LIVE TRADING: DISABLED" in output
    assert "real_paper_wrapper_connected=false" in output
    assert "real_paper_wrapper_attempted=false" in output
    assert "real_paper_order_submitted=false" in output
    assert "broker_order_call_performed=false" in output
    assert "live_trading_enabled=false" in output
    assert "CONNECTOR_SHAPE_READY_REAL_WRAPPER_DISCONNECTED_IN_PHASE_10C_21" in output
