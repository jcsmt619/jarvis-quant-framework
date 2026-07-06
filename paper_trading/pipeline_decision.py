"""Market-aware fake pipeline decision classification.

Phase 5D safety layer.

This module converts lower-level pipeline outputs into a clear final decision:
- WAIT_MARKET_CLOSED
- NO_ACTION
- FAKE_EXECUTED
- BLOCKED_PREFLIGHT
- BLOCKED_EXECUTION_GATE
- BLOCKED_FAKE_EXECUTION

It submits zero orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FakePipelineDecision:
    timestamp_utc: str
    symbol: str
    strategy: str
    decision_status: str
    actionable: bool
    reason: str
    market_session_open: bool
    market_session_reason: str
    preflight_ready: bool
    dry_run_signal: str
    intent_action: str
    execution_gate_status: str
    fake_execution_status: str
    fake_execution_attempted: bool
    real_broker_client_used: bool
    real_paper_order_submitted: bool
    live_trading_enabled: bool
    note: str = (
        "FINAL PIPELINE DECISION ONLY: no real paper order, live order, "
        "or real broker execution was submitted."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_fake_pipeline_decision(
    *,
    market_session,
    preflight_report,
    intent,
    execution_gate,
    fake_result,
) -> FakePipelineDecision:
    """Classify final fake pipeline decision in market-aware language."""
    if not market_session.is_market_open:
        decision_status = "WAIT_MARKET_CLOSED"
        actionable = False
        reason = market_session.reason
    elif not preflight_report.ready_for_paper_order_phase:
        decision_status = "BLOCKED_PREFLIGHT"
        actionable = False
        reason = "; ".join(preflight_report.blocked_reasons) or "preflight blocked"
    elif intent.intent_action == "HOLD":
        decision_status = "NO_ACTION"
        actionable = False
        reason = intent.reason
    elif not execution_gate.execution_allowed:
        decision_status = "BLOCKED_EXECUTION_GATE"
        actionable = False
        reason = "; ".join(execution_gate.blocked_reasons) or "execution gate blocked"
    elif fake_result.execution_status == "FAKE_SUBMITTED":
        decision_status = "FAKE_EXECUTED"
        actionable = True
        reason = "fake client accepted simulated order path"
    elif fake_result.execution_status == "NO_ACTION":
        decision_status = "NO_ACTION"
        actionable = False
        reason = fake_result.note
    elif fake_result.execution_status == "BLOCKED":
        decision_status = "BLOCKED_FAKE_EXECUTION"
        actionable = False
        reason = "; ".join(fake_result.blocked_reasons) or "fake execution blocked"
    else:
        decision_status = "BLOCKED_UNKNOWN"
        actionable = False
        reason = f"unrecognized fake execution status: {fake_result.execution_status!r}"

    return FakePipelineDecision(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=intent.symbol,
        strategy=intent.strategy,
        decision_status=decision_status,
        actionable=actionable,
        reason=reason,
        market_session_open=market_session.is_market_open,
        market_session_reason=market_session.reason,
        preflight_ready=preflight_report.ready_for_paper_order_phase,
        dry_run_signal=preflight_report.dry_run_signal,
        intent_action=intent.intent_action,
        execution_gate_status=execution_gate.execution_status,
        fake_execution_status=fake_result.execution_status,
        fake_execution_attempted=fake_result.execution_attempted,
        real_broker_client_used=fake_result.real_broker_client_used,
        real_paper_order_submitted=False,
        live_trading_enabled=False,
    )


def write_fake_pipeline_decision(
    decision: FakePipelineDecision,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write final fake pipeline decision report to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"fake_pipeline_decision_{stamp}.json"

    file_path.write_text(
        json.dumps(decision.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
