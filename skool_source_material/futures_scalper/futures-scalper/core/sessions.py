"""CME Globex session calendar for equity-index and similar futures.

Futures trade close to 24 hours, which is the main reason a stock loop does not
transfer cleanly. This module answers three questions the live loop needs every
iteration: is the market open right now, are we inside the regular cash session
(RTH) or the overnight session (ETH), and when does the next session open.

All times are handled in US Eastern. Globex equity-index hours in ET:
    Open  : Sunday 18:00
    Close : Friday 17:00
    Daily maintenance break Mon-Thu: 17:00 -> 18:00
    Regular trading hours (RTH): 09:30 -> 16:00 on weekdays

These are the standard index hours. Energy and metals differ slightly; adjust
``rth_open``/``rth_close`` and the break window in config if you trade those.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - fallback if tz database is unavailable
    _ET = None


class SessionType(str, Enum):
    RTH = "rth"            # Regular cash-hours session
    ETH = "eth"            # Electronic / overnight session
    MAINTENANCE = "maint"  # Daily break, market closed briefly
    CLOSED = "closed"      # Weekend or after Friday close


@dataclass
class SessionConfig:
    open_weekday: int = 6       # Sunday (Mon=0 .. Sun=6)
    open_time: time = time(18, 0)
    close_weekday: int = 4      # Friday
    close_time: time = time(17, 0)
    break_start: time = time(17, 0)
    break_end: time = time(18, 0)
    rth_open: time = time(9, 30)
    rth_close: time = time(16, 0)

    @classmethod
    def from_dict(cls, d: dict | None) -> "SessionConfig":
        d = d or {}
        def _t(key, default):
            v = d.get(key)
            if isinstance(v, str) and ":" in v:
                hh, mm = v.split(":")[:2]
                return time(int(hh), int(mm))
            return default
        return cls(
            open_weekday=d.get("open_weekday", 6),
            open_time=_t("open_time", time(18, 0)),
            close_weekday=d.get("close_weekday", 4),
            close_time=_t("close_time", time(17, 0)),
            break_start=_t("break_start", time(17, 0)),
            break_end=_t("break_end", time(18, 0)),
            rth_open=_t("rth_open", time(9, 30)),
            rth_close=_t("rth_close", time(16, 0)),
        )


class SessionCalendar:
    """Stateless calendar; pass any timezone-aware or naive ET datetime."""

    def __init__(self, config: SessionConfig | dict | None = None) -> None:
        if isinstance(config, SessionConfig):
            self.cfg = config
        else:
            self.cfg = SessionConfig.from_dict(config)

    # -- normalisation -----------------------------------------------------
    @staticmethod
    def now_et() -> datetime:
        if _ET is not None:
            return datetime.now(_ET)
        return datetime.now(timezone.utc) - timedelta(hours=5)

    def _as_et(self, dt: datetime) -> datetime:
        if _ET is None:
            return dt.replace(tzinfo=None)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=_ET)
        return dt.astimezone(_ET)

    # -- core queries ------------------------------------------------------
    def session_type(self, dt: datetime | None = None) -> SessionType:
        dt = self._as_et(dt or self.now_et())
        wd = dt.weekday()
        t = dt.time()

        # Saturday is fully closed.
        if wd == 5:
            return SessionType.CLOSED
        # Sunday: closed until the 18:00 open.
        if wd == 6:
            return SessionType.ETH if t >= self.cfg.open_time else SessionType.CLOSED
        # Friday: closes at 17:00.
        if wd == 4 and t >= self.cfg.close_time:
            return SessionType.CLOSED
        # Daily maintenance break (Mon-Thu) 17:00-18:00.
        if wd in (0, 1, 2, 3) and self.cfg.break_start <= t < self.cfg.break_end:
            return SessionType.MAINTENANCE
        # Regular cash hours.
        if self.cfg.rth_open <= t < self.cfg.rth_close:
            return SessionType.RTH
        return SessionType.ETH

    def is_open(self, dt: datetime | None = None) -> bool:
        st = self.session_type(dt)
        return st in (SessionType.RTH, SessionType.ETH)

    def is_rth(self, dt: datetime | None = None) -> bool:
        return self.session_type(dt) is SessionType.RTH

    def is_maintenance(self, dt: datetime | None = None) -> bool:
        return self.session_type(dt) is SessionType.MAINTENANCE

    def next_open(self, dt: datetime | None = None) -> datetime:
        """Return the next datetime at which the market is open."""
        dt = self._as_et(dt or self.now_et())
        probe = dt
        for _ in range(60 * 24 * 8):  # search up to ~8 days in minute steps
            if self.is_open(probe):
                return probe
            probe += timedelta(minutes=1)
        return probe

    def minutes_until_close(self, dt: datetime | None = None) -> float | None:
        """Minutes until the next maintenance break or weekly close, if open."""
        dt = self._as_et(dt or self.now_et())
        if not self.is_open(dt):
            return None
        wd = dt.weekday()
        if wd == 4:
            close_dt = dt.replace(hour=self.cfg.close_time.hour, minute=self.cfg.close_time.minute,
                                  second=0, microsecond=0)
        else:
            close_dt = dt.replace(hour=self.cfg.break_start.hour, minute=self.cfg.break_start.minute,
                                  second=0, microsecond=0)
        if close_dt <= dt:
            return 0.0
        return (close_dt - dt).total_seconds() / 60.0

    def session_open_for(self, dt: datetime) -> datetime:
        """The RTH open timestamp for the date of ``dt`` (used for VWAP anchoring)."""
        dt = self._as_et(dt)
        return dt.replace(hour=self.cfg.rth_open.hour, minute=self.cfg.rth_open.minute,
                          second=0, microsecond=0)
