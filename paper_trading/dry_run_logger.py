"""
paper_trading/dry_run_logger.py
================================
Phase 2 dry-run signal logger, per docs/ALPACA_PAPER_TRADING_GATE_SPEC.md
Section 11 and the "Phase 2 -- Dry-run signal logger" definition in
Section 12.

This module NEVER connects to a broker, NEVER submits an order (paper or
live), and NEVER reads/writes any credential or .env file. It only:
  1. Validates that the requested strategy/asset/params are on the
     hardcoded allowlist (paper_trading/allowlist.py).
  2. Computes the RSI(14) value for the latest bar using the existing,
     unmodified indicator function (edge_hunting/indicators.py::rsi).
  3. Applies the exact approved entry/exit rule (RSI < 30 -> BUY /
     enter long; RSI > 70 AND a position is assumed open -> EXIT;
     otherwise HOLD) -- this mirrors, but does not alter,
     edge_hunting/strategy_library.py::strategy_rsi_revert's own
     oversold/overbought logic.
  4. Runs the Phase 2 risk-gate placeholders (paper_trading/risk_gates.py).
  5. Writes one structured JSON-lines record per evaluation to
     reports/paper_trading/, with an explicit "order_submitted": false
     and a human-readable note that no order was submitted.

Strategy parameters are NOT tunable at the call site beyond what the
allowlist accepts -- passing any other window/oversold/overbought value
for EEM rsi_revert raises NotAllowedError.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge_hunting import indicators as ind
from paper_trading.allowlist import NotAllowedError, is_allowed
from paper_trading.risk_gates import RiskGateStatus, evaluate_all_gates

DEFAULT_REPORT_DIR = ROOT / "reports" / "paper_trading"
DEFAULT_REPORT_FILE = "eem_rsi_dry_run.jsonl"

APPROVED_STRATEGY = "rsi_revert"
APPROVED_ASSET = "EEM"
APPROVED_PARAMS = {"window": 14, "oversold": 30, "overbought": 70}

SIGNAL_BUY = "BUY"
SIGNAL_EXIT = "EXIT"
SIGNAL_HOLD = "HOLD"


@dataclass
class DryRunResult:
    """One evaluation's full outcome. Never contains an executed order."""
    timestamp: str
    symbol: str
    latest_price: float
    rsi_value: float | None
    position_state_assumption: str          # "flat" | "long"
    signal: str                              # BUY | EXIT | HOLD
    reason: str
    risk_gate_passed: bool
    risk_gate_checks: dict
    final_decision: str                      # human-readable summary
    order_submitted: bool = False            # ALWAYS False in Phase 2
    note: str = "DRY RUN: no order was submitted (Phase 2, no broker connection)."

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "latest_price": self.latest_price,
            "rsi_value": self.rsi_value,
            "position_state_assumption": self.position_state_assumption,
            "signal": self.signal,
            "reason": self.reason,
            "risk_gate_passed": self.risk_gate_passed,
            "risk_gate_checks": {
                name: {"passed": ok, "detail": detail}
                for name, (ok, detail) in self.risk_gate_checks.items()
            },
            "final_decision": self.final_decision,
            "order_submitted": self.order_submitted,
            "note": self.note,
        }


def compute_rsi_signal(
    close_prices: pd.Series,
    params: dict,
    position_open: bool,
) -> tuple[float | None, str, str]:
    """Computes the RSI value for the latest bar and applies the
    approved entry/exit rule. Returns (rsi_value, signal, reason).

    Rule (matches edge_hunting/strategy_library.py::strategy_rsi_revert's
    oversold/overbought logic, applied causally to the latest bar only):
      - RSI < oversold                        -> BUY (enter long)
      - RSI > overbought AND position is open -> EXIT
      - otherwise                              -> HOLD
    """
    window = params["window"]
    oversold = params["oversold"]
    overbought = params["overbought"]

    rsi_series = ind.rsi(close_prices, window)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return None, SIGNAL_HOLD, "RSI could not be computed (insufficient/invalid data)"

    rsi_value = float(rsi_series.iloc[-1])

    if rsi_value < oversold:
        return rsi_value, SIGNAL_BUY, f"RSI {rsi_value:.2f} < oversold threshold {oversold}"
    if rsi_value > overbought and position_open:
        return rsi_value, SIGNAL_EXIT, (
            f"RSI {rsi_value:.2f} > overbought threshold {overbought} "
            f"and position assumed open"
        )
    if rsi_value > overbought and not position_open:
        return rsi_value, SIGNAL_HOLD, (
            f"RSI {rsi_value:.2f} > overbought threshold {overbought} "
            f"but no position assumed open (no exit possible)"
        )
    return rsi_value, SIGNAL_HOLD, (
        f"RSI {rsi_value:.2f} between oversold {oversold} and overbought {overbought}"
    )


