from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.orchestrator_approval_receipt_state import (
    build_approval_receipt_runtime_notes,
    evaluate_orchestrator_approval_receipt_state,
)
from automation.orchestrator_heartbeat import read_heartbeat
import scripts.check_orchestrator_approval_receipt_state as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def write_approved_record(approvals_dir: Path) -> str:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=10,
        source="test",
        note="approval receipt gate test",
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


def test_approval_receipt_state_blocks_without_id(tmp_path):
    state = evaluate_orchestrator_approval_receipt_state(
        approval_id=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )

    assert state.integrated is True
    assert state.approval_id_provided is False
    assert state.gate_allowed is False
    assert state.approval_status == "MISSING_ID"
    assert state.paper_arm_attempted is False
    assert state.paper_arm_enabled is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_approval_receipt_state_allows_approved_record(tmp_path):
    approval_id = write_approved_record(tmp_path)

    state = evaluate_orchestrator_approval_receipt_state(
        approval_id=approval_id,
        approvals_dir=tmp_path,
        now=fixed_now() + timedelta(minutes=1),
    )

    assert state.integrated is True
    assert state.approval_id_provided is True
    assert state.approval_id == approval_id
    assert state.gate_allowed is True
    assert state.approval_status == "APPROVED"
    assert state.paper_arm_attempted is False
    assert state.paper_arm_enabled is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_approval_receipt_runtime_notes_include_safety_flags(tmp_path):
    state = evaluate_orchestrator_approval_receipt_state(
        approval_id=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    notes = build_approval_receipt_runtime_notes(state)

    assert "approval_receipt_gate_integrated=true" in notes
    assert "approval_id_provided=false" in notes
    assert "approval_receipt_gate_allowed=false" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_approval_receipt_report_prints_disabled_state(capsys, tmp_path):
    code = check_script.run_orchestrator_approval_receipt_state_report(
        approval_id=None,
        approvals_dir=tmp_path,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR APPROVAL RECEIPT GATE REPORT: PASS" in output
    assert "Approval receipt gate integrated: true" in output
    assert "Approval id provided: false" in output
    assert "Approval receipt gate allowed: false" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_approval_receipt_state_without_arm(capsys, tmp_path):
    runner_calls = []

    def fake_runner(**kwargs):
        runner_calls.append(kwargs)
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="approval_receipt_no_id",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert runner_calls
    assert "Approval receipt gate integrated: true" in output
    assert "Approval id provided: false" in output
    assert "Approval receipt gate allowed: false" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_approval_receipt_allowed_still_does_not_arm(capsys, tmp_path):
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
        session_id="approval_receipt_allowed",
        max_cycles=1,
        approval_id=approval_id,
        injected_cycle_runner=fake_runner,
        now=fixed_now() + timedelta(minutes=1),
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "Approval id provided: true" in output
    assert "Approval receipt gate allowed: true" in output
    assert "Approval receipt status: APPROVED" in output
    assert "Paper arm attempted: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "approval_receipt_gate_allowed=true" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "LIVE TRADING: DISABLED" in output
