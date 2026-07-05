"""Paper order intent generation.

Phase 4A safety layer only.

This module converts a preflight report into a local intent record:
- BUY intent
- EXIT intent
- HOLD intent
- BLOCKED intent

It does not submit orders.
It does not connect to a broker.
It does not implement execution.
It does not enable live trading.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_MAX_POSITION_NOTIONAL = 10_000.0
DEFAULT_MAX_EQUITY_FRACTION = 0.10


@dataclass(frozen=True)
class PaperOrderIntent:
    """Local-only paper order intent with no broker execution."""

    timestamp_utc: str
    symbol: str
    strategy: str
    requested_signal: str
    intent_action: str
    estimated_quantity: int
    estimated_notional: float
    latest_price: float | None
    preflight_ready: bool
    blocked_reasons: list[str]
    reason: str
    order_submission_enabled: bool = False
    live_trading_enabled: bool = False
    broker_call_performed: bool = False
    note: str = (
        "INTENT ONLY: no paper order, live order, or broker execution was submitted."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_float(value: object) -> float | None:
    if value is None:
        return None

    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _estimate_buy_quantity(
    *,
    price: float,
    cash: float | None,
    portfolio_value: float | None,
    max_position_notional: float,
    max_equity_fraction: float,
) -> tuple[int, float, list[str]]:
    blocked: list[str] = []

    if price <= 0:
        return 0, 0.0, ["latest price must be positive"]

    if cash is None or cash <= 0:
        return 0, 0.0, ["cash is missing or non-positive"]

    equity_cap = (
        portfolio_value * max_equity_fraction
        if portfolio_value is not None and portfolio_value > 0
        else max_position_notional
    )

    target_notional = min(cash, max_position_notional, equity_cap)

    if target_notional <= 0:
        return 0, 0.0, ["target notional is non-positive"]

    quantity = int(target_notional // price)

    if quantity <= 0:
        return 0, 0.0, ["estimated quantity is zero"]

    return quantity, round(quantity * price, 2), blocked


def build_paper_order_intent(
    *,
    preflight_report,
    latest_price: float | None,
    current_position_quantity: int = 0,
    max_position_notional: float = DEFAULT_MAX_POSITION_NOTIONAL,
    max_equity_fraction: float = DEFAULT_MAX_EQUITY_FRACTION,
) -> PaperOrderIntent:
    """Build a local-only paper intent from a preflight report.

    This function performs zero broker calls.
    """
    signal = str(preflight_report.dry_run_signal).upper()
    blocked_reasons = list(preflight_report.blocked_reasons)

    if not preflight_report.ready_for_paper_order_phase:
        return PaperOrderIntent(
            timestamp_utc=datetime.now(UTC).isoformat(),
            symbol=preflight_report.symbol,
            strategy=preflight_report.strategy,
            requested_signal=signal,
            intent_action="BLOCKED",
            estimated_quantity=0,
            estimated_notional=0.0,
            latest_price=latest_price,
            preflight_ready=False,
            blocked_reasons=blocked_reasons or ["preflight report is not ready"],
            reason="Preflight blocked paper intent generation.",
        )

    if latest_price is None:
        return PaperOrderIntent(
            timestamp_utc=datetime.now(UTC).isoformat(),
            symbol=preflight_report.symbol,
            strategy=preflight_report.strategy,
            requested_signal=signal,
            intent_action="BLOCKED",
            estimated_quantity=0,
            estimated_notional=0.0,
            latest_price=None,
            preflight_ready=True,
            blocked_reasons=["latest price is required"],
            reason="Cannot estimate quantity without latest price.",
        )

    if signal == "BUY":
        cash = _safe_float(preflight_report.cash)
        portfolio_value = _safe_float(preflight_report.portfolio_value)

        quantity, notional, buy_blocks = _estimate_buy_quantity(
            price=float(latest_price),
            cash=cash,
            portfolio_value=portfolio_value,
            max_position_notional=max_position_notional,
            max_equity_fraction=max_equity_fraction,
        )

        if buy_blocks:
            return PaperOrderIntent(
                timestamp_utc=datetime.now(UTC).isoformat(),
                symbol=preflight_report.symbol,
                strategy=preflight_report.strategy,
                requested_signal=signal,
                intent_action="BLOCKED",
                estimated_quantity=0,
                estimated_notional=0.0,
                latest_price=float(latest_price),
                preflight_ready=True,
                blocked_reasons=buy_blocks,
                reason="BUY intent blocked by sizing checks.",
            )

        return PaperOrderIntent(
            timestamp_utc=datetime.now(UTC).isoformat(),
            symbol=preflight_report.symbol,
            strategy=preflight_report.strategy,
            requested_signal=signal,
            intent_action="BUY",
            estimated_quantity=quantity,
            estimated_notional=notional,
            latest_price=float(latest_price),
            preflight_ready=True,
            blocked_reasons=[],
            reason=preflight_report.dry_run_final_decision,
        )

    if signal == "EXIT":
        if current_position_quantity <= 0:
            return PaperOrderIntent(
                timestamp_utc=datetime.now(UTC).isoformat(),
                symbol=preflight_report.symbol,
                strategy=preflight_report.strategy,
                requested_signal=signal,
                intent_action="HOLD",
                estimated_quantity=0,
                estimated_notional=0.0,
                latest_price=float(latest_price),
                preflight_ready=True,
                blocked_reasons=[],
                reason="EXIT signal received, but no open paper position quantity was supplied.",
            )

        return PaperOrderIntent(
            timestamp_utc=datetime.now(UTC).isoformat(),
            symbol=preflight_report.symbol,
            strategy=preflight_report.strategy,
            requested_signal=signal,
            intent_action="EXIT",
            estimated_quantity=int(current_position_quantity),
            estimated_notional=round(int(current_position_quantity) * float(latest_price), 2),
            latest_price=float(latest_price),
            preflight_ready=True,
            blocked_reasons=[],
            reason=preflight_report.dry_run_final_decision,
        )

    return PaperOrderIntent(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=preflight_report.symbol,
        strategy=preflight_report.strategy,
        requested_signal=signal,
        intent_action="HOLD",
        estimated_quantity=0,
        estimated_notional=0.0,
        latest_price=float(latest_price),
        preflight_ready=True,
        blocked_reasons=[],
        reason=preflight_report.dry_run_final_decision,
    )


def write_paper_order_intent(
    intent: PaperOrderIntent,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write local paper intent to a JSON report file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"paper_order_intent_{stamp}.json"

    file_path.write_text(
        json.dumps(intent.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
