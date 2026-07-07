from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_real_inbox_gate import evaluate_real_gmail_inbox_read_gate
import scripts.check_orchestrator_real_inbox_gate as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def test_real_inbox_gate_disabled_by_default():
    state = evaluate_real_gmail_inbox_read_gate()

    assert state.inbox_processing_requested is False
    assert state.real_gmail_inbox_read_requested is False
    assert state.confirmation_accepted is False
    assert state.gate_allowed is False
    assert state.attempted is False
    assert state.decision == "DISABLED_BY_DEFAULT"
    assert state.approval_records_updated == 0
    assert state.real_gmail_inbox_read_performed is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_real_inbox_gate_blocks_real_read_without_inbox_processing():
    state = evaluate_real_gmail_inbox_read_gate(
        enable_inbox_processing=False,
        enable_real_gmail_inbox_read=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
    )

    assert state.inbox_processing_requested is False
    assert state.real_gmail_inbox_read_requested is True
    assert state.confirmation_accepted is True
    assert state.gate_allowed is False
    assert state.attempted is False
    assert state.decision == "BLOCKED_INBOX_PROCESSING_NOT_ENABLED"
    assert state.real_gmail_inbox_read_performed is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_real_inbox_gate_blocks_without_confirmation():
    state = evaluate_real_gmail_inbox_read_gate(
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        confirmation=None,
    )

    assert state.inbox_processing_requested is True
    assert state.real_gmail_inbox_read_requested is True
    assert state.confirmation_accepted is False
    assert state.gate_allowed is False
    assert state.attempted is False
    assert state.decision == "BLOCKED_CONFIRMATION_NOT_ACCEPTED"
    assert state.real_gmail_inbox_read_performed is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_real_inbox_gate_allows_gate_but_does_not_attempt_processor_in_this_phase():
    state = evaluate_real_gmail_inbox_read_gate(
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
    )

    assert state.inbox_processing_requested is True
    assert state.real_gmail_inbox_read_requested is True
    assert state.confirmation_accepted is True
    assert state.gate_allowed is True
    assert state.attempted is False
    assert state.decision == "GATE_ALLOWED_PROCESSOR_NOT_CONNECTED_IN_THIS_PHASE"
    assert state.approval_records_updated == 0
    assert state.real_gmail_inbox_read_performed is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_real_inbox_gate_report_prints_disabled_state(capsys):
    code = check_script.run_orchestrator_real_inbox_gate_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR REAL GMAIL INBOX READ GATE REPORT: PASS" in output
    assert "Real Gmail inbox read requested: false" in output
    assert "Real Gmail inbox read gate allowed: false" in output
    assert "Real Gmail inbox read attempted: false" in output
    assert "Real Gmail inbox read performed: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_real_inbox_gate_default_state(capsys, tmp_path):
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
        session_id="real_inbox_gate_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Real Gmail inbox read requested: false" in output
    assert "Real Gmail inbox read confirmation accepted: false" in output
    assert "Real Gmail inbox read gate allowed: false" in output
    assert "Real Gmail inbox read attempted: false" in output
    assert "Real Gmail inbox read performed: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_real_inbox_gate_allowed_but_processor_still_not_attempted(capsys, tmp_path):
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
        session_id="real_inbox_gate_allowed",
        max_cycles=1,
        enable_inbox_processing=True,
        enable_real_gmail_inbox_read=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processing requested: true" in output
    assert "Real Gmail inbox read requested: true" in output
    assert "Real Gmail inbox read confirmation accepted: true" in output
    assert "Real Gmail inbox read gate allowed: true" in output
    assert "Real Gmail inbox read attempted: false" in output
    assert "Real Gmail inbox read performed: false" in output
    assert "Inbox processor attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
