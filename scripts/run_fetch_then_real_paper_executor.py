"""One-command read-only market data fetch plus account-state-aware armed paper executor report.

Phase 9C safety layer.

This script:
1. Loads Alpaca paper-only config
2. Fetches recent read-only Alpaca market bars
3. Reads read-only Alpaca paper account state for the symbol
4. Uses actual paper account position quantity
5. Blocks execution if open paper orders already exist for the symbol
6. Runs the armed real-paper executor report from the fresh CSV

Default behavior:
- real paper execution disabled
- no paper order submitted
- live trading disabled

Paper order submission requires:
- --enable-real-paper-execution
- exact confirmation phrase
- market open
- account state clean
- execution gate ALLOWED
- executable BUY or EXIT intent
"""

from __future__ import annotations

import argparse
from pathlib import Path

from paper_trading.alpaca_account_state import (
    AlpacaPaperSymbolState,
    build_alpaca_paper_symbol_state,
    write_alpaca_paper_symbol_state,
)
from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_health import create_alpaca_paper_client
from paper_trading.alpaca_market_data import (
    fetch_alpaca_daily_bars,
    write_market_data_csv,
)
from paper_trading.paper_executor import PAPER_ORDER_CONFIRMATION
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_real_paper_executor_report import run_real_paper_executor_report


def _account_state_blocked_reasons(state: AlpacaPaperSymbolState) -> list[str]:
    reasons: list[str] = []

    if state.account_status.upper() != "ACTIVE":
        reasons.append(f"paper account status is not ACTIVE: {state.account_status}")

    if state.open_symbol_orders_count > 0:
        reasons.append(
            f"open {state.symbol} paper orders exist: {state.open_symbol_orders_count}"
        )

    return reasons


def _position_quantity_for_intent(state: AlpacaPaperSymbolState) -> int:
    return int(abs(state.position_quantity))


def run_fetch_then_real_paper_executor_report(
    *,
    env_file: Path | None = None,
    symbol: str = "EEM",
    limit: int = 120,
    feed: str | None = "iex",
    price_column: str = "Close",
    date_column: str | None = "Date",
    position_open: bool = False,
    current_position_quantity: int = 0,
    kill_switch_engaged: bool = False,
    max_position_notional: float = 10_000.0,
    max_equity_fraction: float = 0.10,
    enable_real_paper_execution: bool = False,
    confirmation: str | None = None,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()

        bars = fetch_alpaca_daily_bars(
            config=config,
            symbol=symbol,
            limit=limit,
            feed=feed,
        )

        csv_path, market_data_result = write_market_data_csv(
            bars=bars,
            symbol=symbol,
        )

        account_state = build_alpaca_paper_symbol_state(
            config=config,
            symbol=symbol,
            paper_client_factory=lambda: create_alpaca_paper_client(config),
        )
        account_state_path = write_alpaca_paper_symbol_state(account_state)
        account_state_blocked_reasons = _account_state_blocked_reasons(account_state)

    except (AlpacaConfigError, ValueError) as exc:
        print("FETCH + ACCOUNT STATE + ARMED REAL PAPER REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local wrapper
        print("FETCH + ACCOUNT STATE + ARMED REAL PAPER REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("READ-ONLY MARKET DATA FETCH: PASS")
    print(f"Symbol: {market_data_result.symbol}")
    print(f"Bars count: {market_data_result.bars_count}")
    print(f"Latest timestamp UTC: {market_data_result.latest_timestamp_utc}")
    print(f"Latest close: {market_data_result.latest_close}")
    print("READ ONLY: true")
    print("ORDER SUBMISSION DURING FETCH: DISABLED")
    print("BROKER ORDER CALL DURING FETCH: false")
    print("LIVE TRADING: DISABLED")
    print(f"CSV written to: {csv_path}")
    print("")

    print("READ-ONLY PAPER ACCOUNT STATE: PASS")
    print(f"Account status: {account_state.account_status}")
    print(f"Cash: {account_state.cash}")
    print(f"Buying power: {account_state.buying_power}")
    print(f"Portfolio value: {account_state.portfolio_value}")
    print(f"Actual {account_state.symbol} position quantity: {account_state.position_quantity}")
    print(f"Actual {account_state.symbol} position open: {account_state.position_open}")
    print(f"Open {account_state.symbol} orders count: {account_state.open_symbol_orders_count}")
    print(f"Open {account_state.symbol} order ids: {account_state.open_symbol_order_ids}")
    print(f"Account-state blocked reasons: {account_state_blocked_reasons}")
    print("READ ONLY: true")
    print("ORDER SUBMISSION DURING ACCOUNT STATE READ: DISABLED")
    print("BROKER ORDER CALL DURING ACCOUNT STATE READ: false")
    print("LIVE TRADING: DISABLED")
    print(f"Account state report written to: {account_state_path}")
    print("")

    executor_code = run_real_paper_executor_report(
        env_file=None,
        close_csv=csv_path,
        price_column=price_column,
        date_column=date_column,
        position_open=account_state.position_open,
        current_position_quantity=_position_quantity_for_intent(account_state),
        kill_switch_engaged=kill_switch_engaged,
        max_position_notional=max_position_notional,
        max_equity_fraction=max_equity_fraction,
        enable_real_paper_execution=enable_real_paper_execution,
        confirmation=confirmation,
        external_blocked_reasons=account_state_blocked_reasons,
        account_state=account_state,
    )

    print("")
    print("ONE-COMMAND REAL PAPER SAFETY SUMMARY")
    print("READ ONLY MARKET DATA FETCH: true")
    print("READ ONLY ACCOUNT STATE: true")
    print(f"ACCOUNT STATE BLOCKED REASONS: {account_state_blocked_reasons}")
    print(f"ACTUAL POSITION OPEN: {account_state.position_open}")
    print(f"ACTUAL POSITION QUANTITY: {account_state.position_quantity}")
    print(f"OPEN SYMBOL ORDERS COUNT: {account_state.open_symbol_orders_count}")
    print(f"REAL PAPER EXECUTION ENABLED: {str(enable_real_paper_execution).lower()}")
    print(f"CONFIRMATION ACCEPTED: {str(confirmation == PAPER_ORDER_CONFIRMATION).lower()}")
    print("LIVE TRADING: DISABLED")
    print("NOTE: paper order submission is possible only if every downstream gate allows it.")

    return executor_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch read-only Alpaca bars, read account state, and run armed real-paper report."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
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
    feed = None if str(args.feed).lower() in {"none", "default"} else args.feed

    return run_fetch_then_real_paper_executor_report(
        env_file=args.env_file,
        symbol=args.symbol,
        limit=args.limit,
        feed=feed,
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
