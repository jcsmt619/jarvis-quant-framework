from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    is_approval_expired,
    parse_approval_command,
    read_approval_record,
    write_approval_record,
)


def test_parse_approve_command():
    command = parse_approval_command("APPROVE 482911")

    assert command.valid is True
    assert command.action == "APPROVE"
    assert command.approval_id == "482911"
    assert command.blocked_reasons == []
    assert command.live_trading_enabled is False


def test_parse_deny_command():
    command = parse_approval_command("DENY 482911")

    assert command.valid is True
    assert command.action == "DENY"
    assert command.approval_id == "482911"


def test_parse_status_command_without_id():
    command = parse_approval_command("STATUS")

    assert command.valid is True
    assert command.action == "STATUS"
    assert command.approval_id is None


def test_parse_rejects_approve_without_id():
    command = parse_approval_command("APPROVE")

    assert command.valid is False
    assert "APPROVE requires exactly one approval id" in command.blocked_reasons


def test_parse_rejects_non_numeric_id():
    command = parse_approval_command("APPROVE abc123")

    assert command.valid is False
    assert "approval id must be numeric" in command.blocked_reasons


def test_parse_rejects_unsupported_command():
    command = parse_approval_command("TRADE NOW")

    assert command.valid is False
    assert command.action == "INVALID"
    assert "unsupported approval command: TRADE" in command.blocked_reasons


def test_create_approval_record():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)

    record = create_approval_record(
        target="PAPER_DRILL",
        ttl_minutes=10,
        source="gmail",
        note="test",
        now=now,
    )

    assert record.status == "PENDING"
    assert record.target == "PAPER_DRILL"
    assert record.source == "gmail"
    assert record.note == "test"
    assert record.live_trading_enabled is False
    assert len(record.approval_id) == 6
    assert record.approval_id.isdigit()
    assert record.created_at_utc == now.isoformat()
    assert record.expires_at_utc == (now + timedelta(minutes=10)).isoformat()


def test_approval_expiration():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", ttl_minutes=10, now=now)

    assert is_approval_expired(record, now=now + timedelta(minutes=9)) is False
    assert is_approval_expired(record, now=now + timedelta(minutes=11)) is True


def test_apply_matching_approve_command():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", ttl_minutes=10, now=now)
    command = parse_approval_command(f"APPROVE {record.approval_id}")

    updated, decision = apply_approval_command(
        record=record,
        command=command,
        now=now + timedelta(minutes=1),
    )

    assert decision.accepted is True
    assert decision.status == "APPROVED"
    assert updated.status == "APPROVED"
    assert updated.approved_at_utc == (now + timedelta(minutes=1)).isoformat()
    assert updated.live_trading_enabled is False


def test_apply_matching_deny_command():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", ttl_minutes=10, now=now)
    command = parse_approval_command(f"DENY {record.approval_id}")

    updated, decision = apply_approval_command(
        record=record,
        command=command,
        now=now + timedelta(minutes=1),
    )

    assert decision.accepted is True
    assert decision.status == "DENIED"
    assert updated.status == "DENIED"
    assert updated.denied_at_utc == (now + timedelta(minutes=1)).isoformat()


def test_apply_rejects_wrong_id():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", ttl_minutes=10, now=now)
    command = parse_approval_command("APPROVE 111111")

    updated, decision = apply_approval_command(record=record, command=command, now=now)

    assert updated == record
    assert decision.accepted is False
    assert "approval id does not match" in decision.blocked_reasons


def test_apply_rejects_expired_approval():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", ttl_minutes=10, now=now)
    command = parse_approval_command(f"APPROVE {record.approval_id}")

    updated, decision = apply_approval_command(
        record=record,
        command=command,
        now=now + timedelta(minutes=11),
    )

    assert updated.status == "EXPIRED"
    assert decision.accepted is False
    assert decision.status == "EXPIRED"
    assert "approval is expired" in decision.blocked_reasons


def test_write_and_read_approval_record(tmp_path):
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    record = create_approval_record(target="PAPER_DRILL", now=now)

    path = write_approval_record(record, output_dir=tmp_path)
    loaded = read_approval_record(path)

    assert path.name == f"approval_{record.approval_id}.json"
    assert loaded == record
