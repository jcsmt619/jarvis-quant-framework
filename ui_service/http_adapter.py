from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ui_service.constants import (
    ALLOWED_METHODS,
    MAX_HEADER_VALUE_BYTES,
    MAX_REQUEST_BODY_BYTES,
    MUTATION_METHODS,
    PUBLIC_ENDPOINTS,
    READ_ENDPOINTS,
    SAFETY_STATE,
)
from ui_service.envelope import json_bytes, normalize_correlation_id, new_request_id, response_envelope
from ui_service.service import LocalReadOnlyService, ServiceConfig


class LoopbackHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, config: ServiceConfig, service: LocalReadOnlyService) -> None:
        if config.host != "127.0.0.1":
            raise ValueError("ui01 HTTP adapter may bind only to 127.0.0.1")
        self.service = service
        super().__init__((config.host, config.port), _Handler)


class LocalServiceServer:
    def __init__(self, config: ServiceConfig) -> None:
        self.service = LocalReadOnlyService(config)
        self.httpd = LoopbackHTTPServer(config, self.service)
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> None:
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="ui01-local-service", daemon=False)
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)

    def port_released(self) -> bool:
        return self.service.verify_port_released("127.0.0.1", self.port)


class _Handler(BaseHTTPRequestHandler):
    server_version = "JarvisUI01/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self._send_empty(204, {"Allow": "GET, HEAD, OPTIONS"})

    def do_HEAD(self) -> None:
        self._handle(send_body=False)

    def do_GET(self) -> None:
        self._handle(send_body=True)

    def do_POST(self) -> None:
        self._reject_mutation()

    def do_PUT(self) -> None:
        self._reject_mutation()

    def do_PATCH(self) -> None:
        self._reject_mutation()

    def do_DELETE(self) -> None:
        self._reject_mutation()

    def do_CONNECT(self) -> None:
        self._reject_mutation()

    def do_TRACE(self) -> None:
        self._reject_mutation()

    def _reject_mutation(self) -> None:
        self._drain_bounded_body()
        request_id = new_request_id()
        correlation_id, _ = normalize_correlation_id(self.headers.get("X-Correlation-ID"))
        payload = response_envelope(
            request_id=request_id,
            correlation_id=correlation_id or f"corr-{request_id}",
            source_mode=self.server.service.config.source_mode,
            data={"status": "method_not_allowed"},
            errors=[{"code": "method_not_allowed", "message": "UI-01 is read-only."}],
        )
        self._audit(status=405, request_id=request_id, correlation_id=payload["correlation_id"], authorization_result="not_evaluated")
        self._send_json(405, payload, send_body=True, extra_headers={"Allow": "GET, HEAD, OPTIONS"})

    def _handle(self, *, send_body: bool) -> None:
        started = time.perf_counter()
        if self.command not in ALLOWED_METHODS or self.command in MUTATION_METHODS:
            self._reject_mutation()
            return
        if self._headers_oversized():
            self._send_error_envelope(431, "request_headers_too_large")
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or parsed.path
        if path == "/api/v1/events":
            self._handle_events(parsed.query, send_body=send_body, started=started)
            return
        if path == "/api/v1/version":
            self._handle_version(send_body=send_body)
            return
        model_name = _model_for_path(path)
        if model_name is None:
            self._send_error_envelope(404, "endpoint_not_found")
            return
        protected = path not in PUBLIC_ENDPOINTS
        status, payload, auth_code = self.server.service.build_response(
            model_name=model_name,
            correlation_header=self.headers.get("X-Correlation-ID"),
            authorization_values=self.headers.get_all("Authorization"),
            protected=protected,
        )
        self._audit(
            status=status,
            request_id=payload["request_id"],
            correlation_id=payload["correlation_id"],
            authorization_result=auth_code,
            duration_class=_duration_class(started),
        )
        self._send_json(status, payload, send_body=send_body)

    def _handle_version(self, *, send_body: bool) -> None:
        request_id = new_request_id()
        correlation_id, _ = normalize_correlation_id(self.headers.get("X-Correlation-ID"))
        payload = response_envelope(
            request_id=request_id,
            correlation_id=correlation_id or f"corr-{request_id}",
            source_mode=self.server.service.config.source_mode,
            data={"api_version": "v1", "service": "ui01-local-read-only-service", "live_trading_status": "LIVE TRADING: DISABLED", "is_live": False},
        )
        self._audit(status=200, request_id=request_id, correlation_id=payload["correlation_id"], authorization_result="not_required")
        self._send_json(200, payload, send_body=send_body)

    def _handle_events(self, query: str, *, send_body: bool, started: float) -> None:
        auth = self.server.service.authorizer.check(self.headers.get_all("Authorization"))
        request_id = new_request_id()
        correlation_id, correlation_error = normalize_correlation_id(self.headers.get("X-Correlation-ID"))
        if correlation_error:
            self._send_error_envelope(400, correlation_error)
            return
        if not auth.allowed:
            payload = response_envelope(
                request_id=request_id,
                correlation_id=correlation_id or f"corr-{request_id}",
                source_mode=self.server.service.config.source_mode,
                data={"status": "authorization_required"},
                errors=[{"code": f"auth_{auth.code}", "message": "Local session authorization failed."}],
            )
            self._audit(status=401, request_id=request_id, correlation_id=payload["correlation_id"], authorization_result=auth.code)
            self._send_json(401, payload, send_body=send_body)
            return
        params = parse_qs(query, keep_blank_values=False)
        after = _sequence_after(params, self.headers.get("Last-Event-ID"))
        if after is None:
            self._send_error_envelope(400, "malformed_after_sequence")
            return
        events = [self.server.service.events.heartbeat(correlation_id or "corr-ui01-events")]
        events.extend(self.server.service.events.replay_after(after))
        self._audit(status=200, request_id=request_id, correlation_id=correlation_id or f"corr-{request_id}", authorization_result="authorized", duration_class=_duration_class(started))
        body = b"".join(_sse_bytes(event.as_dict()) for event in events[:12])
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(body) if send_body else 0))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _send_error_envelope(self, status: int, code: str) -> None:
        request_id = new_request_id()
        payload = response_envelope(
            request_id=request_id,
            correlation_id=f"corr-{request_id}",
            source_mode=self.server.service.config.source_mode,
            data={"status": "error"},
            errors=[{"code": code, "message": HTTPStatus(status).phrase}],
        )
        self._audit(status=status, request_id=request_id, correlation_id=payload["correlation_id"], authorization_result="not_evaluated")
        self._send_json(status, payload, send_body=True)

    def _send_json(self, status: int, payload: dict[str, Any], *, send_body: bool, extra_headers: dict[str, str] | None = None) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body) if send_body else 0))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _send_empty(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _audit(self, *, status: int, request_id: str, correlation_id: str, authorization_result: str, duration_class: str = "fast") -> None:
        self.server.service.audit.append(
            endpoint=urlparse(self.path).path,
            method=self.command,
            status=status,
            duration_class=duration_class,
            request_id=request_id,
            correlation_id=correlation_id,
            source_mode=self.server.service.config.source_mode,
            authorization_result=authorization_result,
            safety_state=SAFETY_STATE,
        )

    def _headers_oversized(self) -> bool:
        return any(len(value.encode("utf-8")) > MAX_HEADER_VALUE_BYTES for value in self.headers.values())

    def _drain_bounded_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(min(length, MAX_REQUEST_BODY_BYTES))


def _model_for_path(path: str) -> str | None:
    prefix = "/api/v1/"
    if not path.startswith(prefix):
        return None
    key = path[len(prefix):]
    return READ_ENDPOINTS.get(key)


def _sequence_after(params: dict[str, list[str]], last_event_id: str | None) -> int | None:
    if "after" in params:
        try:
            value = int(params["after"][0])
        except (ValueError, TypeError):
            return None
        return value if value >= 0 else None
    if last_event_id:
        try:
            return int(last_event_id.rsplit("-", 1)[-1])
        except ValueError:
            return None
    return 0


def _sse_bytes(event: dict[str, Any]) -> bytes:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return f"id: {event['sequence']}\nevent: {event['event_type']}\ndata: {encoded}\n\n".encode("utf-8")


def _duration_class(started: float) -> str:
    elapsed = time.perf_counter() - started
    if elapsed < 0.05:
        return "fast"
    if elapsed < 0.5:
        return "normal"
    return "slow"


def run_local_service(config: ServiceConfig) -> LocalServiceServer:
    server = LocalServiceServer(config)
    server.start()
    return server
