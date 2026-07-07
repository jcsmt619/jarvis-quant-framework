from datetime import UTC, datetime

import scripts.run_local_autonomous_orchestrator as orchestrator_script
import scripts.view_orchestrator_heartbeat as view_script
from automation.orchestrator_controls import PAUSE_FILE_NAME
from automation.orchestrator_heartbeat import (
    build_heartbeat,
    read_heartbeat,
    write_heartbeat,
)


def fixed_now():
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def test_heartbeat_round_trip(tmp_path):
    hb = build_heartbeat(
        session_id="heartbeat_test",
        cycle_number=1,
        symbol="EEM",
        engine="Wealth",
        last_decision="CYCLE_COMPLETED",
        cycles_attempted=1,
        max_cycles=1,
        stop_requested=False,
        pause_requested=False,
        resume_marker_present=False,
        audit_ledger_path=tmp_path / "audit.jsonl",
        session_manifest_path=tmp_path / "session.json",
        real_email_send_enabled=False,
        notes=["test"],
        now=fixed_now(),
    )

    path = write_heartbeat(hb, path=tmp_path / "heartbeat.json")
    loaded = read_heartbeat(path)

    assert path.exists()
    assert loaded["session_id"] == "heartbeat_test"
    assert loaded["last_decision"] == "CYCLE_COMPLETED"
    assert loaded["broker_order_call_performed"] is False
    assert loaded["live_trading_enabled"] is False


def test_view_heartbeat_report_handles_missing_file(capsys, tmp_path):
    code = view_script.run_orchestrator_heartbeat_report(orchestrator_dir=tmp_path)
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR HEARTBEAT REPORT: PASS" in output
    assert "Heartbeat present: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_writes_completed_heartbeat(capsys, tmp_path):
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
        session_id="heartbeat_completed",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    hb = read_heartbeat(tmp_path / "heartbeat.json")

    assert code == 0
    assert len(calls) == 1
    assert hb["session_id"] == "heartbeat_completed"
    assert hb["last_decision"] == "COMPLETED_MAX_CYCLES"
    assert hb["cycles_attempted"] == 1
    assert hb["inbox_processing_enabled"] is False
    assert hb["paper_arm_enabled"] is False
    assert hb["broker_order_call_performed"] is False
    assert hb["live_trading_enabled"] is False
    assert "Heartbeat written:" in output


def test_orchestrator_writes_pause_heartbeat(capsys, tmp_path):
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
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="heartbeat_pause",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    hb = read_heartbeat(tmp_path / "heartbeat.json")

    assert code == 0
    assert calls == []
    assert hb["last_decision"] == "PAUSE_FILE_PRESENT_BEFORE_CYCLE_1"
    assert hb["cycles_attempted"] == 0
    assert hb["pause_requested"] is True
    assert hb["broker_order_call_performed"] is False
    assert "ORCHESTRATOR DECISION: PAUSE_FILE_PRESENT_BEFORE_CYCLE_1" in output


def test_orchestrator_writes_failure_heartbeat(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 7

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        heartbeat_file=tmp_path / "heartbeat.json",
        session_id="heartbeat_failure",
        max_cycles=3,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    hb = read_heartbeat(tmp_path / "heartbeat.json")

    assert code == 7
    assert hb["last_decision"] == "STOPPED_ON_CYCLE_FAILURE"
    assert hb["cycles_attempted"] == 1
    assert hb["live_trading_enabled"] is False
    assert "ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE" in output


def test_view_heartbeat_report_shows_state(capsys, tmp_path):
    hb = build_heartbeat(
        session_id="heartbeat_view",
        cycle_number=2,
        symbol="EEM",
        engine="Wealth",
        last_decision="COMPLETED_MAX_CYCLES",
        cycles_attempted=2,
        max_cycles=2,
        stop_requested=False,
        pause_requested=False,
        resume_marker_present=False,
        audit_ledger_path=tmp_path / "audit.jsonl",
        session_manifest_path=tmp_path / "session.json",
        real_email_send_enabled=False,
        now=fixed_now(),
    )
    write_heartbeat(hb, path=tmp_path / "orchestrator_heartbeat.json")

    code = view_script.run_orchestrator_heartbeat_report(orchestrator_dir=tmp_path)
    output = capsys.readouterr().out

    assert code == 0
    assert "Heartbeat present: true" in output
    assert "Session id: heartbeat_view" in output
    assert "Last decision: COMPLETED_MAX_CYCLES" in output
    assert "Cycles attempted: 2" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
