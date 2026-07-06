"""Fake-client paper order executor.

Phase 5A safety layer.

This module tests the execution path using an injected fake client only.

It does not create a real Alpaca client.
It does not allow live trading.
It does not submit real paper orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Callable

from paper_trading.alpaca_config import AlpacaPaperConfig, validate_alpaca_paper_config
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.order_intent import PaperOrderIntent


@dataclass(frozen=True)
class FakePaperExecutionResult:
    """Result from fake-client execution path."""

    timestamp_utc: str
    symbol: str
    strategy: str
    intent_action: str
    requested_signal: str
    execution_attempted: bool
    execution_status: str
    submitted_side: str | None
    submitted_quantity: int
    submitted_order_type: str | None
    submitted_time_in_force: str | None
    fake_order_id: str | None
    blocked_reasons: list[str]
    fake_client_used: bool = True
    real_broker_client_used: bool = False
    live_trading_enabled: bool = False
    order_submission_to_real_broker_enabled: bool = False
    note: str = (
        "FAKE EXECUTION ONLY: no real paper order, live order, or real broker "
        "execution was submitted."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _blocked_result(
    *,
    intent: PaperOrderIntent,
    reasons: list[str],
) -> FakePaperExecutionResult:
    return FakePaperExecutionResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        execution_attempted=False,
        execution_status="BLOCKED",
        submitted_side=None,
        submitted_quantity=0,
        submitted_order_type=None,
        submitted_time_in_force=None,
        fake_order_id=None,
        blocked_reasons=reasons,
    )


def _extract_order_id(order: object) -> str | None:
    value = getattr(order, "id", None)

    if value is None and isinstance(order, dict):
        value = order.get("id")

    return None if value is None else str(value)


def execute_with_fake_paper_client(
    *,
    config: AlpacaPaperConfig,
    intent: PaperOrderIntent,
    execution_gate: PaperExecutionGateResult,
    fake_client_factory: Callable[[], object] | None,
    fake_execution_enabled: bool = False,
) -> FakePaperExecutionResult:
    """Execute an intent against an injected fake client only.

    Required for execution attempt:
    - valid Alpaca paper-only config
    - fake_execution_enabled=True
    - fake_client_factory supplied
    - execution gate status ALLOWED
    - intent action BUY or EXIT

    HOLD is treated as safe no-action.
    """
    validate_alpaca_paper_config(config)

    if intent.live_trading_enabled:
        return _blocked_result(
            intent=intent,
            reasons=["intent live_trading_enabled must be False"],
        )

    if intent.broker_call_performed:
        return _blocked_result(
            intent=intent,
            reasons=["intent already reports broker_call_performed=True"],
        )

    if not fake_execution_enabled:
        return _blocked_result(
            intent=intent,
            reasons=["fake execution is disabled"],
        )

    if fake_client_factory is None:
        return _blocked_result(
            intent=intent,
            reasons=["fake client factory is required"],
        )

    if not execution_gate.execution_allowed:
        return _blocked_result(
            intent=intent,
            reasons=["execution gate is not allowed"] + list(execution_gate.blocked_reasons),
        )

    if execution_gate.live_trading_enabled:
        return _blocked_result(
            intent=intent,
            reasons=["execution gate live_trading_enabled must be False"],
        )

    if execution_gate.broker_call_performed:
        return _blocked_result(
            intent=intent,
            reasons=["execution gate already reports broker_call_performed=True"],
        )

    if execution_gate.order_submitted:
        return _blocked_result(
            intent=intent,
            reasons=["execution gate already reports order_submitted=True"],
        )

    if intent.intent_action == "HOLD":
        return FakePaperExecutionResult(
            timestamp_utc=datetime.now(UTC).isoformat(),
            symbol=intent.symbol,
            strategy=intent.strategy,
            intent_action=intent.intent_action,
            requested_signal=intent.requested_signal,
            execution_attempted=False,
            execution_status="NO_ACTION",
            submitted_side=None,
            submitted_quantity=0,
            submitted_order_type=None,
            submitted_time_in_force=None,
            fake_order_id=None,
            blocked_reasons=[],
        )

    if intent.intent_action not in {"BUY", "EXIT"}:
        return _blocked_result(
            intent=intent,
            reasons=[f"unsupported executable intent action: {intent.intent_action!r}"],
        )

    if intent.estimated_quantity <= 0:
        return _blocked_result(
            intent=intent,
            reasons=["estimated quantity must be positive"],
        )

    side = "buy" if intent.intent_action == "BUY" else "sell"
    client = fake_client_factory()

    order = client.submit_order(
        symbol=intent.symbol,
        qty=int(intent.estimated_quantity),
        side=side,
        type="market",
        time_in_force="day",
    )

    return FakePaperExecutionResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        execution_attempted=True,
        execution_status="FAKE_SUBMITTED",
        submitted_side=side,
        submitted_quantity=int(intent.estimated_quantity),
        submitted_order_type="market",
        submitted_time_in_force="day",
        fake_order_id=_extract_order_id(order),
        blocked_reasons=[],
    )
