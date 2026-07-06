"""Local read-only Alpaca market data fetch script.

Phase 6A.

Fetches recent EEM daily bars from Alpaca and writes a local CSV.
Submits zero orders.
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


def run_market_data_fetch(
    *,
    env_file: Path | None = None,
    symbol: str = "EEM",
    limit: int = 120,
    feed: str | None = "iex",
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
        csv_path, result = write_market_data_csv(
            bars=bars,
            symbol=symbol,
        )
    except (AlpacaConfigError, ValueError) as exc:
        print("ALPACA MARKET DATA FETCH: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:
        print("ALPACA MARKET DATA FETCH: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ALPACA MARKET DATA FETCH: PASS")
    print(f"Symbol: {result.symbol}")
    print(f"Timeframe: {result.timeframe}")
    print(f"Bars count: {result.bars_count}")
    print(f"Latest timestamp UTC: {result.latest_timestamp_utc}")
    print(f"Latest close: {result.latest_close}")
    print("READ ONLY: true")
    print("ORDER SUBMISSION: DISABLED")
    print("BROKER ORDER CALL PERFORMED: false")
    print("LIVE TRADING: DISABLED")
    print(f"CSV written to: {csv_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch read-only Alpaca market data with zero orders."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")

    args = parser.parse_args()
    feed = None if str(args.feed).lower() in {"none", "default"} else args.feed

    return run_market_data_fetch(
        env_file=args.env_file,
        symbol=args.symbol,
        limit=args.limit,
        feed=feed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
