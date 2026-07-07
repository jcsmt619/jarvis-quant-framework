from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_inbox_processor_once import (
    parse_approval_records_updated,
    run_orchestrator_inbox_processor_once,
)
import scripts.check_orchestrator_inbox_processor_once as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def test_parse_approval_records_updated():
    assert parse_approval_records_updated("Approval records updated: 3") == 3
    assert parse_approval_records_updated("nothing here") == 0


def test_processor_once_disabled_by_default():
    state = run_orchestrator_inbox_processor_once()

    assert state.hook_present is True
    assert state.processor_callable_wired is True
    assert state.gate_allowed is False
    assert state.attempted is False
    assert state.decision == "DISABLED_BY_DEFAULT"
    assert state.approval_records_updated == 0
    assert state.real_gmail_inbox_read_performed is False
    assert state.paper_arm_enabled is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_processor_once_blocks_without_confirmation():
    state = run_orchestrator_inbox_processor_once(
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        confirmation=None,
    )

    assert state.gate_allowed is False
    assert state.attempted is False
    assert state.decision == "BLOCKED_CONFIRMATION_NOT_ACCEPTED"
    assert state.real_gmail_inbox_read_performed is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_processor_once_calls_injected_processor_when_gate_allowed():
    calls = []

    def fake_processor():
        calls.append("called")
        return 4

    state = run_orchestrator_inbox_processor_once(
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        processor_callable=fake_processor,
    )

    assert calls == ["called"]
    assert state.gate_allowed is True
    assert state.attempted is True
    assert state.processor_return_code == 0
    assert state.decision == "PROCESSOR_ATTEMPTED_READ_ONLY"
    assert state.approval_records_updated == 4
    assert state.real_gmail_inbox_read_performed is True
    assert state.paper_arm_enabled is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_processor_once_report_prints_disabled_state(capsys):
    code = check_script.run_orchestrator_inbox_processor_once_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR INBOX PROCESSOR ONE-CYCLE REPORT: PASS" in output
    assert "Inbox processor one-cycle callable wired: true" in output
    assert "Inbox processor one-cycle attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Real Gmail inbox read performed: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_processor_once_disabled_state(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="processor_once_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processor one-cycle callable wired: true" in output
    assert "Inbox processor one-cycle attempted: false" in output
    assert "Real Gmail inbox read performed: false" in output
    assert "Approval records updated: 0" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_processor_once_gate_allowed_with_injected_processor(capsys, tmp_path):
    runner_calls = []
    processor_calls = []

    def fake_runner(**kwargs):
        runner_calls.append(kwargs)
        return 0

    def fake_processor():
        processor_calls.append("called")
        return 2

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="processor_once_allowed",
        max_cycles=1,
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
        injected_inbox_processor_once=fake_processor,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(runner_calls) == 1
    assert processor_calls == ["called"]
    assert "Real Gmail inbox read gate allowed: true" in output
    assert "Inbox processor one-cycle attempted: true" in output
    assert "Inbox processor one-cycle decision: PROCESSOR_ATTEMPTED_READ_ONLY" in output
    assert "Approval records updated: 2" in output
    assert "Real Gmail inbox read performed: true" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
