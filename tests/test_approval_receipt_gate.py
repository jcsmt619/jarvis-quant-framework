from datetime import UTC, datetime, timedelta

import scripts.check_approval_receipt_gate as script
from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.approval_receipt_gate import evaluate_approval_receipt_gate


def make_approved_record(tmp_path, *, now=None, ttl_minutes=10):
    current = now or datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        ttl_minutes=ttl_minutes,
        now=current,
    )
    command = parse_approval_command(f"APPROVE {record.approval_id}")
    approved, decision = apply_approval_command(
        record=record,
        command=command,
        now=current + timedelta(seconds=30),
    )
    assert decision.accepted is True
    write_approval_record(approved, output_dir=tmp_path)
    return approved, current


def test_gate_allows_approved_non_expired_record(tmp_path):
    approved, now = make_approved_record(tmp_path)

    result = evaluate_approval_receipt_gate(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        now=now + timedelta(minutes=1),
    )

    assert result.allowed is True
    assert result.approval_status == "APPROVED"
    assert result.blocked_reasons == []
    assert result.broker_order_call_performed is False
    assert result.live_trading_enabled is False


def test_gate_blocks_pending_record(tmp_path):
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="READY_TO_ARM_REVIEW", now=now)
    write_approval_record(record, output_dir=tmp_path)

    result = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
        now=now + timedelta(minutes=1),
    )

    assert result.allowed is False
    assert result.approval_status == "PENDING"
    assert "approval status is not APPROVED: PENDING" in result.blocked_reasons


def test_gate_blocks_denied_record(tmp_path):
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="READY_TO_ARM_REVIEW", now=now)
    command = parse_approval_command(f"DENY {record.approval_id}")
    denied, decision = apply_approval_command(
        record=record,
        command=command,
        now=now + timedelta(seconds=30),
    )
    assert decision.accepted is True
    write_approval_record(denied, output_dir=tmp_path)

    result = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
        now=now + timedelta(minutes=1),
    )

    assert result.allowed is False
    assert result.approval_status == "DENIED"
    assert "approval status is not APPROVED: DENIED" in result.blocked_reasons


def test_gate_blocks_expired_approved_record(tmp_path):
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    approved, _ = make_approved_record(tmp_path, now=now, ttl_minutes=1)

    result = evaluate_approval_receipt_gate(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        now=now + timedelta(minutes=2),
    )

    assert result.allowed is False
    assert result.approval_status == "APPROVED"
    assert "approval is expired" in result.blocked_reasons


def test_gate_blocks_missing_record(tmp_path):
    result = evaluate_approval_receipt_gate(
        approval_id="123456",
        approvals_dir=tmp_path,
    )

    assert result.allowed is False
    assert result.approval_status == "MISSING_RECORD"
    assert "approval record not found" in result.blocked_reasons[0]


def test_gate_blocks_missing_id(tmp_path):
    result = evaluate_approval_receipt_gate(
        approval_id="",
        approvals_dir=tmp_path,
    )

    assert result.allowed is False
    assert result.approval_status == "MISSING_ID"
    assert "approval id is required" in result.blocked_reasons


def test_gate_blocks_non_numeric_id(tmp_path):
    result = evaluate_approval_receipt_gate(
        approval_id="abc123",
        approvals_dir=tmp_path,
    )

    assert result.allowed is False
    assert result.approval_status == "INVALID_ID"
    assert "approval id must be numeric" in result.blocked_reasons


def test_script_reports_allowed_for_approved_record(capsys, tmp_path):
    approved, now = make_approved_record(tmp_path)

    code = script.run_approval_receipt_gate_report(
        approval_id=approved.approval_id,
        approvals_dir=tmp_path,
        now=now + timedelta(minutes=1),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "APPROVAL RECEIPT GATE REPORT: PASS" in output
    assert "Approval status: APPROVED" in output
    assert "Gate allowed: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_script_reports_blocked_for_pending_record(capsys, tmp_path):
    record = create_approval_record(target="READY_TO_ARM_REVIEW")
    write_approval_record(record, output_dir=tmp_path)

    code = script.run_approval_receipt_gate_report(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Approval status: PENDING" in output
    assert "Gate allowed: false" in output
    assert "approval status is not APPROVED: PENDING" in output
    assert "LIVE TRADING: DISABLED" in output
