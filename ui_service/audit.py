from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ui_service.envelope import utc_now


@dataclass
class InMemoryAuditSink:
    records: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        endpoint: str,
        method: str,
        status: int,
        duration_class: str,
        request_id: str,
        correlation_id: str,
        source_mode: str,
        authorization_result: str,
        safety_state: dict[str, Any],
    ) -> None:
        self.records.append(
            {
                "created_at": utc_now(),
                "endpoint": endpoint,
                "method": method,
                "status": status,
                "duration_class": duration_class,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "source_mode": source_mode,
                "authorization_result": authorization_result,
                "safety_state": {
                    "live_trading_enabled": bool(safety_state.get("live_trading_enabled")),
                    "broker_order_call_performed": bool(safety_state.get("broker_order_call_performed")),
                    "live_trading_status": safety_state.get("live_trading_status"),
                },
            }
        )
