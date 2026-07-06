"""Market session helpers for paper trading.

Phase 5C safety layer.

This module provides a conservative local check for whether the US equity
market is probably open.

It intentionally avoids treating uncertain times as tradable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


US_EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(16, 0)


@dataclass(frozen=True)
class MarketSessionStatus:
    timestamp_utc: str
    timestamp_eastern: str
    is_weekday: bool
    is_regular_hours: bool
    is_market_open: bool
    reason: str


def get_us_equity_market_session_status(
    now: datetime | None = None,
) -> MarketSessionStatus:
    """Return a conservative US equity regular-session status.

    This handles weekdays and regular cash-session hours.
    It does not model holidays or early closes yet, so uncertain cases should
    still be treated conservatively by downstream gates.
    """
    if now is None:
        now = datetime.now(UTC)

    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    now_utc = now.astimezone(UTC)
    now_et = now_utc.astimezone(US_EASTERN)

    is_weekday = now_et.weekday() < 5
    is_regular_hours = MARKET_OPEN_TIME <= now_et.time() < MARKET_CLOSE_TIME
    is_market_open = is_weekday and is_regular_hours

    if not is_weekday:
        reason = "US equity market is closed because it is not a weekday"
    elif not is_regular_hours:
        reason = "US equity market is outside regular cash-session hours"
    else:
        reason = "US equity market is within regular cash-session hours"

    return MarketSessionStatus(
        timestamp_utc=now_utc.isoformat(),
        timestamp_eastern=now_et.isoformat(),
        is_weekday=is_weekday,
        is_regular_hours=is_regular_hours,
        is_market_open=is_market_open,
        reason=reason,
    )