def evaluate_dry_run(
    *,
    symbol: str,
    strategy: str,
    params: dict,
    close_prices: pd.Series,
    position_open: bool = False,
    kill_switch_engaged: bool = False,
    is_market_open: bool | None = True,
    daily_pnl_pct: float | None = None,
    drawdown_pct: float | None = None,
    now: datetime | None = None,
) -> DryRunResult:
    """The single entry point for one dry-run evaluation cycle.

    Raises NotAllowedError if (strategy, symbol, params) is not the
    exact approved EEM rsi_revert(14,30/70) configuration -- this is a
    hard stop, never a soft warning, per spec Section 1.

    Never submits an order. Always returns a DryRunResult with
    order_submitted=False.
    """
    if not is_allowed(strategy, symbol, params):
        raise NotAllowedError(
            f"strategy/asset/params not on the approved allowlist: "
            f"strategy={strategy!r}, symbol={symbol!r}, params={params!r}. "
            f"Only {APPROVED_STRATEGY} on {APPROVED_ASSET} with "
            f"{APPROVED_PARAMS} is approved for paper-trading dry-run."
        )

    now = now or datetime.now(timezone.utc)
    latest_price = float(close_prices.iloc[-1]) if len(close_prices) else float("nan")
    bar_count = len(close_prices)
    latest_bar_timestamp = None
    if len(close_prices) and isinstance(close_prices.index, pd.DatetimeIndex):
        ts = close_prices.index[-1]
        latest_bar_timestamp = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else None

    rsi_value, raw_signal, reason = compute_rsi_signal(close_prices, params, position_open)

    # Position-size placeholder: only relevant if the raw signal is BUY.
    # Phase 2 never actually sizes or opens a position; this uses the
    # hardcoded max cap itself as the hypothetical target notional so
    # the gate is meaningfully exercised even without a real account.
    from paper_trading.risk_gates import MAX_POSITION_USD
    target_notional = MAX_POSITION_USD if raw_signal == SIGNAL_BUY else 0.0

    gate_status: RiskGateStatus = evaluate_all_gates(
        target_notional=target_notional,
        daily_pnl_pct=daily_pnl_pct,
        drawdown_pct=drawdown_pct,
        latest_bar_timestamp=latest_bar_timestamp,
        bar_count=bar_count,
        is_market_open=is_market_open,
        kill_switch_engaged=kill_switch_engaged,
        now=now,
    )

    final_signal = raw_signal
    if not gate_status.passed and raw_signal != SIGNAL_HOLD:
        final_decision = (
            f"{raw_signal} signal detected but BLOCKED by risk gate(s): "
            f"{'; '.join(gate_status.blocked_reasons())}"
        )
        final_signal = SIGNAL_HOLD  # never act if any gate fails
    elif raw_signal == SIGNAL_HOLD:
        final_decision = f"HOLD: {reason}"
    else:
        final_decision = f"{raw_signal} signal approved by all risk gates (dry run only, no order sent)"

    position_state_assumption = "long" if position_open else "flat"

    return DryRunResult(
        timestamp=now.isoformat(),
        symbol=symbol,
        latest_price=latest_price,
        rsi_value=rsi_value,
        position_state_assumption=position_state_assumption,
        signal=final_signal,
        reason=reason,
        risk_gate_passed=gate_status.passed,
        risk_gate_checks=gate_status.checks,
        final_decision=final_decision,
        order_submitted=False,
    )


def log_dry_run_result(
    result: DryRunResult,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    report_file: str = DEFAULT_REPORT_FILE,
) -> Path:
    """Append one JSON-lines record to the dry-run report file. Creates
    the directory if needed. Never touches any broker or credential."""
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / report_file
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result.to_dict(), default=str) + "\n")
    return path


def run_dry_run_cycle(
    *,
    symbol: str = APPROVED_ASSET,
    strategy: str = APPROVED_STRATEGY,
    params: dict | None = None,
    close_prices: pd.Series,
    position_open: bool = False,
    kill_switch_engaged: bool = False,
    is_market_open: bool | None = True,
    daily_pnl_pct: float | None = None,
    drawdown_pct: float | None = None,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    report_file: str = DEFAULT_REPORT_FILE,
) -> DryRunResult:
    """Convenience wrapper: evaluate + log in one call. This is the
    function an external scheduler (e.g. a daily cron trigger) would
    call once per day; it still never submits an order."""
    params = params or dict(APPROVED_PARAMS)
    result = evaluate_dry_run(
        symbol=symbol,
        strategy=strategy,
        params=params,
        close_prices=close_prices,
        position_open=position_open,
        kill_switch_engaged=kill_switch_engaged,
        is_market_open=is_market_open,
        daily_pnl_pct=daily_pnl_pct,
        drawdown_pct=drawdown_pct,
    )
    log_dry_run_result(result, report_dir=report_dir, report_file=report_file)
    return result
