"""Local-only paper preflight report script.

This script:
- loads local .env values
- validates Alpaca paper-only config
- reads paper account snapshot
- evaluates approved EEM RSI dry-run signal
- writes a preflight control report
- submits zero orders
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.preflight import (
    build_paper_preflight_report,
    write_paper_preflight_report,
)
from scripts.check_alpaca_paper_connection import load_env_file


def _load_close_prices_csv(
    path: Path,
    price_column: str,
    date_column: str = "Date",
) -> pd.Series:
    data = pd.read_csv(path)

    if date_column not in data.columns:
        raise ValueError(f"Date column {date_column!r} not found in {path}")

    if price_column not in data.columns:
        raise ValueError(f"Price column {price_column!r} not found in {path}")

    dates = pd.to_datetime(data[date_column], utc=True, errors="coerce")
    prices = pd.to_numeric(data[price_column], errors="coerce")

    close_prices = pd.Series(prices.values, index=dates, name=price_column)
    close_prices = close_prices[close_prices.index.notna()].dropna().sort_index()

    if close_prices.empty:
        raise ValueError(f"No valid close prices found in {path}")

    return close_prices


def run_preflight(
    *,
    env_file: Path | None = None,
    close_csv: Path,
    price_column: str = "Close",
    date_column: str = "Date",
    position_open: bool = False,
    kill_switch_engaged: bool = False,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()
        close_prices = _load_close_prices_csv(close_csv, price_column, date_column)
        report = build_paper_preflight_report(
            config=config,
            close_prices=close_prices,
            position_open=position_open,
            kill_switch_engaged=kill_switch_engaged,
            is_market_open=True,
        )
        output_path = write_paper_preflight_report(report)
    except (AlpacaConfigError, ValueError) as exc:
        print("PAPER PREFLIGHT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local script wrapper
        print("PAPER PREFLIGHT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("PAPER PREFLIGHT:", "READY" if report.ready_for_paper_order_phase else "BLOCKED")
    print(f"Account status: {report.account_status}")
    print(f"Symbol: {report.symbol}")
    print(f"Strategy: {report.strategy}")
    print(f"Dry-run signal: {report.dry_run_signal}")
    print(f"Dry-run final decision: {report.dry_run_final_decision}")
    print(f"Risk gate passed: {report.risk_gate_passed}")
    print(f"Blocked reasons: {report.blocked_reasons}")
    print("ORDER SUBMISSION: DISABLED")
    print("LIVE TRADING: DISABLED")
    print(f"Preflight report written to: {output_path}")

    return 0 if report.ready_for_paper_order_phase else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a local paper preflight report with zero order submission."
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
        help="CSV file containing close prices for dry-run RSI evaluation.",
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
        "--kill-switch",
        action="store_true",
        help="Engage kill switch and force preflight block.",
    )

    args = parser.parse_args()
    return run_preflight(
        env_file=args.env_file,
        close_csv=args.close_csv,
        price_column=args.price_column,
        date_column=args.date_column,
        position_open=args.position_open,
        kill_switch_engaged=args.kill_switch,
    )


if __name__ == "__main__":
    raise SystemExit(main())
