from pathlib import Path

import scripts.check_orchestrator_health as script
from automation.orchestrator_health import evaluate_orchestrator_health
from automation.orchestrator_controls import PAUSE_FILE_NAME, STOP_FILE_NAME
from automation.orchestrator_heartbeat import build_heartbeat, write_heartbeat
from automation.orchestrator_session import build_session_manifest, write_session_manifest
from automation.orchestrator_audit import build_audit_event, append_audit_event


def test_health_passes_with_env_and_no_controls(capsys, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")

    code = script.run_orchestrator_health_report(
        env_file=env_file,
        orchestrator_dir=tmp_path / "orchestrator",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR HEALTH CHECK REPORT: PASS" in output
    assert "Env file present: true" in output
    assert "Safe to run: true" in output
    assert "Inbox processing enabled: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_health_blocks_missing_env_when_required(tmp_path):
    result = evaluate_orchestrator_health(
        env_file=tmp_path / ".env",
        orchestrator_dir=tmp_path / "orchestrator",
        require_env_file=True,
    )

    assert result.safe_to_run is False
    assert result.env_file_present is False
    assert any("env file not found" in reason for reason in result.blocked_reasons)
    assert result.broker_order_call_performed is False
    assert result.live_trading_enabled is False


def test_health_can_ignore_missing_env(tmp_path):
    result = evaluate_orchestrator_health(
        env_file=tmp_path / ".env",
        orchestrator_dir=tmp_path / "orchestrator",
        require_env_file=False,
    )

    assert result.safe_to_run is True
    assert result.env_file_present is False
    assert result.blocked_reasons == []


def test_health_blocks_stop_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")

    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / STOP_FILE_NAME).write_text("stop")

    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
    )

    assert result.safe_to_run is False
    assert result.stop_requested is True
    assert "JARVIS_STOP is present" in result.blocked_reasons


def test_health_blocks_pause_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")

    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / PAUSE_FILE_NAME).write_text("pause")

    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
    )

    assert result.safe_to_run is False
    assert result.pause_requested is True
    assert "JARVIS_PAUSE is present" in result.blocked_reasons


def test_health_reads_existing_heartbeat(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")

    orchestrator_dir = tmp_path / "orchestrator"
    hb = build_heartbeat(
        session_id="health_heartbeat",
        cycle_number=1,
        symbol="EEM",
        engine="Wealth",
        last_decision="COMPLETED_MAX_CYCLES",
        cycles_attempted=1,
        max_cycles=1,
        stop_requested=False,
        pause_requested=False,
        resume_marker_present=False,
        audit_ledger_path=orchestrator_dir / "audit" / "orchestrator_audit_ledger.jsonl",
        session_manifest_path=orchestrator_dir / "sessions" / "session.json",
        real_email_send_enabled=False,
    )
    write_heartbeat(hb, path=orchestrator_dir / "orchestrator_heartbeat.json")

    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
    )

    assert result.safe_to_run is True
    assert result.heartbeat_present is True
    assert result.heartbeat_readable is True


def test_health_blocks_corrupt_heartbeat(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")

    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / "orchestrator_heartbeat.json").write_text("{bad json")

    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
    )

    assert result.safe_to_run is False
    assert result.heartbeat_present is True
    assert result.heartbeat_readable is False
    assert any("heartbeat is not readable" in reason for reason in result.blocked_reasons)


def test_health_counts_sessions_and_audit_events(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY=true")
    orchestrator_dir = tmp_path / "orchestrator"

    manifest = build_session_manifest(
        session_id="orchestrator_health_session",
        started_at_utc="2026-07-06T12:00:00+00:00",
        ended_at_utc="2026-07-06T12:01:00+00:00",
        symbol="EEM",
        engine="Wealth",
        max_cycles=1,
        sleep_seconds=0,
        cycles_attempted=1,
        final_decision="COMPLETED_MAX_CYCLES",
        final_return_code=0,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=orchestrator_dir,
        audit_ledger_path=orchestrator_dir / "audit" / "orchestrator_audit_ledger.jsonl",
        stop_requested_at_end=False,
        pause_requested_at_end=False,
        resume_marker_present_at_end=False,
        real_email_send_enabled=False,
    )
    write_session_manifest(manifest, session_dir=orchestrator_dir / "sessions")

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
    )
    append_audit_event(event, audit_dir=orchestrator_dir / "audit")

    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
    )

    assert result.safe_to_run is True
    assert result.sessions_count == 1
    assert result.audit_events_count == 1
