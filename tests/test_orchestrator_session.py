from datetime import UTC, datetime

import scripts.run_local_autonomous_orchestrator as orchestrator_script
import scripts.view_orchestrator_sessions as view_script
from automation.orchestrator_controls import PAUSE_FILE_NAME
from automation.orchestrator_session import (
    build_session_manifest,
    list_session_manifests,
    read_session_manifest,
    write_session_manifest,
)


def fixed_now():
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def test_session_manifest_round_trip(tmp_path):
    manifest = build_session_manifest(
        session_id="orchestrator_test_123",
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
        orchestrator_dir=tmp_path / "orchestrator",
        audit_ledger_path=tmp_path / "audit" / "orchestrator_audit_ledger.jsonl",
        stop_requested_at_end=False,
        pause_requested_at_end=False,
        resume_marker_present_at_end=False,
        real_email_send_enabled=False,
        notes=["test"],
    )

    path = write_session_manifest(manifest, session_dir=tmp_path)
    loaded = read_session_manifest(path)

    assert path.exists()
    assert loaded["session_id"] == "orchestrator_test_123"
    assert loaded["final_decision"] == "COMPLETED_MAX_CYCLES"
    assert loaded["broker_order_call_performed"] is False
    assert loaded["live_trading_enabled"] is False


def test_view_session_report_handles_empty_dir(capsys, tmp_path):
    code = view_script.run_orchestrator_session_report(
        orchestrator_dir=tmp_path,
        limit=10,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "ORCHESTRATOR SESSION REPORT: PASS" in output
    assert "Sessions count: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_writes_completed_session_manifest(capsys, tmp_path):
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
        session_id="orchestrator_test_completed",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    manifests = list_session_manifests(session_dir=tmp_path / "sessions")

    assert code == 0
    assert len(calls) == 1
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest["session_id"] == "orchestrator_test_completed"
    assert manifest["cycles_attempted"] == 1
    assert manifest["final_decision"] == "COMPLETED_MAX_CYCLES"
    assert manifest["final_return_code"] == 0
    assert manifest["inbox_processing_enabled"] is False
    assert manifest["paper_arm_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["live_trading_enabled"] is False
    assert "Session manifest written:" in output
    assert "ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES" in output


def test_orchestrator_writes_pause_session_manifest(capsys, tmp_path):
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
        session_id="orchestrator_test_pause",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    manifests = list_session_manifests(session_dir=tmp_path / "sessions")

    assert code == 0
    assert calls == []
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest["cycles_attempted"] == 0
    assert manifest["final_decision"] == "PAUSE_FILE_PRESENT_BEFORE_CYCLE_1"
    assert manifest["pause_requested_at_end"] is True
    assert manifest["broker_order_call_performed"] is False
    assert "ORCHESTRATOR DECISION: PAUSE_FILE_PRESENT_BEFORE_CYCLE_1" in output


def test_orchestrator_writes_failure_session_manifest(capsys, tmp_path):
    def fake_runner(**kwargs):
        return 7

    code = orchestrator_script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        session_id="orchestrator_test_failure",
        max_cycles=3,
        injected_cycle_runner=fake_runner,
        now=fixed_now(),
    )
    output = capsys.readouterr().out
    manifests = list_session_manifests(session_dir=tmp_path / "sessions")

    assert code == 7
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest["cycles_attempted"] == 1
    assert manifest["final_decision"] == "STOPPED_ON_CYCLE_FAILURE"
    assert manifest["final_return_code"] == 7
    assert manifest["live_trading_enabled"] is False
    assert "ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE" in output


def test_view_session_report_shows_recent_manifest(capsys, tmp_path):
    manifest = build_session_manifest(
        session_id="orchestrator_test_view",
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
        orchestrator_dir=tmp_path,
        audit_ledger_path=tmp_path / "audit" / "orchestrator_audit_ledger.jsonl",
        stop_requested_at_end=False,
        pause_requested_at_end=False,
        resume_marker_present_at_end=False,
        real_email_send_enabled=False,
    )
    write_session_manifest(manifest, session_dir=tmp_path / "sessions")

    code = view_script.run_orchestrator_session_report(
        orchestrator_dir=tmp_path,
        limit=1,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Sessions count: 1" in output
    assert "Session id: orchestrator_test_view" in output
    assert "Final decision: COMPLETED_MAX_CYCLES" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
