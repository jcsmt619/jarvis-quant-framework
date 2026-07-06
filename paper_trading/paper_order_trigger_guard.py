"""Final trigger guard before real Alpaca paper order attempts.

Phase 9E safety layer.

This module does not submit orders. It evaluates whether a real Alpaca PAPER
order attempt is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from paper_trading.alpaca_account_state import AlpacaPaperSymbolState
from paper_trading.paper_executor import PAPER_ORDER_CONFIRMATION


EXECUTABLE_INTENT_ACTIONS = {"BUY", "EXIT"}


@dataclass(frozen=True)
class PaperOrderTriggerGuardResult:
    timestamp_utc: str
    symbol: str
    allowed_to_attempt_order: bool
    blocked_reasons: list[str]
    intent_action: str
    execution_gate_status: str
    market_session_open: bool
    account_status: str
    open_symbol_orders_count: int
    real_paper_execution_enabled: bool
    confirmation_accepted: bool
    live_trading_enabled: bool
    paper_only: bool
    order_submission_attempted: bool = False
    real_broker_client_used: bool = False


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def evaluate_paper_order_trigger_guard(
    *,
    account_state: AlpacaPaperSymbolState,
    market_session: Any,
    intent: Any,
    execution_gate: Any,
    real_paper_execution_enabled: bool,
    confirmation: str | None,
    live_trading_enabled: bool = False,
    paper_only: bool = True,
) -> PaperOrderTriggerGuardResult:
    """Evaluate the final pre-attempt guard for real Alpaca PAPER orders."""

    symbol = _text(_get_attr(intent, "symbol", account_state.symbol)).upper()
    intent_action = _text(_get_attr(intent, "intent_action", "")).upper()
    execution_gate_status = _text(_get_attr(execution_gate, "execution_status", "")).upper()

    market_session_open = bool(
        _get_attr(
            market_session,
            "is_open",
            _get_attr(market_session, "market_is_open", False),
        )
    )

    confirmation_accepted = confirmation == PAPER_ORDER_CONFIRMATION

    blocked_reasons: list[str] = []

    if not paper_only:
        blocked_reasons.append("paper_only is false")

    if live_trading_enabled:
        blocked_reasons.append("live trading is enabled")

    if not market_session_open:
        blocked_reasons.append("market session is not open")

    if account_state.account_status.upper() != "ACTIVE":
        blocked_reasons.append(f"paper account status is not ACTIVE: {account_state.account_status}")

    if account_state.open_symbol_orders_count > 0:
        blocked_reasons.append(
            f"open {account_state.symbol} paper orders exist: {account_state.open_symbol_orders_count}"
        )

    if intent_action not in EXECUTABLE_INTENT_ACTIONS:
        blocked_reasons.append(f"intent action is not executable: {intent_action}")

    if execution_gate_status != "ALLOWED":
        blocked_reasons.append(f"execution gate status is not ALLOWED: {execution_gate_status}")

    if not real_paper_execution_enabled:
        blocked_reasons.append("real paper execution is disabled")

    if not confirmation_accepted:
        blocked_reasons.append("real paper confirmation phrase was not accepted")

    return PaperOrderTriggerGuardResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=symbol,
        allowed_to_attempt_order=len(blocked_reasons) == 0,
        blocked_reasons=blocked_reasons,
        intent_action=intent_action,
        execution_gate_status=execution_gate_status,
        market_session_open=market_session_open,
        account_status=account_state.account_status,
        open_symbol_orders_count=account_state.open_symbol_orders_count,
        real_paper_execution_enabled=real_paper_execution_enabled,
        confirmation_accepted=confirmation_accepted,
        live_trading_enabled=live_trading_enabled,
        paper_only=paper_only,
    )
