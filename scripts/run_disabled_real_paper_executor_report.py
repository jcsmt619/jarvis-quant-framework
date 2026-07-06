"""Disabled real Alpaca paper executor report.

Phase 7B safety layer.

This script exercises the real Alpaca paper executor module while keeping
real paper execution disabled by default.

It may read Alpaca paper account state through the preflight layer.
It does not submit paper orders.
It does not submit live orders.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.execution_gate import evaluate_paper_execution_gate
from paper_trading.order_intent import build_paper_order_intent
from paper_trading.paper_executor import (
    execute_real_alpaca_paper_order,
    write_real_paper_execution_result,
)
from paper_trading.preflight import build_paper_preflight_report, write_paper_preflight_report
from scripts.check_alpaca_paper_connection import load_env_file


def _load_close_prices(
    *,
    close_csv: Path,
    price_column: str = "Close",
    date_column: str | None = "Date",
) -> pd.Series:
    df = pd.read_csv(close_csv)

    if price_column not in df.columns:
        raise ValueError(
            f"CSV does not contain price column {price_column!r}. "
            f"Available columns: {list(df.columns)!r}"
        )

    close_prices = pd.to_numeric(df[price_column], errors="coerce").dropna()

    if date_column and date_column in df.columns:
        dates = pd.to_datetime(df.loc[close_prices.index, date_column], errors="coerce", utc=True)
        close_prices.index = dates

    close_prices.name = price_column
    return close_prices


def run_disabled_real_paper_executor_report(
    *,
    env_file: Path | None = None,
    close_csv: Path,
    price_column: str = "Close",
    date_column: str | None = "Date",
    position_open: bool = False,
    current_position_quantity: int = 0,
    kill_switch_engaged: bool = False,
    is_market_open: bool | None = False,
    max_position_notional: float = 10_000.0,
    max_equity_fraction: float = 0.10,
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

        execution_gate = evaluate_paper_execution_gate(
            config=config,
            intent=intent,
            order_submission_enabled=False,
        )

        real_paper_result = execute_real_alpaca_paper_order(
            config=config,
            intent=intent,
            execution_gate=execution_gate,
            paper_client_factory=None,
            real_paper_execution_enabled=False,
            confirmation=None,
        )
        real_paper_path = write_real_paper_execution_result(real_paper_result)

    except (AlpacaConfigError, ValueError) as exc:
        print("DISABLED REAL PAPER EXECUTOR REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local wrapper
        print("DISABLED REAL PAPER EXECUTOR REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("DISABLED REAL PAPER EXECUTOR REPORT: PASS")
    print(f"Symbol: {real_paper_result.symbol}")
    print(f"Strategy: {real_paper_result.strategy}")
    print(f"Intent action: {real_paper_result.intent_action}")
    print(f"Requested signal: {real_paper_result.requested_signal}")
    print(f"Execution status: {real_paper_result.execution_status}")
    print(f"Execution attempted: {real_paper_result.execution_attempted}")
    print(f"Submitted side: {real_paper_result.submitted_side}")
    print(f"Submitted quantity: {real_paper_result.submitted_quantity}")
    print(f"Paper order id: {real_paper_result.paper_order_id}")
    print(f"Blocked reasons: {real_paper_result.blocked_reasons}")
    print(f"PAPER CLIENT USED: {str(real_paper_result.paper_client_used).lower()}")
    print(f"REAL BROKER CLIENT USED: {str(real_paper_result.real_broker_client_used).lower()}")
    print(f"REAL PAPER ORDER SUBMITTED: {str(real_paper_result.execution_attempted).lower()}")
    print("REAL PAPER EXECUTION ENABLED: false")
    print("LIVE TRADING: DISABLED")
    print(f"Preflight report written to: {preflight_path}")
    print(f"Real paper execution report written to: {real_paper_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run disabled real Alpaca paper executor report."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--close-csv", type=Path, required=True)
    parser.add_argument("--price-column", default="Close")
    parser.add_argument("--date-column", default="Date")
    parser.add_argument("--position-open", action="store_true")
    parser.add_argument("--current-position-quantity", type=int, default=0)
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--market-open", action="store_true")
    parser.add_argument("--max-position-notional", type=float, default=10_000.0)
    parser.add_argument("--max-equity-fraction", type=float, default=0.10)

    args = parser.parse_args()

    return run_disabled_real_paper_executor_report(
        env_file=args.env_file,
        close_csv=args.close_csv,
        price_column=args.price_column,
        date_column=args.date_column,
        position_open=args.position_open,
        current_position_quantity=args.current_position_quantity,
        kill_switch_engaged=args.kill_switch,
        is_market_open=True if args.market_open else False,
        max_position_notional=args.max_position_notional,
        max_equity_fraction=args.max_equity_fraction,
    )


if __name__ == "__main__":
    raise SystemExit(main())
