"""
monitoring/alerts.py
====================
Critical-event alerting (STEP 8). Fires on:
  * REGIME_SHIFT       — e.g. Bull -> Bear
  * CIRCUIT_BREAKER    — any RiskManager breaker trip
  * DATA_FEED_FAILURE  — stale / missing market data

Rate limited to at most 1 alert per 15 minutes PER TRIGGER TYPE, so a storm of
identical events cannot spam the channel while distinct critical events still
get through. Every alert is also written to the structured JSON log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from monitoring.logger import get_logger


class AlertType(Enum):
    REGIME_SHIFT = "regime_shift"
    CIRCUIT_BREAKER = "circuit_breaker"
    DATA_FEED_FAILURE = "data_feed_failure"
    STRATEGY_DISABLED = "strategy_disabled"
    ALLOCATOR_REBALANCE = "allocator_rebalance"
    CORRELATION_CLUSTER = "correlation_cluster"
    PORTFOLIO_DD_BREAKER = "portfolio_dd_breaker"


@dataclass
class Alert:
    alert_type: AlertType
    message: str
    timestamp: datetime
    severity: str = "warning"


class AlertManager:
    def __init__(
        self,
        rate_limit_minutes: int = 15,
        sink: Callable[[Alert], None] | None = None,
    ):
        self.rate_limit = timedelta(minutes=rate_limit_minutes)
        self.sink = sink
        self._last_sent: dict[AlertType, datetime] = {}
        self.history: list[Alert] = []
        self._log = get_logger("alerts", log_file="alerts.jsonl")

    def _rate_ok(self, alert_type: AlertType, now: datetime) -> bool:
        last = self._last_sent.get(alert_type)
        return last is None or (now - last) >= self.rate_limit

    def _emit(self, alert_type: AlertType, message: str, severity: str, now: datetime | None) -> bool:
        now = now or datetime.now()
        if not self._rate_ok(alert_type, now):
            return False
        self._last_sent[alert_type] = now
        alert = Alert(alert_type, message, now, severity)
        self.history.append(alert)
        self._log.warning(
            message,
            extra={"extra_fields": {"alert_type": alert_type.value, "severity": severity}},
        )
        if self.sink is not None:
            self.sink(alert)
        return True

    # --- triggers ---
    def regime_shift(self, from_regime: str, to_regime: str, now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.REGIME_SHIFT,
            f"Regime shift: {from_regime} -> {to_regime}",
            "warning", now,
        )

    def circuit_breaker(self, breaker_type: str, drawdown: float, equity: float,
                        now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.CIRCUIT_BREAKER,
            f"CIRCUIT BREAKER {breaker_type}: DD={drawdown * 100:.2f}% equity=${equity:,.0f}",
            "critical", now,
        )

    def data_feed_failure(self, detail: str, now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.DATA_FEED_FAILURE,
            f"Data feed failure: {detail}",
            "critical", now,
        )

    # --- multi-strategy triggers ---
    def strategy_disabled(self, strategy_name: str, reason: str | None,
                          now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.STRATEGY_DISABLED,
            f"Strategy auto-disabled: {strategy_name} ({reason or 'health check failed'})",
            "critical", now,
        )

    def allocator_rebalance(self, n_changes: int, now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.ALLOCATOR_REBALANCE,
            f"Allocator rebalance triggered: {n_changes} weight change(s)",
            "info", now,
        )

    def correlation_cluster(self, pair: tuple[str, str], corr: float,
                            now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.CORRELATION_CLUSTER,
            f"Correlation cluster detected: {pair[0]}~{pair[1]} corr={corr:.2f}",
            "warning", now,
        )

    def portfolio_dd_breaker(self, kind: str, drawdown: float, equity: float,
                             now: datetime | None = None) -> bool:
        return self._emit(
            AlertType.PORTFOLIO_DD_BREAKER,
            f"PORTFOLIO DD BREAKER {kind}: DD={drawdown * 100:.2f}% equity=${equity:,.0f}",
            "critical", now,
        )
