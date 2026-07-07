import scripts.run_safe_multi_cycle_orchestrator as script


def test_multi_cycle_blocks_without_confirmation(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=2,
        confirmation=None,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "SAFE MULTI-CYCLE DECISION: BLOCKED_CONFIRMATION_NOT_ACCEPTED" in output
    assert "Underlying orchestrator attempted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_multi_cycle_blocks_too_few_cycles(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=1,
        confirmation=script.SAFE_MULTI_CYCLE_CONFIRMATION,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 2
    assert calls == []
    assert "SAFE MULTI-CYCLE DECISION: BLOCKED_TOO_FEW_CYCLES" in output
    assert "LIVE TRADING: DISABLED" in output


def test_multi_cycle_blocks_too_many_cycles(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=script.MAX_SAFE_MULTI_CYCLES + 1,
        confirmation=script.SAFE_MULTI_CYCLE_CONFIRMATION,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 2
    assert calls == []
    assert "SAFE MULTI-CYCLE DECISION: BLOCKED_TOO_MANY_CYCLES" in output
    assert "LIVE TRADING: DISABLED" in output


def test_multi_cycle_blocks_invalid_sleep(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=2,
        sleep_seconds=-1,
        confirmation=script.SAFE_MULTI_CYCLE_CONFIRMATION,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 2
    assert calls == []
    assert "SAFE MULTI-CYCLE DECISION: BLOCKED_NEGATIVE_SLEEP" in output
    assert "LIVE TRADING: DISABLED" in output


def test_multi_cycle_allows_safe_orchestrator_and_forces_disabled_modes(capsys, tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        print("FAKE LOCAL ORCHESTRATOR")
        print("Inbox processing enabled: false")
        print("Paper arm enabled: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        audit_dir=tmp_path / "audit",
        session_dir=tmp_path / "sessions",
        session_id="safe_multi_test",
        symbol="EEM",
        max_cycles=3,
        sleep_seconds=0,
        confirmation=script.SAFE_MULTI_CYCLE_CONFIRMATION,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert calls[0]["max_cycles"] == 3
    assert calls[0]["enable_real_email_send"] is False
    assert calls[0]["email_confirmation"] is None
    assert "SAFE MULTI-CYCLE DECISION: ORCHESTRATOR_ALLOWED" in output
    assert "Underlying orchestrator attempted: true" in output
    assert "Real email send enabled: false" in output
    assert "Inbox processing enabled: false" in output
    assert "Paper arm enabled: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_multi_cycle_propagates_orchestrator_failure(capsys, tmp_path):
    def fake_runner(**kwargs):
        print("FAKE LOCAL ORCHESTRATOR FAILURE")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 7

    code = script.run_safe_multi_cycle_orchestrator(
        env_file=None,
        approvals_dir=tmp_path / "approvals",
        orchestrator_dir=tmp_path / "orchestrator",
        max_cycles=2,
        confirmation=script.SAFE_MULTI_CYCLE_CONFIRMATION,
        injected_orchestrator_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 7
    assert "Underlying orchestrator return code: 7" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
