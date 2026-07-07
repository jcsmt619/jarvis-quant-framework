from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.orchestrator_heartbeat import read_heartbeat
from automation.orchestrator_paper_arm_bridge import PAPER_ARM_BRIDGE_CONFIRMATION
from automation.orchestrator_paper_arm_drill import (
    PAPER_ARM_DRILL_CONFIRMATION,
    build_paper_arm_drill_runtime_notes,
    run_orchestrator_paper_arm_drill,
)
import scripts.check_orchestrator_paper_arm_drill as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def write_approved_record(approvals_dir: Path) -> str:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=10,
        source="test",
        note="paper arm drill test",
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


def test_paper_arm_drill_disabled_by_default_does_not_call():
    calls = []

    def fake_paper_arm():
        calls.append("called")
        return 0

    state = run_orchestrator_paper_arm_drill(
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_callable=fake_paper_arm,
    )

    assert calls == []
    assert state.paper_arm_drill_requested is False
    assert state.paper_arm_drill_attempted is False
    assert state.paper_arm_enabled is False
    assert state.real_paper_order_submitted is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_paper_arm_drill_calls_injected_callable_only_when_all_gates_pass():
    calls = []

    def fake_paper_arm():
        calls.append("called")
        return 0

    state = run_orchestrator_paper_arm_drill(
        enable_paper_arm_drill=True,
        paper_arm_drill_confirmation=PAPER_ARM_DRILL_CONFIRMATION,
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_callable=fake_paper_arm,
    )

    assert calls == ["called"]
    assert state.paper_arm_drill_attempted is True
    assert state.paper_arm_drill_return_code == 0
    assert state.decision == "DRILL_COMPLETED_WITH_INJECTED_CALLABLE_ONLY"
    assert state.paper_arm_enabled is False
    assert state.real_paper_order_submitted is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_paper_arm_drill_notes_include_safety_flags():
    state = run_orchestrator_paper_arm_drill()
    notes = build_paper_arm_drill_runtime_notes(state)

    assert "paper_arm_drill_integrated=true" in notes
    assert "paper_arm_drill_requested=false" in notes
    assert "paper_arm_drill_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "real_paper_order_submitted=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_paper_arm_drill_report_prints_disabled_state(capsys):
    code = check_script.run_orchestrator_paper_arm_drill_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR PAPER ARM DRILL REPORT: PASS" in output
    assert "Paper arm drill integrated: true" in output
    assert "Paper arm drill requested: false" in output
    assert "Paper arm drill attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Real paper order submitted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_paper_arm_drill_default_state(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="paper_arm_drill_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Paper arm drill integrated: true" in output
    assert "Paper arm drill requested: false" in output
    assert "Paper arm drill attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Real paper order submitted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_approval_gated_paper_arm_drill_uses_injected_callable_only(capsys, tmp_path):
    approvals_dir = tmp_path / "approvals"
    approval_id = write_approved_record(approvals_dir)
    drill_calls = []

    def fake_runner(**kwargs):
        return 0

    def fake_paper_arm_drill():
        drill_calls.append("called")
        return 0

    heartbeat_path = tmp_path / "heartbeat.json"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=approvals_dir,
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=heartbeat_path,
        session_id="paper_arm_drill_injected",
        max_cycles=1,
        approval_id=approval_id,
        enable_paper_arm=True,
        paper_arm_confirmation=PAPER_ARM_BRIDGE_CONFIRMATION,
        enable_paper_arm_drill=True,
        paper_arm_drill_confirmation=PAPER_ARM_DRILL_CONFIRMATION,
        injected_cycle_runner=fake_runner,
        injected_paper_arm_drill=fake_paper_arm_drill,
        now=fixed_now() + timedelta(minutes=1),
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert drill_calls == ["called"]
    assert "Approval receipt gate allowed: true" in output
    assert "Paper arm requested: true" in output
    assert "Paper arm drill requested: true" in output
    assert "Paper arm drill confirmation accepted: true" in output
    assert "Paper arm bridge allows drill: true" in output
    assert "Paper arm drill attempted: true" in output
    assert "Paper arm drill decision: DRILL_COMPLETED_WITH_INJECTED_CALLABLE_ONLY" in output
    assert "Paper arm drill return code: 0" in output
    assert "Paper arm enabled: false" in output
    assert "Real paper order submitted: false" in output
    assert "Broker order call performed: false" in output
    assert "paper_arm_drill_attempted=true" in notes
    assert "real_paper_order_submitted=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "LIVE TRADING: DISABLED" in output
