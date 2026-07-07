from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_inbox_processor_once import run_orchestrator_inbox_processor_once
from automation.orchestrator_inbox_runtime_record import (
    build_inbox_processor_runtime_notes,
    build_inbox_processor_runtime_record,
)
from automation.orchestrator_heartbeat import read_heartbeat
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def test_inbox_processor_runtime_record_disabled_state():
    state = run_orchestrator_inbox_processor_once()
    record = build_inbox_processor_runtime_record(state)

    assert record.inbox_processor_one_cycle_attempted is False
    assert record.approval_records_updated == 0
    assert record.real_gmail_inbox_read_performed is False
    assert record.paper_arm_enabled is False
    assert record.broker_order_call_performed is False
    assert record.live_trading_enabled is False


def test_inbox_processor_runtime_notes_include_safety_flags():
    state = run_orchestrator_inbox_processor_once()
    notes = build_inbox_processor_runtime_notes(state)

    assert "inbox_processor_one_cycle_attempted=false" in notes
    assert "approval_records_updated=0" in notes
    assert "real_gmail_inbox_read_performed=false" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes


def test_orchestrator_writes_inbox_processor_audit_event(capsys, tmp_path):
    runner_calls = []
    processor_calls = []

    def fake_runner(**kwargs):
        runner_calls.append(kwargs)
        return 0

    def fake_processor():
        processor_calls.append("called")
        return 2

    audit_dir = tmp_path / "audit"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=audit_dir,
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="inbox_audit_integration",
        max_cycles=1,
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
        injected_inbox_processor_once=fake_processor,
    )
    output = capsys.readouterr().out
    ledger_text = (audit_dir / "orchestrator_audit_ledger.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert runner_calls
    assert processor_calls == ["called"]
    assert "Inbox processor audit integration enabled: true" in output
    assert "Inbox processor audit event written: true" in output
    assert "orchestrator_inbox_processor_state" in ledger_text
    assert "approval_records_updated=2" in ledger_text
    assert "real_gmail_inbox_read_performed=true" in ledger_text
    assert "broker_order_call_performed=false" in ledger_text
    assert "live_trading_enabled=false" in ledger_text


def test_orchestrator_final_heartbeat_contains_inbox_processor_notes(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 0

    def fake_processor():
        return 3

    heartbeat_path = tmp_path / "heartbeat.json"

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=heartbeat_path,
        session_id="inbox_heartbeat_integration",
        max_cycles=1,
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
        injected_inbox_processor_once=fake_processor,
    )
    output = capsys.readouterr().out
    heartbeat = read_heartbeat(heartbeat_path)
    notes = heartbeat["notes"]

    assert code == 0
    assert "Inbox processor heartbeat integration enabled: true" in output
    assert "approval_records_updated=3" in notes
    assert "real_gmail_inbox_read_performed=true" in notes
    assert "paper_arm_enabled=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "live_trading_enabled=false" in notes
