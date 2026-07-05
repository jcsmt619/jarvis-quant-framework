"""Local-only paper trading pipeline report.

Phase 4D safety layer.

This script runs the complete local paper-trading decision pipeline:

1. Load Alpaca paper-only config
2. Load EEM close prices
3. Build preflight report
4. Build paper order intent
5. Evaluate execution gate
6. Write a combined pipeline summary

It submits zero orders.
It performs zero execution broker calls.
It does not enable live trading.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.execution_gate import (
    evaluate_paper_execution_gate,
    write_paper_execution_gate_result,
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


def write_pipeline_summary(
    *,
    preflight_report,
    intent,
    execution_gate,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write a combined local-only pipeline summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"paper_pipeline_summary_{stamp}.json"

    summary = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "symbol": intent.symbol,
        "strategy": intent.strategy,
        "preflight": preflight_report.as_dict(),
        "intent": intent.as_dict(),
        "execution_gate": execution_gate.as_dict(),
        "broker_call_performed": False,
        "order_submission_enabled": False,
        "live_trading_enabled": False,
        "order_submitted": False,
        "note": (
            "PIPELINE REPORT ONLY: no paper order, live order, or broker execution "
            "was submitted."
        ),
    }

    file_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path


def run_pipeline_report(
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

        execution_gate = evaluate_paper_execution_gate(
            config=config,
            intent=intent,
            order_submission_enabled=False,
        )
        execution_gate_path = write_paper_execution_gate_result(execution_gate)

        pipeline_summary_path = write_pipeline_summary(
            preflight_report=preflight_report,
            intent=intent,
            execution_gate=execution_gate,
        )

    except (AlpacaConfigError, ValueError) as exc:
        print("PAPER PIPELINE REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive local script wrapper
        print("PAPER PIPELINE REPORT: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("PAPER PIPELINE REPORT: PASS")
    print(f"Symbol: {intent.symbol}")
    print(f"Strategy: {intent.strategy}")
    print(f"Latest price: {intent.latest_price}")
    print(f"Preflight ready: {preflight_report.ready_for_paper_order_phase}")
    print(f"Dry-run signal: {preflight_report.dry_run_signal}")
    print(f"Intent action: {intent.intent_action}")
    print(f"Estimated quantity: {intent.estimated_quantity}")
    print(f"Estimated notional: {intent.estimated_notional}")
    print(f"Execution gate status: {execution_gate.execution_status}")
    print(f"Execution allowed: {execution_gate.execution_allowed}")
    print(f"Execution blocked reasons: {execution_gate.blocked_reasons}")
    print("BROKER CALL PERFORMED: false")
    print("ORDER SUBMISSION: DISABLED")
    print("LIVE TRADING: DISABLED")
    print("ORDER SUBMITTED: false")
    print(f"Preflight report written to: {preflight_path}")
    print(f"Intent report written to: {intent_path}")
    print(f"Execution gate report written to: {execution_gate_path}")
    print(f"Pipeline summary written to: {pipeline_summary_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full local paper trading pipeline report with zero orders."
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

    args = parser.parse_args()
    return run_pipeline_report(
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
