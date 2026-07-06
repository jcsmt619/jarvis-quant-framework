"""Real Alpaca paper-order executor.

Phase 7A safety layer.

This module can submit to an Alpaca PAPER account only, but it is disabled
by default and requires explicit confirmation.

It does not allow live trading.
It rejects live Alpaca endpoints.
It only accepts already-approved execution gate results.
It is not wired into the one-command fake pipeline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from paper_trading.alpaca_config import AlpacaPaperConfig, validate_alpaca_paper_config
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.order_intent import PaperOrderIntent


PAPER_ORDER_CONFIRMATION = "I_UNDERSTAND_THIS_SUBMITS_A_REAL_ALPACA_PAPER_ORDER"


@dataclass(frozen=True)
class RealPaperExecutionResult:
    """Result from real Alpaca paper execution path."""

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
    paper_order_id: str | None
    blocked_reasons: list[str]
    paper_client_used: bool = False
    real_broker_client_used: bool = False
    live_trading_enabled: bool = False
    order_submission_to_real_broker_enabled: bool = False
    note: str = (
        "REAL ALPACA PAPER EXECUTION MODULE: can submit only to Alpaca paper "
        "when explicitly enabled and confirmed. Live trading is disabled."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _blocked_result(
    *,
    intent: PaperOrderIntent,
    reasons: list[str],
) -> RealPaperExecutionResult:
    return RealPaperExecutionResult(
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
        paper_order_id=None,
        blocked_reasons=reasons,
        paper_client_used=False,
        real_broker_client_used=False,
        live_trading_enabled=False,
        order_submission_to_real_broker_enabled=False,
    )


def _extract_order_id(order: object) -> str | None:
    value = getattr(order, "id", None)

    if value is None and isinstance(order, dict):
        value = order.get("id")

    return None if value is None else str(value)


def execute_real_alpaca_paper_order(
    *,
    config: AlpacaPaperConfig,
    intent: PaperOrderIntent,
    execution_gate: PaperExecutionGateResult,
    paper_client_factory: Callable[[], object] | None,
    real_paper_execution_enabled: bool = False,
    confirmation: str | None = None,
) -> RealPaperExecutionResult:
    """Submit an approved BUY/EXIT intent to an Alpaca paper client.

    Required for execution attempt:
    - valid Alpaca paper-only config
    - real_paper_execution_enabled=True
    - confirmation matches PAPER_ORDER_CONFIRMATION exactly
    - injected paper_client_factory supplied
    - execution gate status ALLOWED
    - intent action BUY or EXIT

    This function rejects live trading and live endpoints through
    validate_alpaca_paper_config(config).
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

    if not execution_gate.execution_allowed:
        return _blocked_result(
            intent=intent,
            reasons=["execution gate is not allowed"] + list(execution_gate.blocked_reasons),
        )

    if intent.intent_action == "HOLD":
        return RealPaperExecutionResult(
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
            paper_order_id=None,
            blocked_reasons=[],
            paper_client_used=False,
            real_broker_client_used=False,
            live_trading_enabled=False,
            order_submission_to_real_broker_enabled=False,
        )

    if not real_paper_execution_enabled:
        return _blocked_result(
            intent=intent,
            reasons=["real Alpaca paper execution is disabled"],
        )

    if confirmation != PAPER_ORDER_CONFIRMATION:
        return _blocked_result(
            intent=intent,
            reasons=["paper order confirmation phrase is missing or incorrect"],
        )

    if paper_client_factory is None:
        return _blocked_result(
            intent=intent,
            reasons=["paper client factory is required"],
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

    if intent.estimated_notional <= 0:
        return _blocked_result(
            intent=intent,
            reasons=["estimated notional must be positive"],
        )

    side = "buy" if intent.intent_action == "BUY" else "sell"
    client = paper_client_factory()

    order = client.submit_order(
        symbol=intent.symbol,
        qty=int(intent.estimated_quantity),
        side=side,
        type="market",
        time_in_force="day",
    )

    return RealPaperExecutionResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        execution_attempted=True,
        execution_status="PAPER_SUBMITTED",
        submitted_side=side,
        submitted_quantity=int(intent.estimated_quantity),
        submitted_order_type="market",
        submitted_time_in_force="day",
        paper_order_id=_extract_order_id(order),
        blocked_reasons=[],
        paper_client_used=True,
        real_broker_client_used=True,
        live_trading_enabled=False,
        order_submission_to_real_broker_enabled=True,
    )


def write_real_paper_execution_result(
    result: RealPaperExecutionResult,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write real paper execution result to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"real_paper_execution_{stamp}.json"

    file_path.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
