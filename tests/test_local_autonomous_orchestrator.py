from pathlib import Path

import scripts.run_local_autonomous_orchestrator as script
from paper_trading.email_alerts import GMAIL_EMAIL_CONFIRMATION


def test_orchestrator_runs_one_safe_cycle(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        print("FAKE READY TO ARM APPROVAL REQUEST")
        print("Approval record created: false")
        print("Email sent: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=1,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert calls[0]["symbol"] == "EEM"
    assert calls[0]["engine"] == "Wealth"
    assert calls[0]["enable_real_email_send"] is False
    assert "LOCAL AUTONOMOUS ORCHESTRATOR REPORT" in output
    assert "Inbox processing enabled: false" in output
    assert "Paper arm enabled: false" in output
    assert "ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_runs_multiple_cycles(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=3,
        sleep_seconds=0,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 3
    assert "Cycles attempted: 3" in output
    assert "ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES" in output


def test_orchestrator_stop_file_blocks_before_first_cycle(capsys, tmp_path):
    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / "JARVIS_STOP").write_text("stop")

    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=orchestrator_dir,
        max_cycles=2,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "ORCHESTRATOR DECISION: STOP_FILE_PRESENT_BEFORE_CYCLE_1" in output
    assert "Cycles attempted: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_stops_on_cycle_failure(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 7

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=3,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 7
    assert len(calls) == 1
    assert "ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE" in output
    assert "Cycles attempted: 1" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_blocks_invalid_max_cycles(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=0,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 2
    assert calls == []
    assert "ORCHESTRATOR DECISION: BLOCKED_INVALID_MAX_CYCLES" in output
    assert "Cycles attempted: 0" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_reports_email_confirmation_state(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_local_autonomous_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=1,
        enable_real_email_send=True,
        email_confirmation=GMAIL_EMAIL_CONFIRMATION,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert calls[0]["enable_real_email_send"] is True
    assert calls[0]["email_confirmation"] == GMAIL_EMAIL_CONFIRMATION
    assert "Real email send enabled: true" in output
    assert "Email confirmation accepted: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
