"""Local-only Alpaca paper account snapshot script.

This script:
- loads local .env values
- validates Alpaca paper-only config
- reads account, positions, and open orders
- writes a redacted JSON snapshot under reports/paper_trading/
- submits zero orders
"""

from __future__ import annotations

import argparse
from pathlib import Path

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_snapshot import (
    collect_alpaca_paper_account_snapshot,
    write_alpaca_paper_account_snapshot,
)
from scripts.check_alpaca_paper_connection import load_env_file


def run_snapshot(env_file: Path | None = None) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()
        snapshot = collect_alpaca_paper_account_snapshot(config)
        output_path = write_alpaca_paper_account_snapshot(snapshot)
    except AlpacaConfigError as exc:
        print("ALPACA PAPER SNAPSHOT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local script wrapper
        print("ALPACA PAPER SNAPSHOT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ALPACA PAPER SNAPSHOT: PASS")
    print(f"Account status: {snapshot.account_status}")
    print(f"Cash: {snapshot.cash}")
    print(f"Buying power: {snapshot.buying_power}")
    print(f"Portfolio value: {snapshot.portfolio_value}")
    print(f"Positions count: {snapshot.positions_count}")
    print(f"Open orders count: {snapshot.open_orders_count}")
    print("ORDER SUBMISSION: DISABLED")
    print("LIVE TRADING: DISABLED")
    print(f"Snapshot written to: {output_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a redacted Alpaca paper account snapshot."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional local .env file path. Defaults to .env.",
    )

    args = parser.parse_args()
    return run_snapshot(env_file=args.env_file)


if __name__ == "__main__":
    raise SystemExit(main())
