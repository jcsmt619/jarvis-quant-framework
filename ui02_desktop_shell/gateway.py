from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ui02_desktop_shell.constants import (
    APPROVED_METHODS,
    APPROVED_PROXY_ENDPOINTS,
    CSP,
    HOST,
    LIVE_TRADING_STATUS,
    MAX_HEADER_VALUE_BYTES,
    MAX_REQUEST_BODY_BYTES,
    MUTATION_METHODS,
    ROUTES,
    SHELL_SCHEMA_VERSION,
)
from ui_service.http_adapter import LocalServiceServer, run_local_service
from ui_service.service import ServiceConfig

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"


class UI02GatewayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, config: "GatewayConfig", ui01: LocalServiceServer) -> None:
        if config.host != HOST:
            raise ValueError("ui02 gateway may bind only to 127.0.0.1")
        self.config = config
        self.ui01 = ui01
        self.local_session_token = config.local_session_token
        super().__init__((config.host, config.port), _GatewayHandler)


class GatewayConfig:
    def __init__(self, *, host: str = HOST, port: int = 0, source_mode: str = "fixture", local_session_token: str | None = None) -> None:
        self.host = host
        self.port = port
        self.source_mode = source_mode
        self.local_session_token = local_session_token or secrets.token_urlsafe(32)
        self.validate()

    def validate(self) -> None:
        if self.host != HOST:
            raise ValueError("ui02 gateway may bind only to 127.0.0.1")
        if not (0 <= self.port <= 65535):
            raise ValueError("invalid local port")
        if self.source_mode not in {"fixture", "recorded_response"}:
            raise ValueError("ui02 supports only fixture or recorded_response source modes")
        if not self.local_session_token or any(ch.isspace() for ch in self.local_session_token):
            raise ValueError("invalid local session token")


class UI02GatewayServer:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.ui01 = run_local_service(
            ServiceConfig(
                host=HOST,
                port=0,
                source_mode=config.source_mode,
                local_session_token=config.local_session_token,
                replay_buffer_size=64,
                subscriber_queue_size=8,
            )
        )
        self.httpd = UI02GatewayHTTPServer(config, self.ui01)
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> None:
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="ui02-desktop-shell", daemon=False)
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)
        self.ui01.stop()

    def port_released(self) -> bool:
        return verify_port_released(HOST, self.port)


