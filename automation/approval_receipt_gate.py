"""Approval receipt gate for Jarvis Quant.

Phase 10B safety layer.

This module checks whether a local approval record is approved and still valid.
It does not trade, does not submit broker orders, and does not enable live trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from automation.approval_gateway import is_approval_expired, read_approval_record


@dataclass(frozen=True)
class ApprovalReceiptGateResult:
    approval_id: str | None
    approval_path: str | None
    allowed: bool
    approval_status: str
    blocked_reasons: list[str]
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_approval_receipt_gate(
    *,
    approval_id: str | None,
    approvals_dir: Path = Path("reports/approvals"),
    now: datetime | None = None,
) -> ApprovalReceiptGateResult:
    cleaned_id = (approval_id or "").strip()

    if not cleaned_id:
        return ApprovalReceiptGateResult(
            approval_id=None,
            approval_path=None,
            allowed=False,
            approval_status="MISSING_ID",
            blocked_reasons=["approval id is required"],
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not cleaned_id.isdigit():
        return ApprovalReceiptGateResult(
            approval_id=cleaned_id,
            approval_path=None,
            allowed=False,
            approval_status="INVALID_ID",
            blocked_reasons=["approval id must be numeric"],
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    path = approvals_dir / f"approval_{cleaned_id}.json"

    if not path.exists():
        return ApprovalReceiptGateResult(
            approval_id=cleaned_id,
            approval_path=str(path),
            allowed=False,
            approval_status="MISSING_RECORD",
            blocked_reasons=[f"approval record not found: {path}"],
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    try:
        record = read_approval_record(path)
    except Exception as exc:
        return ApprovalReceiptGateResult(
            approval_id=cleaned_id,
            approval_path=str(path),
            allowed=False,
            approval_status="READ_ERROR",
            blocked_reasons=[f"could not read approval record: {exc}"],
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    blocked_reasons: list[str] = []

    if record.approval_id != cleaned_id:
        blocked_reasons.append("approval record id does not match requested approval id")

    if record.status != "APPROVED":
        blocked_reasons.append(f"approval status is not APPROVED: {record.status}")

    if is_approval_expired(record, now=now):
        blocked_reasons.append("approval is expired")

    allowed = len(blocked_reasons) == 0

    return ApprovalReceiptGateResult(
        approval_id=cleaned_id,
        approval_path=str(path),
        allowed=allowed,
        approval_status=record.status,
        blocked_reasons=blocked_reasons,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
