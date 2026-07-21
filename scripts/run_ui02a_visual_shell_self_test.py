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

from ui02_desktop_shell.constants import CSP, LIVE_TRADING_STATUS, ROUTES, SHELL_SCHEMA_VERSION
from ui02_desktop_shell.gateway import GatewayConfig, run_gateway

AUTH_VALUE = "ui02a-self-test-local-session-token"
STATIC_ROOT = ROOT / "ui02_desktop_shell" / "static"


def main() -> int:
    server = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    output: dict[str, object] = {
        "schema_version": "ui02a.visual_shell_self_test.v1",
        "shell_schema_version": SHELL_SCHEMA_VERSION,
        "source_mode": "fixture",
        "provider_validation_status": "pending",
        "is_live": False,
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
        icons = _text_get(f"{base}/assets/icons.svg")
        fetched_text = "\n".join([html, css, state_js, app_js, icons])
        lowered = fetched_text.lower().replace("http://www.w3.org/2000/svg", "")

        checks["local_assets_load"] = all((html, css, state_js, app_js, icons))
        checks["overview_component_hierarchy"] = all(
            marker in app_js
            for marker in (
                "Market Regime",
                "Risk Gate",
                "Opportunity Radar",
                "Portfolio and Exposure",
                "Wealth Engine",
                "Moonshot Engine",
                "Signal-Strength Distribution",
                "Exposure Allocation",
                "Safe Mode",
            )
        )
        checks["diagnostics_collapsed_by_default"] = "<details" not in html.lower() and "details.className = \"panel diagnostics" in app_js
        checks["no_external_references"] = not any(
            marker in lowered
            for marker in ("http://", "https://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function")
        )
        checks["content_security_policy"] = headers.get("Content-Security-Policy") == CSP and "'unsafe-inline'" not in headers.get("Content-Security-Policy", "")
        checks["all_routes_load"] = all(_status(f"{base}/route/{route}") == 200 for route, _label, _endpoint in ROUTES)
        checks["global_safety_badge"] = html.count(LIVE_TRADING_STATUS) == 1 and LIVE_TRADING_STATUS in app_js
        checks["provider_pending_non_live"] = _provider_pending_non_live(base)
        checks["svg_sprite_accessible"] = all(f'id="icon-{icon}"' in icons for icon in ("emblem", "overview", "shield", "events", "moonshot"))
        checks["responsive_layout_markers"] = all(marker in css for marker in ("@media (max-width: 1280px)", "@media (max-width: 1040px)", "@media (max-width: 760px)", "prefers-reduced-motion"))
        checks["one_sse_instance_static_contract"] = app_js.count("new EventSource(") == 1 and "activeEventSource.close()" in app_js
        checks["fixture_completion_no_hot_loop"] = "markFixtureComplete" in app_js and "setTimeout(connectEvents, delay)" in app_js and "reconnectDelay" in state_js
        checks["bounded_duplicate_counters"] = "MAX_REJECT_COUNT = 25" in state_js and "Math.min(MAX_REJECT_COUNT" in state_js
        checks["sse_fixture_replay"] = _sse_ok(base)
        checks["mutation_methods_405"] = all(_method_status(f"{base}/gateway/api/v1/research", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"))
        checks["token_absent"] = AUTH_VALUE not in fetched_text and AUTH_VALUE not in json.dumps(output)
        checks["loopback_only"] = server.url.startswith("http://127.0.0.1:")
    except Exception as exc:
        output["errors"] = [{"code": "ui02a_visual_self_test_failed", "message": exc.__class__.__name__}]
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
        print(json.dumps({"schema_version": "ui02a.visual_shell_self_test.v1", "errors": [{"code": "sanitization_failed"}]}, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True, indent=2))
    checks_ok = all(bool(value) for value in output.get("checks", {}).values())
    return 0 if checks_ok and not output.get("errors") else 1


def _provider_pending_non_live(base: str) -> bool:
    payload = json.loads(_text_get(f"{base}/gateway/api/v1/safety"))
    return (
        payload["provider_validation_status"] == "pending"
        and payload["safety_state"]["live_trading_enabled"] is False
        and payload["data"]["is_live"] is False
    )


def _sse_ok(base: str) -> bool:
    body = _text_get(f"{base}/gateway/api/v1/events?after=0")
    replay = _text_get(f"{base}/gateway/api/v1/events", headers={"Last-Event-ID": "5"})
    return all(fragment in body + replay for fragment in ("event: heartbeat", "event: system_health_updated", "provider_validation_status"))


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
