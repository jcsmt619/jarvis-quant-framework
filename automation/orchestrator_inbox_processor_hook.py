from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION


@dataclass(frozen=True)
class OrchestratorInboxProcessorHookResult:
    hook_present: bool
    requested: bool
    confirmation_accepted: bool
    attempted: bool
    decision: str
    blocked_reasons: list[str]
    approval_records_updated: int = 0
    real_gmail_inbox_read: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_inbox_processor_hook(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
    allow_processor_attempt: bool = False,
    processor: Callable[[], int] | None = None,
) -> OrchestratorInboxProcessorHookResult:
    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION

    if not enable_inbox_processing:
        return OrchestratorInboxProcessorHookResult(
            hook_present=True,
            requested=False,
            confirmation_accepted=confirmation_accepted,
            attempted=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["inbox processor disabled by default"],
            approval_records_updated=0,
            real_gmail_inbox_read=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorInboxProcessorHookResult(
            hook_present=True,
            requested=True,
            confirmation_accepted=False,
            attempted=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["Gmail inbox read confirmation phrase was not accepted"],
            approval_records_updated=0,
            real_gmail_inbox_read=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not allow_processor_attempt:
        return OrchestratorInboxProcessorHookResult(
            hook_present=True,
            requested=True,
            confirmation_accepted=True,
            attempted=False,
            decision="BLOCKED_BY_ORCHESTRATOR_GATE",
            blocked_reasons=["orchestrator inbox processor gate is disabled in this phase"],
            approval_records_updated=0,
            real_gmail_inbox_read=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if processor is None:
        return OrchestratorInboxProcessorHookResult(
            hook_present=True,
            requested=True,
            confirmation_accepted=True,
            attempted=False,
            decision="BLOCKED_NO_PROCESSOR",
            blocked_reasons=["no inbox processor callable was provided"],
            approval_records_updated=0,
            real_gmail_inbox_read=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    updated_count = int(processor())

    return OrchestratorInboxProcessorHookResult(
        hook_present=True,
        requested=True,
        confirmation_accepted=True,
        attempted=True,
        decision="PROCESSOR_ATTEMPTED",
        blocked_reasons=[],
        approval_records_updated=updated_count,
        real_gmail_inbox_read=True,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
