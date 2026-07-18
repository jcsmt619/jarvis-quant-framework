from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

from ui_service.audit import InMemoryAuditSink
from ui_service.auth import LocalSessionAuthorizer
from ui_service.envelope import normalize_correlation_id, new_request_id, response_envelope
from ui_service.events import EventBackbone
from ui_service.sources import ReadModelSource


@dataclass(frozen=True)
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 0
    source_mode: str = "fixture"
    local_session_token: str | None = None
    replay_buffer_size: int = 64
    subscriber_queue_size: int = 8

    def validate(self) -> None:
        if self.host != "127.0.0.1":
            raise ValueError("ui01 service may bind only to 127.0.0.1")
        if not (0 <= self.port <= 65535):
            raise ValueError("invalid local port")
        if self.source_mode not in {"fixture", "recorded_response", "live_provider"}:
            raise ValueError("unsupported source mode")


class LocalReadOnlyService:
    def __init__(self, config: ServiceConfig) -> None:
        config.validate()
        self.config = config
        self.authorizer = LocalSessionAuthorizer(config.local_session_token)
        self.audit = InMemoryAuditSink()
        self.source = ReadModelSource(config.source_mode)
        self.events = EventBackbone(
            source_mode=config.source_mode,
            buffer_size=config.replay_buffer_size,
            subscriber_queue_size=config.subscriber_queue_size,
        )
        self.events.publish_fixture_events()
        self.ready = True

    def build_response(
        self,
        *,
        model_name: str,
        correlation_header: str | None,
        authorization_values: list[str] | None,
        protected: bool,
    ) -> tuple[int, dict[str, Any], str]:
        request_id = new_request_id()
        correlation_id, correlation_error = normalize_correlation_id(correlation_header)
        if correlation_error:
            correlation_id = f"corr-{request_id}"
            return 400, response_envelope(
                request_id=request_id,
                correlation_id=correlation_id,
                source_mode=self.config.source_mode,
                data={"status": "rejected"},
                errors=[{"code": correlation_error, "message": "Correlation ID is malformed or oversized."}],
            ), "correlation_rejected"
        auth_result = self.authorizer.check(authorization_values) if protected else None
        if auth_result and not auth_result.allowed:
            return 401, response_envelope(
                request_id=request_id,
                correlation_id=correlation_id,
                source_mode=self.config.source_mode,
                data={"status": "authorization_required"},
                errors=[{"code": f"auth_{auth_result.code}", "message": "Local session authorization failed."}],
            ), auth_result.code
        data, warnings = self.source.read(model_name)
        status = 503 if self.config.source_mode == "live_provider" else 200
        return status, response_envelope(
            request_id=request_id,
            correlation_id=correlation_id,
            source_mode=self.config.source_mode,
            data=data,
            warnings=warnings,
        ), "authorized" if auth_result else "not_required"

    def verify_port_released(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, port)) != 0
