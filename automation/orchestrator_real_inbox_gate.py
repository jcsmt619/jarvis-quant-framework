from __future__ import annotations

from dataclasses import dataclass

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION


@dataclass(frozen=True)
class OrchestratorRealInboxReadGateResult:
    inbox_processing_requested: bool
    real_gmail_inbox_read_requested: bool
    confirmation_accepted: bool
    gate_allowed: bool
    attempted: bool
    decision: str
    blocked_reasons: list[str]
    approval_records_updated: int = 0
    real_gmail_inbox_read_performed: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_real_gmail_inbox_read_gate(
    *,
    enable_inbox_processing: bool = False,
    enable_real_gmail_inbox_read: bool = False,
    confirmation: str | None = None,
) -> OrchestratorRealInboxReadGateResult:
    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION

    if not enable_real_gmail_inbox_read:
        return OrchestratorRealInboxReadGateResult(
            inbox_processing_requested=enable_inbox_processing,
            real_gmail_inbox_read_requested=False,
            confirmation_accepted=confirmation_accepted,
            gate_allowed=False,
            attempted=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["real Gmail inbox read disabled by default"],
            approval_records_updated=0,
            real_gmail_inbox_read_performed=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not enable_inbox_processing:
        return OrchestratorRealInboxReadGateResult(
            inbox_processing_requested=False,
            real_gmail_inbox_read_requested=True,
            confirmation_accepted=confirmation_accepted,
            gate_allowed=False,
            attempted=False,
            decision="BLOCKED_INBOX_PROCESSING_NOT_ENABLED",
            blocked_reasons=["real Gmail inbox read requires inbox processing to be enabled"],
            approval_records_updated=0,
            real_gmail_inbox_read_performed=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorRealInboxReadGateResult(
            inbox_processing_requested=True,
            real_gmail_inbox_read_requested=True,
            confirmation_accepted=False,
            gate_allowed=False,
            attempted=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["Gmail inbox read confirmation phrase was not accepted"],
            approval_records_updated=0,
            real_gmail_inbox_read_performed=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorRealInboxReadGateResult(
        inbox_processing_requested=True,
        real_gmail_inbox_read_requested=True,
        confirmation_accepted=True,
        gate_allowed=True,
        attempted=False,
        decision="GATE_ALLOWED_PROCESSOR_NOT_CONNECTED_IN_THIS_PHASE",
        blocked_reasons=["gate is allowed, but real inbox processor execution remains disconnected in Phase 10C-12"],
        approval_records_updated=0,
        real_gmail_inbox_read_performed=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
