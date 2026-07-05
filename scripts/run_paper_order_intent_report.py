"""Local-only paper order intent report script.

This script:
- loads local .env values
- validates Alpaca paper-only config
- loads EEM close prices
- builds a paper preflight report
- converts the dry-run signal into a local paper order intent
- writes local reports under reports/paper_trading/
- submits zero orders
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.order_intent import (
    build_paper_order_intent,
    write_paper_order_intent,
)
from paper_trading.preflight import (
    build_paper_preflight_report,
    write_paper_preflight_report,
)
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_paper_preflight_report import _load_close_prices_csv


def _latest_price_from_close_prices(close_prices: pd.Series) -> float:
    clean = close_prices.dropna()

    if clean.empty:
        raise ValueError("No close prices available for latest price.")

    latest_price = float(clean.iloc[-1])

    if latest_price <= 0:
        raise ValueError("Latest close price must be positive.")

    return latest_price


def run_order_intent_report(
    *,
    env_file: Path | None = None,
    close_csv: Path,
    price_column: str = "Close",
    date_column: str = "Date",
    position_open: bool = False,
    current_position_quantity: int = 0,
    kill_switch_engaged: bool = False,
    max_position_notional: float = 10_000.0,
    max_equity_fraction: float = 0.10,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()
        close_prices = _load_close_prices_csv(close_csv, price_column, date_column)
        latest_price = _latest_price_from_close_prices(close_prices)

        preflight_report = build_paper_preflight_report(
            config=config,
            close_prices=close_prices,
            position_open=position_open,
            kill_switch_engaged=kill_switch_engaged,
            is_market_open=True,
        )
        preflight_path = write_paper_preflight_report(preflight_report)

        intent = build_paper_order_intent(
            preflight_report=preflight_report,
            latest_price=latest_price,
            current_position_quantity=current_position_quantity,
            max_position_notional=max_position_notional,
            max_equity_fraction=max_equity_fraction,
        )
        intent_path = write_paper_order_intent(intent)

    except (AlpacaConfigError, ValueError) as exc:
        print("PAPER ORDER INTENT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local script wrapper
        print("PAPER ORDER INTENT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print(f"PAPER ORDER INTENT: {intent.intent_action}")
    print(f"Symbol: {intent.symbol}")
    print(f"Strategy: {intent.strategy}")
    print(f"Requested signal: {intent.requested_signal}")
    print(f"Latest price: {intent.latest_price}")
    print(f"Estimated quantity: {intent.estimated_quantity}")
    print(f"Estimated notional: {intent.estimated_notional}")
    print(f"Preflight ready: {intent.preflight_ready}")
    print(f"Blocked reasons: {intent.blocked_reasons}")
    print(f"Reason: {intent.reason}")
    print("BROKER CALL PERFORMED: false")
    print("ORDER SUBMISSION: DISABLED")
    print("LIVE TRADING: DISABLED")
    print(f"Preflight report written to: {preflight_path}")
    print(f"Intent report written to: {intent_path}")

    return 1 if intent.intent_action == "BLOCKED" else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a local paper order intent report with zero order submission."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional local .env file path. Defaults to .env.",
    )
    parser.add_argument(
        "--close-csv",
        type=Path,
        required=True,
        help="CSV file containing close prices for RSI evaluation.",
    )
    parser.add_argument(
        "--price-column",
        default="Close",
        help="Close price column name. Defaults to Close.",
    )
    parser.add_argument(
        "--date-column",
        default="Date",
        help="Date column name. Defaults to Date.",
    )
    parser.add_argument(
        "--position-open",
        action="store_true",
        help="Assume an EEM paper position is already open.",
    )
    parser.add_argument(
        "--current-position-quantity",
        type=int,
        default=0,
        help="Current EEM paper position quantity assumption. Defaults to 0.",
    )
    parser.add_argument(
        "--kill-switch",
        action="store_true",
        help="Engage kill switch and block intent.",
    )
    parser.add_argument(
        "--max-position-notional",
        type=float,
        default=10_000.0,
        help="Maximum intended position notional. Defaults to 10000.",
    )
    parser.add_argument(
        "--max-equity-fraction",
        type=float,
        default=0.10,
        help="Maximum portfolio equity fraction. Defaults to 0.10.",
    )

    args = parser.parse_args()
    return run_order_intent_report(
        env_file=args.env_file,
        close_csv=args.close_csv,
        price_column=args.price_column,
        date_column=args.date_column,
        position_open=args.position_open,
        current_position_quantity=args.current_position_quantity,
        kill_switch_engaged=args.kill_switch,
        max_position_notional=args.max_position_notional,
        max_equity_fraction=args.max_equity_fraction,
    )


if __name__ == "__main__":
    raise SystemExit(main())
