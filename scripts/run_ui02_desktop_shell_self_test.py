from __future__ import annotations

import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui02_desktop_shell.constants import APPROVED_PROXY_ENDPOINTS, CSP, LIVE_TRADING_STATUS, ROUTES, SHELL_SCHEMA_VERSION
from ui02_desktop_shell.gateway import GatewayConfig, run_gateway

AUTH_VALUE = "ui02-self-test-local-session-token"


def main() -> int:
    server = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    output: dict[str, object] = {
        "schema_version": "ui02.self_test.v1",
        "shell_schema_version": SHELL_SCHEMA_VERSION,
        "source_mode": "fixture",
        "live_trading_status": LIVE_TRADING_STATUS,
        "checks": {},
        "warnings": [],
        "errors": [],
    }
    fetched_text = ""
    try:
        checks = output["checks"]
        assert isinstance(checks, dict)
        base = server.url
        html, headers = _text_get_with_headers(f"{base}/")
        css = _text_get(f"{base}/assets/theme.css")
        state_js = _text_get(f"{base}/assets/state.js")
        app_js = _text_get(f"{base}/assets/app.js")
        fetched_text = "\n".join([html, css, state_js, app_js])
        checks["shell_and_assets_load"] = all((html, css, state_js, app_js))
        checks["no_external_asset_references"] = not any(marker in fetched_text.lower() for marker in ("http://", "https://", "//cdn", "googleapis", "analytics", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"))
        checks["content_security_policy"] = headers.get("Content-Security-Policy") == CSP and "'unsafe-inline'" not in headers.get("Content-Security-Policy", "")
        checks["all_module_routes"] = all(_status(f"{base}/route/{route}") == 200 for route, _label, _endpoint in ROUTES)
        checks["approved_proxy_endpoints"] = all(_status(f"{base}/gateway{endpoint}") in {200, 204} for endpoint in APPROVED_PROXY_ENDPOINTS if endpoint != "/api/v1/events")
        sse = _text_get(f"{base}/gateway/api/v1/events?after=0")
        replay = _text_get(f"{base}/gateway/api/v1/events", headers={"Last-Event-ID": "5"})
        reconnect = _text_get(f"{base}/gateway/api/v1/events?after=5")
        checks["sse_heartbeat_fixture_replay_reconnect"] = all(fragment in sse + replay + reconnect for fragment in ("event: heartbeat", "event: system_health_updated", "provider_validation_status"))
        checks["mutation_methods_405"] = all(_method_status(f"{base}/gateway/api/v1/research", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"))
        checks["arbitrary_proxy_targets_rejected"] = _status(f"{base}/gateway/http://example.test/") == 403 and _status(f"{base}/gateway/api/v1/../../secrets") in {400, 403, 404}
        checks["token_absent_from_static_and_output"] = AUTH_VALUE not in fetched_text and AUTH_VALUE not in json.dumps(output)
        payload = json.loads(_text_get(f"{base}/gateway/api/v1/safety"))
        checks["pending_non_live_disabled"] = payload["provider_validation_status"] == "pending" and payload["safety_state"]["live_trading_enabled"] is False
        checks["live_trading_disabled_visible"] = LIVE_TRADING_STATUS in html
        checks["loopback_only"] = server.url.startswith("http://127.0.0.1:")
    except Exception as exc:
        output["errors"] = [{"code": "ui02_self_test_failed", "message": exc.__class__.__name__}]
    finally:
        ui02_port = server.port
        ui01_port = server.ui01.port
        server.stop()
        time.sleep(0.05)
        checks = output["checks"]
        assert isinstance(checks, dict)
        checks["ui02_port_released"] = _port_released(ui02_port)
        checks["ui01_port_released"] = _port_released(ui01_port)
        checks["thread_cleanup"] = not server.thread or not server.thread.is_alive()

    sanitized = json.dumps(output, sort_keys=True, separators=(",", ":"))
    if AUTH_VALUE in sanitized:
        print(json.dumps({"schema_version": "ui02.self_test.v1", "errors": [{"code": "sanitization_failed"}]}, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True, indent=2))
    checks_ok = all(bool(value) for value in output.get("checks", {}).values())
    return 0 if checks_ok and not output.get("errors") else 1


def _text_get(url: str, headers: dict[str, str] | None = None) -> str:
    text, _headers = _text_get_with_headers(url, headers=headers)
    return text


def _text_get_with_headers(url: str, headers: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8"), dict(response.headers)


def _status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code


def _method_status(url: str, method: str) -> int:
    request = urllib.request.Request(url, data=b"{}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code


def _port_released(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    raise SystemExit(main())
