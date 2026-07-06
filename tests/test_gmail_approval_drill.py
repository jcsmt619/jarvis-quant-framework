from datetime import UTC, datetime
from types import SimpleNamespace

import scripts.run_gmail_approval_drill as script
from automation.approval_gateway import (
    apply_approval_command,
    parse_approval_command,
    read_approval_record,
    write_approval_record,
)
from automation.approval_receipt_gate import evaluate_approval_receipt_gate


def fixed_now():
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def make_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_create_mode_writes_pending_record_and_latest_id(capsys, tmp_path):
    code = script.run_gmail_approval_drill(
        mode="create",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    output = capsys.readouterr().out

    approval_files = list(tmp_path.glob("approval_*.json"))
    latest = tmp_path / "latest_gmail_approval_drill_id.txt"

    assert code == 0
    assert len(approval_files) == 1
    assert latest.exists()

    record = read_approval_record(approval_files[0])
    assert record.status == "PENDING"
    assert record.target == "READY_TO_ARM_REVIEW"
    assert record.source == "gmail_drill"
    assert latest.read_text().strip() == record.approval_id

    assert "GMAIL APPROVAL DRILL REPORT: PASS" in output
    assert "Mode: create" in output
    assert "Approval record created: true" in output
    assert f"APPROVE {record.approval_id}" in output
    assert "Inbox processor attempted: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_verify_mode_uses_latest_id(capsys, tmp_path):
    script.run_gmail_approval_drill(
        mode="create",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    capsys.readouterr()

    code = script.run_gmail_approval_drill(
        mode="verify",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Mode: verify" in output
    assert "Receipt gate allowed: false" in output
    assert "Receipt gate status: PENDING" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_process_mode_blocks_without_real_inbox_flag(capsys, tmp_path):
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed("should not run")

    script.run_gmail_approval_drill(
        mode="create",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    capsys.readouterr()

    code = script.run_gmail_approval_drill(
        mode="process",
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=False,
        confirmation=script.GMAIL_INBOX_READ_CONFIRMATION,
        now=fixed_now(),
        injected_processor_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "Gmail inbox processor decision: BLOCKED_REAL_INBOX_READ_DISABLED" in output
    assert "Inbox processor attempted: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_process_mode_blocks_without_confirmation(capsys, tmp_path):
    calls = []

    def fake_runner(command):
        calls.append(command)
        return make_completed("should not run")

    script.run_gmail_approval_drill(
        mode="create",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    capsys.readouterr()

    code = script.run_gmail_approval_drill(
        mode="process",
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=True,
        confirmation=None,
        now=fixed_now(),
        injected_processor_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert calls == []
    assert "Gmail inbox processor decision: BLOCKED_CONFIRMATION_NOT_ACCEPTED" in output
    assert "Inbox processor attempted: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_process_mode_runs_processor_and_verifies_approved_gate(capsys, tmp_path):
    script.run_gmail_approval_drill(
        mode="create",
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )
    create_output = capsys.readouterr().out
    approval_files = list(tmp_path.glob("approval_*.json"))
    record = read_approval_record(approval_files[0])

    def fake_runner(command):
        current = read_approval_record(approval_files[0])
        approval_command = parse_approval_command(f"APPROVE {current.approval_id}")
        updated, decision = apply_approval_command(
            record=current,
            command=approval_command,
            now=fixed_now(),
        )
        assert decision.accepted is True
        write_approval_record(updated, output_dir=tmp_path)
        return make_completed("fake inbox processor applied approval")

    code = script.run_gmail_approval_drill(
        mode="process",
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=True,
        confirmation=script.GMAIL_INBOX_READ_CONFIRMATION,
        now=fixed_now(),
        injected_processor_runner=fake_runner,
    )
    output = capsys.readouterr().out

    gate = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )

    assert code == 0
    assert gate.allowed is True
    assert "Gmail inbox processor decision: PROCESSOR_ALLOWED" in output
    assert "Inbox processor attempted: true" in output
    assert "Receipt gate allowed after inbox processing: true" in output
    assert "Receipt gate status after inbox processing: APPROVED" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_unsupported_mode_fails_safely(capsys, tmp_path):
    code = script.run_gmail_approval_drill(
        mode="bad",
        env_file=None,
        approvals_dir=tmp_path,
    )
    output = capsys.readouterr().out

    assert code == 2
    assert "GMAIL APPROVAL DRILL REPORT: FAIL" in output
    assert "Unsupported mode: bad" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
