"""Paper trading preflight control report.

Phase 3C safety layer only.

This module combines:
- Alpaca paper account snapshot
- approved EEM RSI dry-run signal
- final preflight READY/BLOCKED decision

It does not submit orders.
It does not implement broker execution.
It does not enable live trading.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.alpaca_snapshot import (
    AlpacaPaperAccountSnapshot,
    collect_alpaca_paper_account_snapshot,
)
from paper_trading.dry_run_logger import DryRunResult, run_dry_run_cycle


@dataclass(frozen=True)
class PaperPreflightReport:
    """Safe paper-trading preflight report with no secrets."""

    timestamp_utc: str
    symbol: str
    strategy: str
    account_status: str | None
    cash: str | None
    buying_power: str | None
    portfolio_value: str | None
    positions_count: int
    open_orders_count: int
    dry_run_signal: str
    dry_run_reason: str
    dry_run_final_decision: str
    dry_run_order_submitted: bool
    risk_gate_passed: bool
    risk_gate_checks: dict
    ready_for_paper_order_phase: bool
    blocked_reasons: list[str]
    order_submission_enabled: bool = False
    live_trading_enabled: bool = False
    note: str = (
        "PREFLIGHT ONLY: no paper order, live order, or broker execution was submitted."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _build_blocked_reasons(
    *,
    snapshot: AlpacaPaperAccountSnapshot,
    dry_run: DryRunResult,
) -> list[str]:
    reasons: list[str] = []

    if snapshot.account_status != "ACTIVE":
        reasons.append(f"paper account status is {snapshot.account_status!r}, not ACTIVE")

    if snapshot.trading_blocked:
        reasons.append("paper account trading_blocked is True")

    if snapshot.account_blocked:
        reasons.append("paper account account_blocked is True")

    if not dry_run.risk_gate_passed:
        reasons.append("dry-run risk gates did not pass")

    if dry_run.order_submitted:
        reasons.append("dry-run unexpectedly reported order_submitted=True")

    if dry_run.final_decision.upper().startswith("BLOCK"):
        reasons.append(f"dry-run final decision is {dry_run.final_decision!r}")

    return reasons


def build_paper_preflight_report(
    *,
    config: AlpacaPaperConfig,
    close_prices: pd.Series,
    position_open: bool = False,
    kill_switch_engaged: bool = False,
    is_market_open: bool | None = True,
    daily_pnl_pct: float | None = None,
    drawdown_pct: float | None = None,
    client_factory: Callable[..., object] | None = None,
) -> PaperPreflightReport:
    """Build a read-only preflight report.

    Allowed:
    - read Alpaca paper account state
    - evaluate approved EEM RSI dry-run decision

    Forbidden:
    - submitting orders
    - canceling orders
    - live trading
    """
    snapshot = collect_alpaca_paper_account_snapshot(
        config,
        client_factory=client_factory,
    )

    dry_run = run_dry_run_cycle(
        symbol="EEM",
        strategy="rsi_revert",
        params=None,
        close_prices=close_prices,
        position_open=position_open,
        kill_switch_engaged=kill_switch_engaged,
        is_market_open=is_market_open,
        daily_pnl_pct=daily_pnl_pct,
        drawdown_pct=drawdown_pct,
    )

    blocked_reasons = _build_blocked_reasons(snapshot=snapshot, dry_run=dry_run)
    ready = len(blocked_reasons) == 0

    return PaperPreflightReport(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol="EEM",
        strategy="rsi_revert",
        account_status=snapshot.account_status,
        cash=snapshot.cash,
        buying_power=snapshot.buying_power,
        portfolio_value=snapshot.portfolio_value,
        positions_count=snapshot.positions_count,
        open_orders_count=snapshot.open_orders_count,
        dry_run_signal=dry_run.signal,
        dry_run_reason=dry_run.reason,
        dry_run_final_decision=dry_run.final_decision,
        dry_run_order_submitted=dry_run.order_submitted,
        risk_gate_passed=dry_run.risk_gate_passed,
        risk_gate_checks=dry_run.risk_gate_checks,
        ready_for_paper_order_phase=ready,
        blocked_reasons=blocked_reasons,
        order_submission_enabled=False,
        live_trading_enabled=False,
    )


def write_paper_preflight_report(
    report: PaperPreflightReport,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write preflight report to a local JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"paper_preflight_report_{stamp}.json"

    file_path.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
