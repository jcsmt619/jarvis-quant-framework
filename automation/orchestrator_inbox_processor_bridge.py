from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION


@dataclass(frozen=True)
class OrchestratorInboxProcessorBridgeResult:
    hook_present: bool
    processor_callable_wired: bool
    requested: bool
    confirmation_accepted: bool
    real_gmail_inbox_read_enabled: bool
    attempted: bool
    decision: str
    blocked_reasons: list[str]
    approval_records_updated: int = 0
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def disabled_gmail_approval_processor_callable() -> int:
    raise RuntimeError("disabled Gmail approval processor bridge must not be executed in dry-run mode")


def evaluate_inbox_processor_dry_run_bridge(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
    enable_real_gmail_inbox_read: bool = False,
    processor_callable: Callable[[], int] | None = disabled_gmail_approval_processor_callable,
) -> OrchestratorInboxProcessorBridgeResult:
    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION
    callable_wired = processor_callable is not None

    if not enable_inbox_processing:
        return OrchestratorInboxProcessorBridgeResult(
            hook_present=True,
            processor_callable_wired=callable_wired,
            requested=False,
            confirmation_accepted=confirmation_accepted,
            real_gmail_inbox_read_enabled=False,
            attempted=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["inbox processor dry-run bridge disabled by default"],
            approval_records_updated=0,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorInboxProcessorBridgeResult(
            hook_present=True,
            processor_callable_wired=callable_wired,
            requested=True,
            confirmation_accepted=False,
            real_gmail_inbox_read_enabled=False,
            attempted=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["Gmail inbox read confirmation phrase was not accepted"],
            approval_records_updated=0,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not enable_real_gmail_inbox_read:
        return OrchestratorInboxProcessorBridgeResult(
            hook_present=True,
            processor_callable_wired=callable_wired,
            requested=True,
            confirmation_accepted=True,
            real_gmail_inbox_read_enabled=False,
            attempted=False,
            decision="DRY_RUN_BRIDGE_ONLY",
            blocked_reasons=["real Gmail inbox read is disabled in this dry-run bridge phase"],
            approval_records_updated=0,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorInboxProcessorBridgeResult(
        hook_present=True,
        processor_callable_wired=callable_wired,
        requested=True,
        confirmation_accepted=True,
        real_gmail_inbox_read_enabled=False,
        attempted=False,
        decision="BLOCKED_REAL_INBOX_READ_NOT_ALLOWED_IN_THIS_PHASE",
        blocked_reasons=["real Gmail inbox read remains blocked in Phase 10C-11"],
        approval_records_updated=0,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
