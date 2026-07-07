from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_inbox_processor_bridge import evaluate_inbox_processor_dry_run_bridge
import scripts.check_orchestrator_inbox_processor_bridge as check_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script


def test_inbox_processor_bridge_disabled_by_default():
    state = evaluate_inbox_processor_dry_run_bridge()

    assert state.hook_present is True
    assert state.processor_callable_wired is True
    assert state.requested is False
    assert state.real_gmail_inbox_read_enabled is False
    assert state.attempted is False
    assert state.decision == "DISABLED_BY_DEFAULT"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_inbox_processor_bridge_blocks_without_confirmation():
    state = evaluate_inbox_processor_dry_run_bridge(
        enable_inbox_processing=True,
        confirmation=None,
    )

    assert state.hook_present is True
    assert state.processor_callable_wired is True
    assert state.requested is True
    assert state.confirmation_accepted is False
    assert state.real_gmail_inbox_read_enabled is False
    assert state.attempted is False
    assert state.decision == "BLOCKED_CONFIRMATION_NOT_ACCEPTED"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_inbox_processor_bridge_does_not_call_processor_in_dry_run():
    calls = []

    def fake_processor():
        calls.append("called")
        return 5

    state = evaluate_inbox_processor_dry_run_bridge(
        enable_inbox_processing=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        enable_real_gmail_inbox_read=False,
        processor_callable=fake_processor,
    )

    assert calls == []
    assert state.hook_present is True
    assert state.processor_callable_wired is True
    assert state.confirmation_accepted is True
    assert state.real_gmail_inbox_read_enabled is False
    assert state.attempted is False
    assert state.decision == "DRY_RUN_BRIDGE_ONLY"
    assert state.approval_records_updated == 0
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False


def test_bridge_report_prints_disabled_state(capsys):
    code = check_script.run_orchestrator_inbox_processor_bridge_report()
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR INBOX PROCESSOR DRY-RUN BRIDGE REPORT: PASS" in output
    assert "Inbox processor hook present: true" in output
    assert "Inbox processor callable wired: true" in output
    assert "Real Gmail inbox read enabled: false" in output
    assert "Inbox processor attempted: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_prints_inbox_processor_bridge_default_state(capsys, tmp_path):
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
        session_id="inbox_processor_bridge_default",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processor callable wired: true" in output
    assert "Real Gmail inbox read enabled: false" in output
    assert "Inbox processor attempted: false" in output
    assert "Inbox processor bridge decision: DISABLED_BY_DEFAULT" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_requested_bridge_stays_dry_run(capsys, tmp_path):
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
        session_id="inbox_processor_bridge_requested",
        max_cycles=1,
        enable_inbox_processing=True,
        inbox_confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "Inbox processing requested: true" in output
    assert "Inbox processor callable wired: true" in output
    assert "Real Gmail inbox read enabled: false" in output
    assert "Inbox processor attempted: false" in output
    assert "Inbox processor bridge decision: DRY_RUN_BRIDGE_ONLY" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
