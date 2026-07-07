from __future__ import annotations

from dataclasses import dataclass

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION


@dataclass(frozen=True)
class OrchestratorInboxProcessingScaffold:
    requested: bool
    confirmation_accepted: bool
    attempted: bool
    decision: str
    blocked_reasons: list[str]
    approval_records_updated: int = 0
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_inbox_processing_scaffold(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
) -> OrchestratorInboxProcessingScaffold:
    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION

    if not enable_inbox_processing:
        return OrchestratorInboxProcessingScaffold(
            requested=False,
            confirmation_accepted=confirmation_accepted,
            attempted=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["inbox processing disabled by default"],
            approval_records_updated=0,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorInboxProcessingScaffold(
            requested=True,
            confirmation_accepted=False,
            attempted=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["Gmail inbox read confirmation phrase was not accepted"],
            approval_records_updated=0,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorInboxProcessingScaffold(
        requested=True,
        confirmation_accepted=True,
        attempted=False,
        decision="BLOCKED_SCAFFOLD_ONLY",
        blocked_reasons=["inbox processing is scaffolded only in this phase"],
        approval_records_updated=0,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
