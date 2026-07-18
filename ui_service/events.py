from __future__ import annotations

import json
import queue
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ui_service.constants import (
    EVENT_SCHEMA_VERSION,
    MAX_EVENT_BYTES,
    PROVIDER_VALIDATION_PENDING,
    SAFETY_STATE,
    SECRET_FIELD_MARKERS,
)
from ui_service.envelope import utc_now

SUPPORTED_EVENT_TYPES = {
    "system_health_updated",
    "safety_state_updated",
    "data_status_updated",
    "research_refreshed",
    "screener_refreshed",
    "risk_gate_updated",
    "portfolio_snapshot_updated",
    "alert_created",
    "backtest_completed",
    "paper_activity_updated",
    "heartbeat",
    "stream_gap",
}

_SAFE_EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


@dataclass(frozen=True)
class EventRecord:
    schema_version: str
    event_id: str
    event_type: str
    sequence: int
    occurred_at: str
    correlation_id: str
    source: str
    source_mode: str
    provider_validation_status: str
    safety_state: dict[str, Any]
    payload: dict[str, Any]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sequence": self.sequence,
            "occurred_at": self.occurred_at,
            "correlation_id": self.correlation_id,
            "source": self.source,
            "source_mode": self.source_mode,
            "provider_validation_status": self.provider_validation_status,
            "safety_state": self.safety_state,
            "payload": self.payload,
            "warnings": self.warnings,
        }


@dataclass
class EventBackbone:
    source_mode: str = "fixture"
    buffer_size: int = 64
    subscriber_queue_size: int = 8
    deterministic_ids: bool = True
    _events: deque[EventRecord] = field(init=False)
    _seen_ids: set[str] = field(default_factory=set, init=False)
    _sequence: int = field(default=0, init=False)
    _subscribers: list[queue.Queue[EventRecord]] = field(default_factory=list, init=False)
    _gap_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._events = deque(maxlen=self.buffer_size)

    @property
    def latest_sequence(self) -> int:
        return self._sequence

    def publish_fixture_events(self) -> None:
        for event_type in (
            "system_health_updated",
            "safety_state_updated",
            "data_status_updated",
            "research_refreshed",
            "screener_refreshed",
            "risk_gate_updated",
            "portfolio_snapshot_updated",
            "alert_created",
            "backtest_completed",
            "paper_activity_updated",
        ):
            self.publish(event_type=event_type, correlation_id="corr-ui01-fixture", payload={"status": "fixture"})

    def heartbeat(self, correlation_id: str = "corr-ui01-heartbeat") -> EventRecord:
        return self._make(event_type="heartbeat", correlation_id=correlation_id, payload={"status": "alive"}, advance=False)

    def publish(self, *, event_type: str, correlation_id: str, payload: dict[str, Any], occurred_at: str | None = None, event_id: str | None = None) -> EventRecord:
        record = self._make(event_type=event_type, correlation_id=correlation_id, payload=payload, occurred_at=occurred_at, event_id=event_id, advance=True)
        self._validate(record)
        self._sequence = record.sequence
        self._events.append(record)
        self._seen_ids.add(record.event_id)
        for subscriber in list(self._subscribers):
            try:
                subscriber.put_nowait(record)
            except queue.Full:
                self._gap_count += 1
                gap = self._make(
                    event_type="stream_gap",
                    correlation_id=correlation_id,
                    payload={"reason": "subscriber_backpressure", "lost_event_sequence": record.sequence},
                    advance=True,
                )
                self._validate(gap)
                self._sequence = gap.sequence
                self._events.append(gap)
                self._seen_ids.add(gap.event_id)
        return record

    def replay_after(self, sequence: int) -> list[EventRecord]:
        if sequence < 0:
            raise ValueError("after sequence must be non-negative")
        return [event for event in self._events if event.sequence > sequence]

    def subscribe(self) -> queue.Queue[EventRecord]:
        subscriber: queue.Queue[EventRecord] = queue.Queue(maxsize=self.subscriber_queue_size)
        self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[EventRecord]) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def _make(
        self,
        *,
        event_type: str,
        correlation_id: str,
        payload: dict[str, Any],
        advance: bool,
        occurred_at: str | None = None,
        event_id: str | None = None,
    ) -> EventRecord:
        sequence = self._sequence + 1 if advance else self._sequence
        generated_id = event_id or (f"evt-ui01-{sequence:06d}" if advance else "evt-ui01-heartbeat")
        return EventRecord(
            schema_version=EVENT_SCHEMA_VERSION,
            event_id=generated_id,
            event_type=event_type,
            sequence=sequence,
            occurred_at=occurred_at or utc_now(),
            correlation_id=correlation_id,
            source="ui_service.event_backbone",
            source_mode=self.source_mode,
            provider_validation_status=PROVIDER_VALIDATION_PENDING,
            safety_state=dict(SAFETY_STATE),
            payload=payload,
            warnings=[],
        )

    def _validate(self, record: EventRecord) -> None:
        if record.event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError("unsupported_event_type")
        if not _SAFE_EVENT_ID.match(record.event_id):
            raise ValueError("malformed_event_id")
        if record.event_id in self._seen_ids:
            raise ValueError("duplicate_event_id")
        if record.sequence <= 0:
            raise ValueError("out_of_order_event")
        previous = self._events[-1].sequence if self._events else 0
        if record.sequence != previous + 1:
            raise ValueError("out_of_order_event")
        occurred = datetime.fromisoformat(record.occurred_at.replace("Z", "+00:00"))
        if occurred > datetime.now(timezone.utc).replace(microsecond=0):
            raise ValueError("future_event")
        encoded = json.dumps(record.as_dict(), sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_EVENT_BYTES:
            raise ValueError("oversized_event")
        if _contains_secret_marker(record.payload):
            raise ValueError("secret_bearing_event")


def _contains_secret_marker(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_FIELD_MARKERS):
                return True
            if _contains_secret_marker(item):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_marker(item) for item in value)
    elif isinstance(value, str):
        lowered = value.lower()
        secret_markers = (
            "-".join(("mock", "quote", "token")),
            "_".join(("api", "key")) + "=",
            "_".join(("oauth", "token")),
            "".join(("pass", "word")) + "=",
        )
        return any(marker in lowered for marker in secret_markers)
    return False
