from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_inbox_scaffold import evaluate_inbox_processing_scaffold
import scripts.check_orchestrator_inbox_scaffold as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def test_inbox_scaffold_disabled_by_default():
    state = evaluate_inbox_processing_scaffold()

    assert state.requested is False
    assert state.confirmation_accepted is False
    assert state.attempted is False
    assert state.decision == "DISABLED_BY_DEFAULT"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_inbox_scaffold_blocks_requested_without_confirmation():
    state = evaluate_inbox_processing_scaffold(
        enable_inbox_processing=True,
        confirmation=None,
    )

    assert state.requested is True
    assert state.confirmation_accepted is False
    assert state.attempted is False
    assert state.decision == "BLOCKED_CONFIRMATION_NOT_ACCEPTED"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_inbox_scaffold_blocks_requested_even_with_confirmation_in_this_phase():
    state = evaluate_inbox_processing_scaffold(
        enable_inbox_processing=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
    )

    assert state.requested is True
    assert state.confirmation_accepted is True
    assert state.attempted is False
    assert state.decision == "BLOCKED_SCAFFOLD_ONLY"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_inbox_scaffold_report_prints_disabled_state(capsys):
    code = check_script.run_orchestrator_inbox_scaffold_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR INBOX PROCESSING SCAFFOLD REPORT: PASS" in output
    assert "Inbox processing requested: false" in output
    assert "Inbox processing attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_default_inbox_scaffold_state(capsys, tmp_path):
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
        session_id="inbox_scaffold_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processing enabled: false" in output
    assert "Inbox processing requested: false" in output
    assert "Inbox processing attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Inbox processing decision: DISABLED_BY_DEFAULT" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_requested_inbox_scaffold_still_does_not_attempt(capsys, tmp_path):
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
        session_id="inbox_scaffold_requested",
        max_cycles=1,
        enable_inbox_processing=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processing requested: true" in output
    assert "Inbox processing confirmation accepted: true" in output
    assert "Inbox processing attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Inbox processing decision: BLOCKED_SCAFFOLD_ONLY" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