class _GatewayHandler(BaseHTTPRequestHandler):
    server_version = "JarvisUI02/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        if self._headers_oversized():
            self._send_error(431, "request_headers_too_large")
            return
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

    def _handle(self, *, send_body: bool) -> None:
        if self.command not in APPROVED_METHODS or self.command in MUTATION_METHODS:
            self._reject_mutation()
            return
        if self._headers_oversized():
            self._send_error(431, "request_headers_too_large")
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.scheme or parsed.netloc:
            self._send_error(400, "absolute_url_rejected")
            return
        path = parsed.path.rstrip("/") or "/"
        if path in {"/", "/index.html"}:
            self._send_static("index.html", send_body=send_body)
            return
        if path.startswith("/assets/"):
            self._send_static(path[len("/assets/") :], send_body=send_body)
            return
        if path.startswith("/route/"):
            route = path[len("/route/") :]
            if not any(route == item[0] for item in ROUTES):
                self._send_error(404, "route_not_found")
                return
            self._send_static("index.html", send_body=send_body)
            return
        if path.startswith("/gateway"):
            self._proxy(path[len("/gateway") :] or "/", parsed.query, send_body=send_body)
            return
        self._send_error(404, "path_not_found")

    def _send_static(self, requested: str, *, send_body: bool) -> None:
        candidate = _resolve_static(requested)
        if candidate is None:
            self._send_error(404, "asset_not_found")
            return
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(200)
        self._send_security_headers(no_store=False)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body) if send_body else 0))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _proxy(self, upstream_path: str, query: str, *, send_body: bool) -> None:
        upstream_path = upstream_path.rstrip("/") or upstream_path
        if upstream_path not in APPROVED_PROXY_ENDPOINTS:
            self._send_error(403, "proxy_destination_rejected")
            return
        if upstream_path != "/api/v1/events" and query:
            self._send_error(400, "query_string_rejected")
            return
        if upstream_path == "/api/v1/events" and not _valid_events_query(query):
            self._send_error(400, "event_query_rejected")
            return
        target = f"{self.server.ui01.url}{upstream_path}"
        if query:
            target = f"{target}?{query}"
        headers = {
            "Authorization": f"Bearer {self.server.local_session_token}",
            "X-Correlation-ID": "corr-ui02-gateway",
        }
        last_event_id = self.headers.get("Last-Event-ID")
        if last_event_id:
            if not last_event_id.isdigit():
                self._send_error(400, "last_event_id_rejected")
                return
            headers["Last-Event-ID"] = last_event_id
        request = urllib.request.Request(target, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read() if send_body else b""
                status = response.status
                content_type = response.headers.get("Content-Type", "application/octet-stream")
        except urllib.error.HTTPError as exc:
            body = exc.read() if send_body else b""
            status = exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
        self.send_response(status)
        self._send_security_headers(no_store=True)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _reject_mutation(self) -> None:
        self._drain_bounded_body()
        self._send_json(405, {"schema_version": SHELL_SCHEMA_VERSION, "status": "method_not_allowed", "live_trading_status": LIVE_TRADING_STATUS}, {"Allow": "GET, HEAD, OPTIONS"})

    def _send_error(self, status: int, code: str) -> None:
        self._send_json(status, {"schema_version": SHELL_SCHEMA_VERSION, "status": "rejected", "code": code, "message": HTTPStatus(status).phrase, "live_trading_status": LIVE_TRADING_STATUS}, None)

    def _send_json(self, status: int, payload: dict[str, Any], extra_headers: dict[str, str] | None) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._send_security_headers(no_store=True)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self._send_security_headers(no_store=True)
        self.send_header("Content-Length", "0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send_security_headers(self, *, no_store: bool) -> None:
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=(), usb=(), serial=()")
        self.send_header("X-Jarvis-Local-Only", "127.0.0.1")
        if no_store:
            self.send_header("Pragma", "no-cache")

    def _headers_oversized(self) -> bool:
        return any(len(value.encode("utf-8")) > MAX_HEADER_VALUE_BYTES for value in self.headers.values())

    def _drain_bounded_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(min(length, MAX_REQUEST_BODY_BYTES))


def _resolve_static(requested: str) -> Path | None:
    if "\\" in requested or "\x00" in requested:
        return None
    requested = requested.lstrip("/")
    if requested in {"", "."}:
        requested = "index.html"
    candidate = (STATIC_ROOT / requested).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _valid_events_query(query: str) -> bool:
    if not query:
        return True
    params = urllib.parse.parse_qs(query, keep_blank_values=False)
    if set(params) != {"after"}:
        return False
    try:
        value = int(params["after"][0])
    except (TypeError, ValueError, IndexError):
        return False
    return value >= 0


def verify_port_released(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) != 0


def run_gateway(config: GatewayConfig) -> UI02GatewayServer:
    server = UI02GatewayServer(config)
    server.start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the UI-02 local desktop shell. LIVE TRADING: DISABLED.")
    parser.add_argument("--port", type=int, default=0, help="127.0.0.1 port, or 0 for ephemeral.")
    parser.add_argument("--source-mode", choices=("fixture", "recorded_response"), default="fixture")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window.")
    parser.add_argument("--open", action="store_true", help="Open the installed browser to the local shell.")
    args = parser.parse_args(argv)

    server = run_gateway(GatewayConfig(port=args.port, source_mode=args.source_mode))
    print(json.dumps({"schema_version": SHELL_SCHEMA_VERSION, "url": server.url, "source_mode": args.source_mode, "live_trading_status": LIVE_TRADING_STATUS}, sort_keys=True), flush=True)
    if args.open and not args.no_open:
        webbrowser.open(f"{server.url}/", new=1, autoraise=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
