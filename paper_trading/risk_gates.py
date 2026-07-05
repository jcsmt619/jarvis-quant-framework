"""
paper_trading/risk_gates.py
===========================
Basic risk-gate checks for the Phase 2 dry-run signal logger, per
docs/ALPACA_PAPER_TRADING_GATE_SPEC.md Sections 3-8, 10.

Phase 2 has no broker connection and never submits an order (spec
Phase 2 definition), so these gates cannot yet observe real fills, real
account equity, or a real market clock. They are implemented here as
honest PLACEHOLDERS that:
  - accept externally-supplied state (equity, daily P&L, drawdown, a
    market-open flag, a kill-switch flag) rather than fabricating it,
  - default to the SAFE (blocking) side whenever required state is
    missing, and
  - are structured so Phase 3+ can supply real values from the broker
    without changing this module's interface.

Nothing here places an order. This module only decides whether a
hypothetical order WOULD be allowed to proceed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Hardcoded limits, per docs/ALPACA_PAPER_TRADING_GATE_SPEC.md
# ---------------------------------------------------------------------------
MAX_POSITION_USD = 5_000.0          # Section 3
MAX_DAILY_LOSS_PCT = 0.01           # Section 4 (placeholder -- no real P&L yet)
MAX_TOTAL_DRAWDOWN_PCT = 0.05       # Section 5 (placeholder -- no real equity yet)
MAX_STALE_BARS_TRADING_DAYS = 1.0   # Section 7
MIN_BARS_REQUIRED = 15              # RSI window (14) + 1 safety margin, Section 7


@dataclass
class RiskGateStatus:
    """Aggregated result of every gate check for one dry-run cycle."""
    passed: bool
    checks: dict = field(default_factory=dict)     # name -> (bool, reason)
    kill_switch_engaged: bool = False

    def blocked_reasons(self) -> list[str]:
        return [reason for ok, reason in self.checks.values() if not ok]


def check_max_position_size(target_notional: float) -> tuple[bool, str]:
    """Section 3: max $5,000 notional per EEM position (placeholder cap;
    no real position is ever opened in Phase 2)."""
    if target_notional > MAX_POSITION_USD:
        return False, (
            f"target notional ${target_notional:,.2f} exceeds max "
            f"position size ${MAX_POSITION_USD:,.2f}"
        )
    return True, "within max position size"


def check_max_daily_loss(daily_pnl_pct: float | None) -> tuple[bool, str]:
    """Section 4 placeholder. daily_pnl_pct is a fraction (e.g. -0.02 =
    -2%). No broker connection exists yet in Phase 2, so this always
    receives None from the dry-run logger and safely passes with an
    explicit 'not yet measurable' note -- it does not fabricate a P&L
    number. Phase 3+ must supply a real value once account equity is
    available."""
    if daily_pnl_pct is None:
        return True, "daily P&L not available in Phase 2 (no broker connection); placeholder pass"
    if daily_pnl_pct < -MAX_DAILY_LOSS_PCT:
        return False, f"daily loss {daily_pnl_pct:.2%} exceeds max {MAX_DAILY_LOSS_PCT:.0%}"
    return True, "within max daily loss"


def check_max_total_drawdown(drawdown_pct: float | None) -> tuple[bool, str]:
    """Section 5 placeholder. Same rationale as check_max_daily_loss --
    no real equity curve exists without a broker connection."""
    if drawdown_pct is None:
        return True, "drawdown not available in Phase 2 (no broker connection); placeholder pass"
    if drawdown_pct > MAX_TOTAL_DRAWDOWN_PCT:
        return False, f"drawdown {drawdown_pct:.2%} exceeds max {MAX_TOTAL_DRAWDOWN_PCT:.0%}"
    return True, "within max total drawdown"


def check_stale_data(latest_bar_timestamp: datetime | None, now: datetime | None = None) -> tuple[bool, str]:
    """Section 7: refuse to evaluate a signal on data older than
    ~1 trading day. Defaults to the SAFE (blocking) side if the
    timestamp is missing entirely."""
    if latest_bar_timestamp is None:
        return False, "no bar timestamp supplied; treated as stale (fail-safe)"
    now = now or datetime.now(timezone.utc)
    if latest_bar_timestamp.tzinfo is None:
        latest_bar_timestamp = latest_bar_timestamp.replace(tzinfo=timezone.utc)
    age_days = (now - latest_bar_timestamp).total_seconds() / 86400.0
    if age_days > MAX_STALE_BARS_TRADING_DAYS + 3.0:  # + weekend/holiday buffer
        return False, f"latest bar is {age_days:.1f} days old; exceeds staleness threshold"
    return True, f"latest bar age {age_days:.1f} days; within threshold"


def check_sufficient_bars(bar_count: int) -> tuple[bool, str]:
    """Section 7 secondary check: RSI(14) needs at least 14 bars plus a
    safety margin."""
    if bar_count < MIN_BARS_REQUIRED:
        return False, f"only {bar_count} bars available; need >= {MIN_BARS_REQUIRED}"
    return True, f"{bar_count} bars available; sufficient"


def check_market_hours(is_market_open: bool | None) -> tuple[bool, str]:
    """Section 8 placeholder. Phase 2 has no broker clock, so this must
    be supplied externally (e.g. a caller-provided assumption for
    historical/offline dry runs) or defaults to the SAFE (blocking)
    side when not supplied, exactly like the other placeholders."""
    if is_market_open is None:
        return False, "market-open state not supplied; treated as closed (fail-safe placeholder)"
    if not is_market_open:
        return False, "market is closed"
    return True, "market is open"


def check_kill_switch(kill_switch_engaged: bool) -> tuple[bool, str]:
    """Section 10: kill switch has absolute veto. True means BLOCKED."""
    if kill_switch_engaged:
        return False, "kill switch engaged: all actions blocked"
    return True, "kill switch not engaged"


def evaluate_all_gates(
    *,
    target_notional: float,
    daily_pnl_pct: float | None = None,
    drawdown_pct: float | None = None,
    latest_bar_timestamp: datetime | None = None,
    bar_count: int = 0,
    is_market_open: bool | None = None,
    kill_switch_engaged: bool = False,
) -> RiskGateStatus:
    """Run every gate and aggregate the result. `passed` is True only if
    every individual check passes -- there is no partial-pass state."""
    checks = {
        "max_position_size": check_max_position_size(target_notional),
        "max_daily_loss": check_max_daily_loss(daily_pnl_pct),
        "max_total_drawdown": check_max_total_drawdown(drawdown_pct),
        "stale_data": check_stale_data(latest_bar_timestamp),
        "sufficient_bars": check_sufficient_bars(bar_count),
        "market_hours": check_market_hours(is_market_open),
        "kill_switch": check_kill_switch(kill_switch_engaged),
    }
    passed = all(ok for ok, _ in checks.values())
    return RiskGateStatus(passed=passed, checks=checks, kill_switch_engaged=kill_switch_engaged)
