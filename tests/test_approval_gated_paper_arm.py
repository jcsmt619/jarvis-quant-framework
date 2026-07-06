from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import scripts.run_approval_gated_paper_arm as script
from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)


def make_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def make_approved_record(tmp_path):
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        now=now,
    )
    command = parse_approval_command(f"APPROVE {record.approval_id}")
    approved, decision = apply_approval_command(
        record=record,
        command=command,
        now=now + timedelta(seconds=30),
    )
    assert decision.accepted is True
    write_approval_record(approved, output_dir=tmp_path)
    return approved, now


def test_missing_approval_id_blocks_without_workflow(capsys, tmp_path):
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed("should not run")

    code = script.run_approval_gated_paper_arm(
        approval_id="",
        approvals_dir=tmp_path,
        env_file=None,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "Approval gate allowed: false" in output
    assert "Approval-gated decision: BLOCKED_BY_APPROVAL_RECEIPT_GATE" in output
    assert "Wrapped workflow attempted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_pending_approval_blocks_without_workflow(capsys, tmp_path):
    record = create_approval_record(target="READY_TO_ARM_REVIEW")
    write_approval_record(record, output_dir=tmp_path)
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed("should not run")

    code = script.run_approval_gated_paper_arm(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "Approval status: PENDING" in output
    assert "Approval gate allowed: false" in output
    assert "approval status is not APPROVED: PENDING" in output
    assert "Wrapped workflow attempted: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_approved_record_runs_disabled_workflow_by_default(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed(
            """
REAL PAPER ORDER SUBMITTED: false
PAPER CLIENT USED: false
REAL BROKER CLIENT USED: false
LIVE TRADING: DISABLED
"""
        )

    code = script.run_approval_gated_paper_arm(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        injected_workflow_runner=fake_runner,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "--enable-real-paper-execution" not in calls[0]
    assert "--confirmation" not in calls[0]
    assert "Approval gate allowed: true" in output
    assert "Armed paper execution requested: false" in output
    assert "Approval-gated decision: WORKFLOW_ALLOWED" in output
    assert "Wrapped workflow attempted: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_approved_record_with_enable_but_wrong_confirmation_blocks_before_workflow(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed("should not run")

    code = script.run_approval_gated_paper_arm(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        enable_real_paper_execution=True,
        confirmation=None,
        injected_workflow_runner=fake_runner,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "Approval gate allowed: true" in output
    assert "Armed paper execution requested: true" in output
    assert "Paper confirmation accepted: false" in output
    assert "Approval-gated decision: BLOCKED_BY_PAPER_CONFIRMATION" in output
    assert "Wrapped workflow attempted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_approved_record_with_enable_and_confirmation_passes_armed_flags(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed(
            """
REAL PAPER ORDER SUBMITTED: false
PAPER CLIENT USED: false
REAL BROKER CLIENT USED: false
LIVE TRADING: DISABLED
"""
        )

    code = script.run_approval_gated_paper_arm(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        enable_real_paper_execution=True,
        confirmation=script.PAPER_ORDER_CONFIRMATION,
        injected_workflow_runner=fake_runner,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1
    assert "--enable-real-paper-execution" in calls[0]
    assert "--confirmation" in calls[0]
    assert script.PAPER_ORDER_CONFIRMATION in calls[0]
    assert "Approval gate allowed: true" in output
    assert "Paper confirmation accepted: true" in output
    assert "Approval-gated decision: WORKFLOW_ALLOWED" in output
    assert "Wrapped workflow attempted: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_workflow_broker_output_is_reported(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)

    def fake_runner(command):
        return make_completed(
            """
REAL PAPER ORDER SUBMITTED: true
PAPER CLIENT USED: true
REAL BROKER CLIENT USED: true
LIVE TRADING: DISABLED
"""
        )

    code = script.run_approval_gated_paper_arm(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        enable_real_paper_execution=True,
        confirmation=script.PAPER_ORDER_CONFIRMATION,
        injected_workflow_runner=fake_runner,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Broker order call performed: true" in output
    assert "LIVE TRADING: DISABLED" in output


def test_workflow_failure_returns_failure_code(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)

    def fake_runner(command):
        return make_completed("workflow failed", returncode=7, stderr="error")

    code = script.run_approval_gated_paper_arm(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        env_file=None,
        injected_workflow_runner=fake_runner,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 7
    assert "Wrapped workflow return code: 7" in output
    assert "Wrapped workflow stderr:" in output
    assert "LIVE TRADING: DISABLED" in output
