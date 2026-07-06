"""Approval gateway for Jarvis Quant.

Phase 10B safety layer.

This module parses owner approval commands and manages approval records.
It does not trade, does not submit broker orders, and does not enable live trading.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal


ApprovalAction = Literal[
    "APPROVE",
    "DENY",
    "STATUS",
    "PAUSE",
    "RESUME",
    "STOP",
    "INVALID",
]


APPROVAL_ACTIONS_REQUIRING_ID = {"APPROVE", "DENY"}
APPROVAL_ACTIONS_WITHOUT_ID = {"STATUS", "PAUSE", "RESUME", "STOP"}
ALLOWED_APPROVAL_TARGETS = {
    "PAPER_DRILL",
    "CODE_CONTINUE",
    "RESEARCH_CONTINUE",
    "READY_TO_ARM_REVIEW",
}


@dataclass(frozen=True)
class ApprovalCommand:
    raw_text: str
    action: ApprovalAction
    approval_id: str | None
    valid: bool
    blocked_reasons: list[str]
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    target: str
    status: str
    created_at_utc: str
    expires_at_utc: str
    approved_at_utc: str | None = None
    denied_at_utc: str | None = None
    source: str = "gmail"
    note: str = ""
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class ApprovalDecision:
    approval_id: str | None
    action: str
    accepted: bool
    status: str
    blocked_reasons: list[str]
    live_trading_enabled: bool = False


def _utc_now() -> datetime:
    return datetime.now(UTC)


def parse_approval_command(raw_text: str) -> ApprovalCommand:
    text = (raw_text or "").strip()
    blocked_reasons: list[str] = []

    if not text:
        return ApprovalCommand(
            raw_text=raw_text,
            action="INVALID",
            approval_id=None,
            valid=False,
            blocked_reasons=["empty command"],
        )

    first_line = text.splitlines()[0].strip()
    parts = first_line.split()
    action = parts[0].upper()

    if action in APPROVAL_ACTIONS_REQUIRING_ID:
        if len(parts) != 2:
            blocked_reasons.append(f"{action} requires exactly one approval id")
            approval_id = None
        else:
            approval_id = parts[1].strip()

        if approval_id and not approval_id.isdigit():
            blocked_reasons.append("approval id must be numeric")

        return ApprovalCommand(
            raw_text=raw_text,
            action=action,  # type: ignore[arg-type]
            approval_id=approval_id,
            valid=len(blocked_reasons) == 0,
            blocked_reasons=blocked_reasons,
        )

    if action in APPROVAL_ACTIONS_WITHOUT_ID:
        if len(parts) != 1:
            blocked_reasons.append(f"{action} does not accept extra arguments")

        return ApprovalCommand(
            raw_text=raw_text,
            action=action,  # type: ignore[arg-type]
            approval_id=None,
            valid=len(blocked_reasons) == 0,
            blocked_reasons=blocked_reasons,
        )

    return ApprovalCommand(
        raw_text=raw_text,
        action="INVALID",
        approval_id=None,
        valid=False,
        blocked_reasons=[f"unsupported approval command: {action}"],
    )


def create_approval_record(
    *,
    target: str,
    ttl_minutes: int = 10,
    source: str = "gmail",
    note: str = "",
    now: datetime | None = None,
) -> ApprovalRecord:
    if target not in ALLOWED_APPROVAL_TARGETS:
        raise ValueError(f"unsupported approval target: {target}")

    current = now or _utc_now()
    expires = current + timedelta(minutes=ttl_minutes)
    approval_id = str(secrets.randbelow(900000) + 100000)

    return ApprovalRecord(
        approval_id=approval_id,
        target=target,
        status="PENDING",
        created_at_utc=current.isoformat(),
        expires_at_utc=expires.isoformat(),
        source=source,
        note=note,
        live_trading_enabled=False,
    )


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def is_approval_expired(record: ApprovalRecord, *, now: datetime | None = None) -> bool:
    current = now or _utc_now()
    return current > _parse_dt(record.expires_at_utc)


def apply_approval_command(
    *,
    record: ApprovalRecord,
    command: ApprovalCommand,
    now: datetime | None = None,
) -> tuple[ApprovalRecord, ApprovalDecision]:
    current = now or _utc_now()

    if not command.valid:
        return record, ApprovalDecision(
            approval_id=command.approval_id,
            action=command.action,
            accepted=False,
            status=record.status,
            blocked_reasons=list(command.blocked_reasons),
        )

    if command.action not in {"APPROVE", "DENY"}:
        return record, ApprovalDecision(
            approval_id=command.approval_id,
            action=command.action,
            accepted=False,
            status=record.status,
            blocked_reasons=[f"{command.action} does not apply to a pending approval record"],
        )

    if command.approval_id != record.approval_id:
        return record, ApprovalDecision(
            approval_id=command.approval_id,
            action=command.action,
            accepted=False,
            status=record.status,
            blocked_reasons=["approval id does not match"],
        )

    if record.status != "PENDING":
        return record, ApprovalDecision(
            approval_id=command.approval_id,
            action=command.action,
            accepted=False,
            status=record.status,
            blocked_reasons=[f"approval is not pending: {record.status}"],
        )

    if is_approval_expired(record, now=current):
        expired = ApprovalRecord(
            **{
                **asdict(record),
                "status": "EXPIRED",
            }
        )
        return expired, ApprovalDecision(
            approval_id=command.approval_id,
            action=command.action,
            accepted=False,
            status="EXPIRED",
            blocked_reasons=["approval is expired"],
        )

    if command.action == "APPROVE":
        updated = ApprovalRecord(
            **{
                **asdict(record),
                "status": "APPROVED",
                "approved_at_utc": current.isoformat(),
            }
        )
        return updated, ApprovalDecision(
            approval_id=command.approval_id,
            action="APPROVE",
            accepted=True,
            status="APPROVED",
            blocked_reasons=[],
        )

    updated = ApprovalRecord(
        **{
            **asdict(record),
            "status": "DENIED",
            "denied_at_utc": current.isoformat(),
        }
    )
    return updated, ApprovalDecision(
        approval_id=command.approval_id,
        action="DENY",
        accepted=True,
        status="DENIED",
        blocked_reasons=[],
    )


def write_approval_record(
    record: ApprovalRecord,
    *,
    output_dir: Path = Path("reports/approvals"),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"approval_{record.approval_id}.json"
    path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_approval_record(path: Path) -> ApprovalRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ApprovalRecord(**data)
