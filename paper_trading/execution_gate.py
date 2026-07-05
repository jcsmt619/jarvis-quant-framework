"""Paper execution gate.

Phase 4C safety layer only.

This module decides whether a paper order intent would be allowed to reach
a future execution layer.

It does not submit orders.
It does not connect to a broker.
It does not enable live trading.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from paper_trading.alpaca_config import AlpacaPaperConfig, validate_alpaca_paper_config
from paper_trading.order_intent import PaperOrderIntent


@dataclass(frozen=True)
class PaperExecutionGateResult:
    """Local-only execution gate result."""

    timestamp_utc: str
    symbol: str
    strategy: str
    intent_action: str
    requested_signal: str
    estimated_quantity: int
    estimated_notional: float
    execution_allowed: bool
    execution_status: str
    blocked_reasons: list[str]
    order_submission_enabled: bool = False
    live_trading_enabled: bool = False
    broker_call_performed: bool = False
    order_submitted: bool = False
    order_id: str | None = None
    note: str = (
        "EXECUTION GATE ONLY: no paper order, live order, or broker execution was submitted."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_paper_execution_gate(
    *,
    config: AlpacaPaperConfig,
    intent: PaperOrderIntent,
    order_submission_enabled: bool = False,
) -> PaperExecutionGateResult:
    """Evaluate whether an intent would be allowed to reach execution.

    This function deliberately performs zero broker calls.
    """
    validate_alpaca_paper_config(config)

    blocked_reasons: list[str] = []

    if intent.live_trading_enabled:
        blocked_reasons.append("intent live_trading_enabled must be False")

    if intent.broker_call_performed:
        blocked_reasons.append("intent already reports broker_call_performed=True")

    if intent.order_submission_enabled:
        blocked_reasons.append("intent order_submission_enabled must be False in gate phase")

    if intent.intent_action == "BLOCKED":
        blocked_reasons.append("intent action is BLOCKED")

    if intent.blocked_reasons:
        blocked_reasons.extend(intent.blocked_reasons)

    if intent.intent_action not in {"BUY", "EXIT", "HOLD", "BLOCKED"}:
        blocked_reasons.append(f"unsupported intent action: {intent.intent_action!r}")

    if intent.intent_action in {"BUY", "EXIT"}:
        if intent.estimated_quantity <= 0:
            blocked_reasons.append("estimated quantity must be positive for BUY/EXIT")

        if intent.estimated_notional <= 0:
            blocked_reasons.append("estimated notional must be positive for BUY/EXIT")

    if intent.intent_action == "HOLD":
        if intent.estimated_quantity != 0:
            blocked_reasons.append("HOLD intent must have zero estimated quantity")

        if intent.estimated_notional != 0:
            blocked_reasons.append("HOLD intent must have zero estimated notional")

    if not order_submission_enabled:
        blocked_reasons.append("order submission is disabled")

    execution_allowed = len(blocked_reasons) == 0

    return PaperExecutionGateResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        estimated_quantity=intent.estimated_quantity,
        estimated_notional=intent.estimated_notional,
        execution_allowed=execution_allowed,
        execution_status="ALLOWED" if execution_allowed else "BLOCKED",
        blocked_reasons=blocked_reasons,
        order_submission_enabled=False,
        live_trading_enabled=False,
        broker_call_performed=False,
        order_submitted=False,
        order_id=None,
    )


def write_paper_execution_gate_result(
    result: PaperExecutionGateResult,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write local execution gate result to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"paper_execution_gate_{stamp}.json"

    file_path.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
