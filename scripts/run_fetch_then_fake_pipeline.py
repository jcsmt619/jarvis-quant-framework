"""One-command read-only market data fetch plus fake paper pipeline.

Phase 6B safety layer.

This script:
1. Loads Alpaca paper-only config
2. Fetches recent read-only market bars
3. Writes a local CSV
4. Runs the fake paper execution pipeline using that CSV

It submits zero real paper orders.
It submits zero live orders.
It performs no real broker order calls.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_market_data import (
    fetch_alpaca_daily_bars,
    write_market_data_csv,
)
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_fake_paper_execution_pipeline import run_fake_execution_pipeline


def run_fetch_then_fake_pipeline(
    *,
    env_file: Path | None = None,
    symbol: str = "EEM",
    limit: int = 120,
    feed: str | None = "iex",
    position_open: bool = False,
    current_position_quantity: int = 0,
    kill_switch_engaged: bool = False,
    max_position_notional: float = 10_000.0,
    max_equity_fraction: float = 0.10,
    fake_execution_enabled: bool = True,
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

    except (AlpacaConfigError, ValueError) as exc:
        print("READ-ONLY FETCH + FAKE PIPELINE: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local wrapper
        print("READ-ONLY FETCH + FAKE PIPELINE: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("READ-ONLY MARKET DATA FETCH: PASS")
    print(f"Symbol: {market_data_result.symbol}")
    print(f"Bars count: {market_data_result.bars_count}")
    print(f"Latest timestamp UTC: {market_data_result.latest_timestamp_utc}")
    print(f"Latest close: {market_data_result.latest_close}")
    print("READ ONLY: true")
    print("ORDER SUBMISSION: DISABLED")
    print("BROKER ORDER CALL PERFORMED: false")
    print("LIVE TRADING: DISABLED")
    print(f"CSV written to: {csv_path}")
    print("")

    pipeline_code = run_fake_execution_pipeline(
        env_file=None,
        close_csv=csv_path,
        price_column="Close",
        date_column="Date",
        position_open=position_open,
        current_position_quantity=current_position_quantity,
        kill_switch_engaged=kill_switch_engaged,
        max_position_notional=max_position_notional,
        max_equity_fraction=max_equity_fraction,
        fake_execution_enabled=fake_execution_enabled,
    )

    print("")
    print("ONE-COMMAND SAFETY SUMMARY")
    print("READ ONLY MARKET DATA FETCH: true")
    print("FAKE CLIENT USED: true")
    print("REAL BROKER CLIENT USED: false")
    print("REAL PAPER ORDER SUBMITTED: false")
    print("LIVE TRADING: DISABLED")

    return pipeline_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch read-only Alpaca bars and run fake paper pipeline."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--position-open", action="store_true")
    parser.add_argument("--current-position-quantity", type=int, default=0)
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--max-position-notional", type=float, default=10_000.0)
    parser.add_argument("--max-equity-fraction", type=float, default=0.10)
    parser.add_argument("--disable-fake-execution", action="store_true")

    args = parser.parse_args()
    feed = None if str(args.feed).lower() in {"none", "default"} else args.feed

    return run_fetch_then_fake_pipeline(
        env_file=args.env_file,
        symbol=args.symbol,
        limit=args.limit,
        feed=feed,
        position_open=args.position_open,
        current_position_quantity=args.current_position_quantity,
        kill_switch_engaged=args.kill_switch,
        max_position_notional=args.max_position_notional,
        max_equity_fraction=args.max_equity_fraction,
        fake_execution_enabled=not args.disable_fake_execution,
    )


if __name__ == "__main__":
    raise SystemExit(main())
