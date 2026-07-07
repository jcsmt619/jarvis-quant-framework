from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.orchestrator_heartbeat import read_heartbeat
from automation.orchestrator_paper_arm_bridge import (
    PAPER_ARM_BRIDGE_CONFIRMATION,
    build_paper_arm_bridge_runtime_notes,
    evaluate_orchestrator_paper_arm_bridge,
)
import scripts.check_orchestrator_paper_arm_bridge as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def write_approved_record(approvals_dir: Path) -> str:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=10,
        source="test",
        note="paper arm bridge test",
        now=fixed_now(),
    )
    command = parse_approval_command(f"APPROVE {record.approval_id}")
    approved, decision = apply_approval_command(
        record=record,
        command=command,
        now=fixed_now() + timedelta(seconds=30),
    )
    assert decision.accepted is True
    write_approval_record(approved, output_dir=approvals_dir)
    return record.approval_id


def test_paper_arm_bridge_disabled_by_default_does_not_call():
    calls = []

    def fake_paper_arm():
        calls.append("called")
        return 5

    state = evaluate_orchestrator_paper_arm_bridge(
        approval_receipt_gate_allowed=True,
        paper_arm_callable=fake_paper_arm,
    )

    assert calls == []
    assert state.integrated is True
    assert state.paper_arm_requested is False
    assert state.approval_receipt_gate_allowed is True
    assert state.paper_arm_callable_wired is True
    assert state.paper_arm_attempted is False
    assert state.paper_arm_enabled is False
    assert state.decision == "DISABLED_BY_DEFAULT"
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_paper_arm_bridge_requested_allowed_still_does_not_call_in_this_phase():
    calls = []

    def fake_paper_arm():
        calls.append("called")
        return 5

    state = evaluate_orchestrator_paper_arm_bridge(
        enable_paper_arm=True,
        paper_arm_confirmation=PAPER_ARM_BRIDGE_CONFIRMATION,
        approval_receipt_gate_allowed=True,
        paper_arm_callable=fake_paper_arm,
    )

    assert calls == []
    assert state.paper_arm_requested is True
    assert state.paper_arm_confirmation_accepted is True
    assert state.approval_receipt_gate_allowed is True
    assert state.paper_arm_attempted is False
    assert state.paper_arm_enabled is False
    assert state.decision == "BRIDGE_WIRED_BUT_EXECUTION_DISABLED_IN_PHASE_10C_17"
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_paper_arm_bridge_notes_include_safety_flags():
    state = evaluate_orchestrator_paper_arm_bridge()
    notes = build_paper_arm_bridge_runtime_notes(state)

    assert "paper_arm_bridge_integrated=true" in notes
    assert "paper_arm_requested=false" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_paper_arm_bridge_report_prints_default_state(capsys):
    code = check_script.run_orchestrator_paper_arm_bridge_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR PAPER ARM BRIDGE REPORT: PASS" in output
    assert "Paper arm bridge integrated: true" in output
    assert "Paper arm requested: false" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_paper_arm_bridge_default_state(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="paper_arm_bridge_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Paper arm bridge integrated: true" in output
    assert "Paper arm requested: false" in output
    assert "Paper arm callable wired: true" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_requested_paper_arm_bridge_still_does_not_arm(capsys, tmp_path):
    approvals_dir = tmp_path / "approvals"
    approval_id = write_approved_record(approvals_dir)

    def fake_runner(**kwargs):
        return 0

    heartbeat_path = tmp_path / "heartbeat.json"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=approvals_dir,
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=heartbeat_path,
        session_id="paper_arm_bridge_requested",
        max_cycles=1,
        approval_id=approval_id,
        enable_paper_arm=True,
        paper_arm_confirmation=PAPER_ARM_BRIDGE_CONFIRMATION,
        injected_cycle_runner=fake_runner,
        now=fixed_now() + timedelta(minutes=1),
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "Approval receipt gate allowed: true" in output
    assert "Paper arm requested: true" in output
    assert "Paper arm confirmation accepted: true" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Paper arm bridge decision: BRIDGE_WIRED_BUT_EXECUTION_DISABLED_IN_PHASE_10C_17" in output
    assert "Broker order call performed: false" in output
    assert "paper_arm_requested=true" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "LIVE TRADING: DISABLED" in output
