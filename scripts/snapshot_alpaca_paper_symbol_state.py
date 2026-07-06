"""Local read-only Alpaca paper symbol state snapshot script."""

from __future__ import annotations

import argparse
from pathlib import Path

from paper_trading.alpaca_account_state import (
    build_alpaca_paper_symbol_state,
    write_alpaca_paper_symbol_state,
)
from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_health import create_alpaca_paper_client
from scripts.check_alpaca_paper_connection import load_env_file


def run_alpaca_paper_symbol_state_snapshot(
    *,
    env_file: Path | None = None,
    symbol: str = "EEM",
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()

        state = build_alpaca_paper_symbol_state(
            config=config,
            symbol=symbol,
            paper_client_factory=lambda: create_alpaca_paper_client(config),
        )
        path = write_alpaca_paper_symbol_state(state)

    except (AlpacaConfigError, ValueError) as exc:
        print("ALPACA PAPER SYMBOL STATE: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local wrapper
        print("ALPACA PAPER SYMBOL STATE: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ALPACA PAPER SYMBOL STATE: PASS")
    print(f"Symbol: {state.symbol}")
    print(f"Account status: {state.account_status}")
    print(f"Cash: {state.cash}")
    print(f"Buying power: {state.buying_power}")
    print(f"Portfolio value: {state.portfolio_value}")
    print(f"Position quantity: {state.position_quantity}")
    print(f"Position open: {state.position_open}")
    print(f"Open symbol orders count: {state.open_symbol_orders_count}")
    print(f"Open symbol order ids: {state.open_symbol_order_ids}")
    print("READ ONLY: true")
    print("ORDER SUBMISSION: DISABLED")
    print("BROKER ORDER CALL PERFORMED: false")
    print("LIVE TRADING: DISABLED")
    print(f"State report written to: {path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Alpaca paper account state for one symbol."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--symbol", default="EEM")

    args = parser.parse_args()

    return run_alpaca_paper_symbol_state_snapshot(
        env_file=args.env_file,
        symbol=args.symbol,
    )


if __name__ == "__main__":
    raise SystemExit(main())
