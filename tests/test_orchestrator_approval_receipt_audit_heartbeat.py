from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.orchestrator_audit import read_audit_events
from automation.orchestrator_heartbeat import read_heartbeat
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def write_approved_record(approvals_dir: Path) -> str:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=10,
        source="test",
        note="approval receipt audit heartbeat test",
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


def test_orchestrator_writes_approval_receipt_audit_event_without_arm(capsys, tmp_path):
    approvals_dir = tmp_path / "approvals"
    approval_id = write_approved_record(approvals_dir)

    runner_calls = []

    def fake_runner(**kwargs):
        runner_calls.append(kwargs)
        return 0

    audit_dir = tmp_path / "audit"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=approvals_dir,
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=audit_dir,
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="approval_receipt_audit_allowed",
        max_cycles=1,
        approval_id=approval_id,
        injected_cycle_runner=fake_runner,
        now=fixed_now() + timedelta(minutes=1),
    )
    output = capsys.readouterr().out
    ledger_text = (audit_dir / "orchestrator_audit_ledger.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert runner_calls
    assert "Approval receipt audit integration enabled: true" in output
    assert "Approval receipt heartbeat integration enabled: true" in output
    assert "Approval receipt audit event written: true" in output
    assert "orchestrator_approval_receipt_state" in ledger_text
    assert "approval_id_provided=true" in ledger_text
    assert "approval_receipt_gate_allowed=true" in ledger_text
    assert "approval_receipt_status=APPROVED" in ledger_text
    assert "paper_arm_attempted=false" in ledger_text
    assert "paper_arm_enabled=false" in ledger_text
    assert "broker_order_call_performed=false" in ledger_text
    assert "live_trading_enabled=false" in ledger_text
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_writes_approval_receipt_blocked_audit_event_without_id(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 0

    audit_dir = tmp_path / "audit"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=audit_dir,
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="approval_receipt_audit_no_id",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    ledger_text = (audit_dir / "orchestrator_audit_ledger.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert "orchestrator_approval_receipt_state" in ledger_text
    assert "approval_id_provided=false" in ledger_text
    assert "approval_receipt_gate_allowed=false" in ledger_text
    assert "paper_arm_attempted=false" in ledger_text
    assert "broker_order_call_performed=false" in ledger_text
    assert "live_trading_enabled=false" in ledger_text
    assert "Approval receipt audit event written: true" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_approval_receipt_heartbeat_notes_allowed_state(capsys, tmp_path):
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
        session_id="approval_receipt_heartbeat_allowed",
        max_cycles=1,
        approval_id=approval_id,
        injected_cycle_runner=fake_runner,
        now=fixed_now() + timedelta(minutes=1),
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "Approval receipt heartbeat integration enabled: true" in output
    assert "approval_id_provided=true" in notes
    assert "approval_receipt_gate_allowed=true" in notes
    assert "approval_receipt_status=APPROVED" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_orchestrator_approval_receipt_heartbeat_notes_blocked_state(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 0

    heartbeat_path = tmp_path / "heartbeat.json"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=heartbeat_path,
        session_id="approval_receipt_heartbeat_no_id",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "approval_id_provided=false" in notes
    assert "approval_receipt_gate_allowed=false" in notes
    assert "paper_arm_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes
