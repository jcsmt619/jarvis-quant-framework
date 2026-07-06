"""Full fake-execution paper pipeline.

Phase 5B safety layer.

This script runs:

1. Alpaca paper-only config validation
2. EEM close-price loading
3. Preflight report
4. Paper order intent
5. Execution gate
6. Fake-client execution

It submits zero real paper orders.
It submits zero live orders.
It never creates a real Alpaca trading client.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.execution_gate import (
    evaluate_paper_execution_gate,
    write_paper_execution_gate_result,
)
from paper_trading.fake_executor import (
    execute_with_fake_paper_client,
    write_fake_paper_execution_result,
)
from paper_trading.order_intent import (
    build_paper_order_intent,
    write_paper_order_intent,
)
from paper_trading.preflight import (
    build_paper_preflight_report,
    write_paper_preflight_report,
)
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_paper_order_intent_report import _latest_price_from_close_prices
from scripts.run_paper_preflight_report import _load_close_prices_csv


class LocalFakeOrder:
    def __init__(self, order_id: str):
        self.id = order_id


class LocalFakePaperClient:
    """Local fake client that records would-be orders."""

    def __init__(self):
        self.submitted_orders = []

    def submit_order(self, **kwargs):
        self.submitted_orders.append(kwargs)
        return LocalFakeOrder(order_id="local_fake_order_001")


def run_fake_execution_pipeline(
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
    fake_execution_enabled: bool = True,
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

        execution_gate = evaluate_paper_execution_gate(
            config=config,
            intent=intent,
            order_submission_enabled=True,
        )
        execution_gate_path = write_paper_execution_gate_result(execution_gate)

        fake_client = LocalFakePaperClient()
        fake_result = execute_with_fake_paper_client(
            config=config,
            intent=intent,
            execution_gate=execution_gate,
            fake_client_factory=lambda: fake_client,
            fake_execution_enabled=fake_execution_enabled,
        )
        fake_result_path = write_fake_paper_execution_result(fake_result)

    except (AlpacaConfigError, ValueError) as exc:
        print("FAKE PAPER EXECUTION PIPELINE: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        print("FAKE PAPER EXECUTION PIPELINE: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("FAKE PAPER EXECUTION PIPELINE: PASS")
    print(f"Symbol: {intent.symbol}")
    print(f"Strategy: {intent.strategy}")
    print(f"Latest price: {intent.latest_price}")
    print(f"Dry-run signal: {preflight_report.dry_run_signal}")
    print(f"Intent action: {intent.intent_action}")
    print(f"Estimated quantity: {intent.estimated_quantity}")
    print(f"Estimated notional: {intent.estimated_notional}")
    print(f"Execution gate status: {execution_gate.execution_status}")
    print(f"Execution allowed: {execution_gate.execution_allowed}")
    print(f"Fake execution status: {fake_result.execution_status}")
    print(f"Fake execution attempted: {fake_result.execution_attempted}")
    print(f"Fake submitted side: {fake_result.submitted_side}")
    print(f"Fake submitted quantity: {fake_result.submitted_quantity}")
    print(f"Fake order id: {fake_result.fake_order_id}")
    print(f"Fake blocked reasons: {fake_result.blocked_reasons}")
    print("FAKE CLIENT USED: true")
    print("REAL BROKER CLIENT USED: false")
    print("REAL PAPER ORDER SUBMITTED: false")
    print("LIVE TRADING: DISABLED")
    print(f"Preflight report written to: {preflight_path}")
    print(f"Intent report written to: {intent_path}")
    print(f"Execution gate report written to: {execution_gate_path}")
    print(f"Fake execution report written to: {fake_result_path}")

    return 0 if fake_result.execution_status in {"FAKE_SUBMITTED", "NO_ACTION"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full fake-client paper execution pipeline with zero real orders."
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
    parser.add_argument("--disable-fake-execution", action="store_true")

    args = parser.parse_args()
    return run_fake_execution_pipeline(
        env_file=args.env_file,
        close_csv=args.close_csv,
        price_column=args.price_column,
        date_column=args.date_column,
        position_open=args.position_open,
        current_position_quantity=args.current_position_quantity,
        kill_switch_engaged=args.kill_switch,
        max_position_notional=args.max_position_notional,
        max_equity_fraction=args.max_equity_fraction,
        fake_execution_enabled=not args.disable_fake_execution,
    )


if __name__ == "__main__":
    raise SystemExit(main())
