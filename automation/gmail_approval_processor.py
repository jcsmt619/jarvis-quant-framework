"""Gmail approval processor for Jarvis Quant.

Phase 10B safety layer.

This module applies authorized Gmail approval commands to local approval records.
It does not trade, does not submit broker orders, and does not enable live trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automation.approval_gateway import (
    ApprovalDecision,
    ApprovalRecord,
    apply_approval_command,
    read_approval_record,
    write_approval_record,
)
from automation.gmail_approval_inbox import GmailApprovalInboxReadResult, InboundApprovalEmail


@dataclass(frozen=True)
class ProcessedApprovalEmail:
    message_id: str
    from_email: str
    subject: str
    action: str
    approval_id: str | None
    command_valid: bool
    sender_authorized: bool
    applied: bool
    decision_status: str
    blocked_reasons: list[str]
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class GmailApprovalProcessResult:
    processed_count: int
    applied_count: int
    processed_emails: list[ProcessedApprovalEmail]
    blocked_reasons: list[str]
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _approval_record_path(approval_id: str, approvals_dir: Path) -> Path:
    return approvals_dir / f"approval_{approval_id}.json"


def process_gmail_approval_emails(
    *,
    inbox_result: GmailApprovalInboxReadResult,
    approvals_dir: Path = Path("reports/approvals"),
) -> GmailApprovalProcessResult:
    processed: list[ProcessedApprovalEmail] = []

    for email in inbox_result.approval_emails:
        command = email.command
        blocked_reasons = list(email.blocked_reasons)

        if not email.sender_authorized:
            processed.append(
                ProcessedApprovalEmail(
                    message_id=email.message_id,
                    from_email=email.from_email,
                    subject=email.subject,
                    action=command.action,
                    approval_id=command.approval_id,
                    command_valid=command.valid,
                    sender_authorized=False,
                    applied=False,
                    decision_status="BLOCKED",
                    blocked_reasons=blocked_reasons,
                )
            )
            continue

        if not command.valid:
            processed.append(
                ProcessedApprovalEmail(
                    message_id=email.message_id,
                    from_email=email.from_email,
                    subject=email.subject,
                    action=command.action,
                    approval_id=command.approval_id,
                    command_valid=False,
                    sender_authorized=True,
                    applied=False,
                    decision_status="BLOCKED",
                    blocked_reasons=blocked_reasons,
                )
            )
            continue

        if command.action not in {"APPROVE", "DENY"}:
            processed.append(
                ProcessedApprovalEmail(
                    message_id=email.message_id,
                    from_email=email.from_email,
                    subject=email.subject,
                    action=command.action,
                    approval_id=command.approval_id,
                    command_valid=True,
                    sender_authorized=True,
                    applied=False,
                    decision_status="NO_RECORD_ACTION",
                    blocked_reasons=[f"{command.action} does not update an approval record"],
                )
            )
            continue

        if command.approval_id is None:
            processed.append(
                ProcessedApprovalEmail(
                    message_id=email.message_id,
                    from_email=email.from_email,
                    subject=email.subject,
                    action=command.action,
                    approval_id=None,
                    command_valid=False,
                    sender_authorized=True,
                    applied=False,
                    decision_status="BLOCKED",
                    blocked_reasons=["approval id is required"],
                )
            )
            continue

        path = _approval_record_path(command.approval_id, approvals_dir)
        if not path.exists():
            processed.append(
                ProcessedApprovalEmail(
                    message_id=email.message_id,
                    from_email=email.from_email,
                    subject=email.subject,
                    action=command.action,
                    approval_id=command.approval_id,
                    command_valid=True,
                    sender_authorized=True,
                    applied=False,
                    decision_status="MISSING_RECORD",
                    blocked_reasons=[f"approval record not found: {path}"],
                )
            )
            continue

        record = read_approval_record(path)
        updated_record, decision = apply_approval_command(record=record, command=command)
        write_approval_record(updated_record, output_dir=approvals_dir)

        processed.append(
            ProcessedApprovalEmail(
                message_id=email.message_id,
                from_email=email.from_email,
                subject=email.subject,
                action=command.action,
                approval_id=command.approval_id,
                command_valid=True,
                sender_authorized=True,
                applied=decision.accepted,
                decision_status=decision.status,
                blocked_reasons=list(decision.blocked_reasons),
            )
        )

    return GmailApprovalProcessResult(
        processed_count=len(processed),
        applied_count=sum(1 for item in processed if item.applied),
        processed_emails=processed,
        blocked_reasons=list(inbox_result.blocked_reasons),
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
