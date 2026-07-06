"""Armed real Alpaca paper executor report.

Phase 7C safety layer.

This script can submit to Alpaca PAPER only if explicitly armed.

Required for paper submission:
- paper-only Alpaca config
- market session open
- approved strategy preflight
- execution gate ALLOWED
- --enable-real-paper-execution flag
- exact confirmation phrase

Live trading remains disabled.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from datetime import UTC, datetime
from typing import Callable

from paper_trading.alpaca_account_state import AlpacaPaperSymbolState
from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_health import create_alpaca_paper_client
from paper_trading.execution_gate import (
    evaluate_paper_execution_gate,
    write_paper_execution_gate_result,
)
from paper_trading.market_session import get_us_equity_market_session_status
from paper_trading.order_intent import build_paper_order_intent, write_paper_order_intent
from paper_trading.paper_executor import (
    PAPER_ORDER_CONFIRMATION,
    RealPaperExecutionResult,
    execute_real_alpaca_paper_order,
    write_real_paper_execution_result,
)
from paper_trading.paper_order_trigger_guard import (
    PaperOrderTriggerGuardResult,
    evaluate_paper_order_trigger_guard,
    write_paper_order_trigger_guard_result,
)
from paper_trading.preflight import build_paper_preflight_report, write_paper_preflight_report
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_disabled_real_paper_executor_report import _load_close_prices



def _build_trigger_guard_blocked_real_paper_result(
    *,
    intent,
    trigger_guard: PaperOrderTriggerGuardResult,
) -> RealPaperExecutionResult:
    execution_status = "NO_ACTION" if trigger_guard.intent_action == "HOLD" else "BLOCKED"

    return RealPaperExecutionResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=trigger_guard.symbol,
        strategy=getattr(intent, "strategy", "unknown"),
        intent_action=trigger_guard.intent_action,
        requested_signal=getattr(intent, "requested_signal", trigger_guard.intent_action),
        execution_attempted=False,
        execution_status=execution_status,
        submitted_side=None,
        submitted_quantity=0,
        submitted_order_type=None,
        submitted_time_in_force=None,
        paper_order_id=None,
        blocked_reasons=list(trigger_guard.blocked_reasons),
        paper_client_used=False,
        real_broker_client_used=False,
        live_trading_enabled=False,
        order_submission_to_real_broker_enabled=False,
    )


def run_real_paper_executor_report(
    *,
    env_file: Path | None = None,
    close_csv: Path,
    price_column: str = "Close",
    date_column: str | None = "Date",
    position_open: bool = False,
    current_position_quantity: int = 0,
    kill_switch_engaged: bool = False,
    max_position_notional: float = 10_000.0,
    max_equity_fraction: float = 0.10,
    enable_real_paper_execution: bool = False,
    confirmation: str | None = None,
    injected_paper_client_factory: Callable[[], object] | None = None,
    external_blocked_reasons: list[str] | None = None,
    account_state: AlpacaPaperSymbolState | None = None,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()
        close_prices = _load_close_prices(
            close_csv=close_csv,
            price_column=price_column,
            date_column=date_column,
        )

        latest_price = float(close_prices.iloc[-1])

        market_session = get_us_equity_market_session_status()
        is_market_open = bool(market_session.is_market_open)

        preflight = build_paper_preflight_report(
            config=config,
            close_prices=close_prices,
            position_open=position_open,
            kill_switch_engaged=kill_switch_engaged,
            is_market_open=is_market_open,
        )
        preflight_path = write_paper_preflight_report(preflight)

        intent = build_paper_order_intent(
            preflight_report=preflight,
            latest_price=latest_price,
            current_position_quantity=current_position_quantity,
            max_position_notional=max_position_notional,
            max_equity_fraction=max_equity_fraction,
        )

        extra_blocked_reasons = [reason for reason in (external_blocked_reasons or []) if reason]
        if extra_blocked_reasons:
            intent = replace(
                intent,
                intent_action="BLOCKED",
                estimated_quantity=0,
                estimated_notional=0.0,
                blocked_reasons=list(intent.blocked_reasons) + extra_blocked_reasons,
                reason="BLOCKED: " + "; ".join(extra_blocked_reasons),
            )

        intent_path = write_paper_order_intent(intent)

        execution_gate = evaluate_paper_execution_gate(
            config=config,
            intent=intent,
            order_submission_enabled=enable_real_paper_execution,
        )
        execution_gate_path = write_paper_execution_gate_result(execution_gate)

        trigger_guard = None
        trigger_guard_path = None

        ready_to_arm_guard = None

        if account_state is not None:
            trigger_guard = evaluate_paper_order_trigger_guard(
                account_state=account_state,
                market_session=market_session,
                intent=intent,
                execution_gate=execution_gate,
                real_paper_execution_enabled=enable_real_paper_execution,
                confirmation=confirmation,
                live_trading_enabled=False,
                paper_only=True,
            )
            trigger_guard_path = write_paper_order_trigger_guard_result(trigger_guard)

            prospective_execution_gate = evaluate_paper_execution_gate(
                config=config,
                intent=intent,
                order_submission_enabled=True,
            )
            ready_to_arm_guard = evaluate_paper_order_trigger_guard(
                account_state=account_state,
                market_session=market_session,
                intent=intent,
                execution_gate=prospective_execution_gate,
                real_paper_execution_enabled=True,
                confirmation=PAPER_ORDER_CONFIRMATION,
                live_trading_enabled=False,
                paper_only=True,
            )

        paper_client_factory = None
        if (
            trigger_guard is None or trigger_guard.allowed_to_attempt_order
        ) and enable_real_paper_execution and confirmation == PAPER_ORDER_CONFIRMATION:
            paper_client_factory = injected_paper_client_factory or (
                lambda: create_alpaca_paper_client(config)
            )

        if trigger_guard is not None and not trigger_guard.allowed_to_attempt_order:
            real_paper_result = _build_trigger_guard_blocked_real_paper_result(
                intent=intent,
                trigger_guard=trigger_guard,
            )
        else:
            real_paper_result = execute_real_alpaca_paper_order(
                config=config,
                intent=intent,
                execution_gate=execution_gate,
                paper_client_factory=paper_client_factory,
                real_paper_execution_enabled=enable_real_paper_execution,
                confirmation=confirmation,
            )

        real_paper_path = write_real_paper_execution_result(real_paper_result)

    except (AlpacaConfigError, ValueError) as exc:
        print("ARMED REAL PAPER EXECUTOR REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local wrapper
        print("ARMED REAL PAPER EXECUTOR REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
    print(f"Symbol: {real_paper_result.symbol}")
    print(f"Strategy: {real_paper_result.strategy}")
    print(f"Market session open: {is_market_open}")
    print(f"Market session reason: {market_session.reason}")
    print(f"Intent action: {real_paper_result.intent_action}")
    print(f"Requested signal: {real_paper_result.requested_signal}")
    print(f"Execution gate status: {execution_gate.execution_status}")
    print(f"Execution allowed: {execution_gate.execution_allowed}")
    print(f"Execution status: {real_paper_result.execution_status}")
    print(f"Execution attempted: {real_paper_result.execution_attempted}")
    print(f"Submitted side: {real_paper_result.submitted_side}")
    print(f"Submitted quantity: {real_paper_result.submitted_quantity}")
    print(f"Paper order id: {real_paper_result.paper_order_id}")
    print(f"Blocked reasons: {real_paper_result.blocked_reasons}")
    print(f"PAPER CLIENT USED: {str(real_paper_result.paper_client_used).lower()}")
    print(f"REAL BROKER CLIENT USED: {str(real_paper_result.real_broker_client_used).lower()}")
    print(f"REAL PAPER ORDER SUBMITTED: {str(real_paper_result.execution_attempted).lower()}")
    print(f"REAL PAPER EXECUTION ENABLED: {str(enable_real_paper_execution).lower()}")
    print(f"CONFIRMATION ACCEPTED: {str(confirmation == PAPER_ORDER_CONFIRMATION).lower()}")
    print("LIVE TRADING: DISABLED")
    print(f"Preflight report written to: {preflight_path}")
    print(f"Intent report written to: {intent_path}")
    print(f"Execution gate report written to: {execution_gate_path}")
    if trigger_guard is not None:
        print(f"Trigger guard allowed: {trigger_guard.allowed_to_attempt_order}")
        print(f"Trigger guard blocked reasons: {trigger_guard.blocked_reasons}")
        print(f"Trigger guard report written to: {trigger_guard_path}")

    if ready_to_arm_guard is not None:
        print(f"READY TO ARM: {str(ready_to_arm_guard.allowed_to_attempt_order).lower()}")
        print(f"READY TO ARM REASONS: {ready_to_arm_guard.blocked_reasons}")
        if ready_to_arm_guard.allowed_to_attempt_order:
            print("READY TO ARM ACTION: You may consider the armed PAPER command after manual review.")
        else:
            print("READY TO ARM ACTION: DO NOT RUN THE ARMED COMMAND.")
    print(f"Real paper execution report written to: {real_paper_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run armed real Alpaca paper executor report."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--close-csv", type=Path, required=True)
    parser.add_argument("--price-column", default="Close")
    parser.add_argument("--date-column", default="Date")
    parser.add_argument("--position-open", action="store_true")
    parser.add_argument("--current-position-quantity", type=int, default=0)
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--max-position-notional", type=float, default=10_000.0)
    parser.add_argument("--max-equity-fraction", type=float, default=0.10)
    parser.add_argument("--enable-real-paper-execution", action="store_true")
    parser.add_argument("--confirmation", default=None)

    args = parser.parse_args()

    return run_real_paper_executor_report(
        env_file=args.env_file,
        close_csv=args.close_csv,
        price_column=args.price_column,
        date_column=args.date_column,
        position_open=args.position_open,
        current_position_quantity=args.current_position_quantity,
        kill_switch_engaged=args.kill_switch,
        max_position_notional=args.max_position_notional,
        max_equity_fraction=args.max_equity_fraction,
        enable_real_paper_execution=args.enable_real_paper_execution,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
