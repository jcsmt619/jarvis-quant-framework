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
from automation.orchestrator_paper_arm_drill import PAPER_ARM_DRILL_CONFIRMATION
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def write_approved_record(approvals_dir: Path) -> str:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=10,
        source="test",
        note="paper arm drill audit heartbeat test",
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


def test_orchestrator_writes_paper_arm_drill_audit_event_default_state(capsys, tmp_path):
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
        session_id="paper_arm_drill_audit_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    ledger_text = (audit_dir / "orchestrator_audit_ledger.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert "Paper arm drill audit integration enabled: true" in output
    assert "Paper arm drill heartbeat integration enabled: true" in output
    assert "Paper arm drill audit event written: true" in output
    assert "orchestrator_paper_arm_drill_state" in ledger_text
    assert "paper_arm_drill_integrated=true" in ledger_text
    assert "paper_arm_drill_requested=false" in ledger_text
    assert "paper_arm_drill_attempted=false" in ledger_text
    assert "paper_arm_enabled=false" in ledger_text
    assert "real_paper_order_submitted=false" in ledger_text
    assert "broker_order_call_performed=false" in ledger_text
    assert "live_trading_enabled=false" in ledger_text
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_writes_paper_arm_drill_audit_event_injected_only(capsys, tmp_path):
    approvals_dir = tmp_path / "approvals"
    approval_id = write_approved_record(approvals_dir)
    drill_calls = []

    def fake_runner(**kwargs):
        return 0

    def fake_paper_arm_drill():
        drill_calls.append("called")
        return 0

    audit_dir = tmp_path / "audit"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=approvals_dir,
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=audit_dir,
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="paper_arm_drill_audit_injected",
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
    ledger_text = (audit_dir / "orchestrator_audit_ledger.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert drill_calls == ["called"]
    assert "orchestrator_paper_arm_drill_state" in ledger_text
    assert "paper_arm_drill_requested=true" in ledger_text
    assert "paper_arm_drill_confirmation_accepted=true" in ledger_text
    assert "approval_receipt_gate_allowed=true" in ledger_text
    assert "paper_arm_bridge_allows_drill=true" in ledger_text
    assert "injected_paper_arm_callable_wired=true" in ledger_text
    assert "paper_arm_drill_attempted=true" in ledger_text
    assert "paper_arm_drill_return_code=0" in ledger_text
    assert "DRILL_COMPLETED_WITH_INJECTED_CALLABLE_ONLY" in ledger_text
    assert "real_paper_order_submitted=false" in ledger_text
    assert "broker_order_call_performed=false" in ledger_text
    assert "live_trading_enabled=false" in ledger_text
    assert "Real paper order submitted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_paper_arm_drill_heartbeat_notes_default_state(capsys, tmp_path):
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
        session_id="paper_arm_drill_heartbeat_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "Paper arm drill heartbeat integration enabled: true" in output
    assert "paper_arm_drill_integrated=true" in notes
    assert "paper_arm_drill_requested=false" in notes
    assert "paper_arm_drill_attempted=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "real_paper_order_submitted=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_orchestrator_paper_arm_drill_heartbeat_notes_injected_only(capsys, tmp_path):
    approvals_dir = tmp_path / "approvals"
    approval_id = write_approved_record(approvals_dir)

    def fake_runner(**kwargs):
        return 0

    def fake_paper_arm_drill():
        return 0

    heartbeat_path = tmp_path / "heartbeat.json"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=approvals_dir,
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=heartbeat_path,
        session_id="paper_arm_drill_heartbeat_injected",
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
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "paper_arm_drill_requested=true" in notes
    assert "paper_arm_drill_confirmation_accepted=true" in notes
    assert "approval_receipt_gate_allowed=true" in notes
    assert "paper_arm_bridge_allows_drill=true" in notes
    assert "injected_paper_arm_callable_wired=true" in notes
    assert "paper_arm_drill_attempted=true" in notes
    assert "paper_arm_drill_return_code=0" in notes
    assert "real_paper_order_submitted=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes
