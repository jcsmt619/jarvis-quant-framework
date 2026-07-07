from datetime import UTC, datetime

import scripts.run_local_autonomous_orchestrator as orchestrator_script
import scripts.view_orchestrator_audit as view_script
from automation.orchestrator_audit import (
    append_audit_event,
    build_audit_event,
    read_audit_events,
)
from automation.orchestrator_controls import PAUSE_FILE_NAME


def fixed_now():
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def test_audit_event_round_trip(tmp_path):
    event = build_audit_event(
        event_type="test_event",
        cycle_number=1,
        symbol="EEM",
        engine="Wealth",
        decision="CYCLE_COMPLETED",
        cycle_return_code=0,
        stop_requested=False,
        pause_requested=False,
        resume_marker_present=False,
        real_email_send_enabled=False,
        notes=["test note"],
        now=fixed_now(),
    )

    ledger = append_audit_event(event, audit_dir=tmp_path)
    events = read_audit_events(audit_dir=tmp_path)

    assert ledger.exists()
    assert len(events) == 1
    assert events[0]["event_type"] == "test_event"
    assert events[0]["symbol"] == "EEM"
    assert events[0]["broker_order_call_performed"] is False
    assert events[0]["live_trading_enabled"] is False


def test_view_audit_report_handles_empty_ledger(capsys, tmp_path):
    code = view_script.run_orchestrator_audit_report(
        orchestrator_dir=tmp_path,
        limit=10,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR AUDIT REPORT: PASS" in output
    assert "Events count: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_writes_success_cycle_audit(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    events = read_audit_events(audit_dir=tmp_path / "audit")
    events = [
        event
        for event in events
        if event.get("event_type") != "orchestrator_inbox_processor_state"
    ]

    assert code == 0
    assert len(calls) == 1
    assert len(events) == 2
    assert events[0]["event_type"] == "orchestrator_cycle"
    assert events[0]["decision"] == "CYCLE_COMPLETED"
    assert events[0]["cycle_return_code"] == 0
    assert events[0]["inbox_processing_enabled"] is False
    assert events[0]["paper_arm_enabled"] is False
    assert events[0]["broker_order_call_performed"] is False
    assert events[0]["live_trading_enabled"] is False
    assert events[1]["event_type"] == "orchestrator_completed"
    assert "Audit ledger path:" in output
    assert "ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES" in output


def test_orchestrator_writes_pause_block_audit(capsys, tmp_path):
    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / PAUSE_FILE_NAME).write_text("pause")

    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=orchestrator_dir,
        audit_dir=tmp_path / "audit",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    events = read_audit_events(audit_dir=tmp_path / "audit")
    events = [
        event
        for event in events
        if event.get("event_type") != "orchestrator_inbox_processor_state"
    ]

    assert code == 0
    assert calls == []
    assert len(events) == 1
    assert events[0]["event_type"] == "orchestrator_control_block"
    assert events[0]["decision"] == "PAUSE_FILE_PRESENT_BEFORE_CYCLE_1"
    assert events[0]["pause_requested"] is True
    assert events[0]["broker_order_call_performed"] is False
    assert "ORCHESTRATOR DECISION: PAUSE_FILE_PRESENT_BEFORE_CYCLE_1" in output


def test_orchestrator_writes_failure_audit(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 7

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        max_cycles=3,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    events = read_audit_events(audit_dir=tmp_path / "audit")
    events = [
        event
        for event in events
        if event.get("event_type") != "orchestrator_inbox_processor_state"
    ]

    assert code == 7
    assert len(events) == 1
    assert events[0]["decision"] == "STOPPED_ON_CYCLE_FAILURE"
    assert events[0]["cycle_return_code"] == 7
    assert events[0]["live_trading_enabled"] is False
    assert "ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE" in output


def test_view_audit_report_shows_recent_event(capsys, tmp_path):
    event = build_audit_event(
        event_type="orchestrator_cycle",
        cycle_number=1,
        symbol="EEM",
        engine="Wealth",
        decision="CYCLE_COMPLETED",
        cycle_return_code=0,
        stop_requested=False,
        pause_requested=False,
        resume_marker_present=False,
        real_email_send_enabled=False,
        now=fixed_now(),
    )
    append_audit_event(event, audit_dir=tmp_path / "audit")

    code = view_script.run_orchestrator_audit_report(
        orchestrator_dir=tmp_path,
        limit=1,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Events count: 1" in output
    assert "Event type: orchestrator_cycle" in output
    assert "Decision: CYCLE_COMPLETED" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
