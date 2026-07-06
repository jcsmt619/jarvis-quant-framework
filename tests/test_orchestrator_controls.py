import scripts.control_local_orchestrator as control_script
import scripts.run_local_autonomous_orchestrator as orchestrator_script
from automation.orchestrator_controls import (
    PAUSE_FILE_NAME,
    RESUME_FILE_NAME,
    STOP_FILE_NAME,
    clear_controls,
    read_control_state,
)


def test_pause_action_writes_pause_file(capsys, tmp_path):
    code = control_script.run_orchestrator_control(
        action="pause",
        orchestrator_dir=tmp_path,
        note="test pause",
    )
    output = capsys.readouterr().out
    state = read_control_state(tmp_path)

    assert code == 0
    assert state.pause_requested is True
    assert (tmp_path / PAUSE_FILE_NAME).exists()
    assert "Action: pause" in output
    assert "Pause requested: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_stop_action_writes_stop_file(capsys, tmp_path):
    code = control_script.run_orchestrator_control(
        action="stop",
        orchestrator_dir=tmp_path,
    )
    output = capsys.readouterr().out
    state = read_control_state(tmp_path)

    assert code == 0
    assert state.stop_requested is True
    assert (tmp_path / STOP_FILE_NAME).exists()
    assert "Action: stop" in output
    assert "Stop requested: true" in output
    assert "LIVE TRADING: DISABLED" in output


def test_resume_action_removes_pause_and_writes_resume_marker(capsys, tmp_path):
    control_script.run_orchestrator_control(action="pause", orchestrator_dir=tmp_path)
    capsys.readouterr()

    code = control_script.run_orchestrator_control(action="resume", orchestrator_dir=tmp_path)
    output = capsys.readouterr().out
    state = read_control_state(tmp_path)

    assert code == 0
    assert state.pause_requested is False
    assert state.resume_marker_present is True
    assert not (tmp_path / PAUSE_FILE_NAME).exists()
    assert (tmp_path / RESUME_FILE_NAME).exists()
    assert "Action: resume" in output
    assert "Pause requested: false" in output
    assert "Resume marker present: true" in output


def test_clear_action_removes_all_control_files(capsys, tmp_path):
    control_script.run_orchestrator_control(action="pause", orchestrator_dir=tmp_path)
    control_script.run_orchestrator_control(action="stop", orchestrator_dir=tmp_path)
    control_script.run_orchestrator_control(action="resume", orchestrator_dir=tmp_path)
    capsys.readouterr()

    code = control_script.run_orchestrator_control(action="clear", orchestrator_dir=tmp_path)
    output = capsys.readouterr().out
    state = read_control_state(tmp_path)

    assert code == 0
    assert state.stop_requested is False
    assert state.pause_requested is False
    assert state.resume_marker_present is False
    assert "Action: clear" in output
    assert "Stop requested: false" in output
    assert "Pause requested: false" in output


def test_status_reports_existing_controls(capsys, tmp_path):
    (tmp_path / PAUSE_FILE_NAME).write_text("pause")

    code = control_script.run_orchestrator_control(action="status", orchestrator_dir=tmp_path)
    output = capsys.readouterr().out

    assert code == 0
    assert "Action: status" in output
    assert "Pause requested: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_pause_file_blocks_before_first_cycle(capsys, tmp_path):
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
        max_cycles=2,
        injected_cycle_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "ORCHESTRATOR DECISION: PAUSE_FILE_PRESENT_BEFORE_CYCLE_1" in output
    assert "Cycles attempted: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_orchestrator_stop_takes_precedence_over_pause(capsys, tmp_path):
    orchestrator_dir = tmp_path / "orchestrator"
    orchestrator_dir.mkdir()
    (orchestrator_dir / STOP_FILE_NAME).write_text("stop")
    (orchestrator_dir / PAUSE_FILE_NAME).write_text("pause")

    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = orchestrator_script.run_local_autonomous_orchestrator(
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
    assert "PAUSE_FILE_PRESENT" not in output
    assert "LIVE TRADING: DISABLED" in output
