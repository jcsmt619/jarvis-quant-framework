from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ui02_desktop_shell.constants import CSP, LIVE_TRADING_STATUS, ROUTES
from ui02_desktop_shell.gateway import GatewayConfig, run_gateway

AUTH_VALUE = "deterministic-ui02-test-token"


@pytest.fixture()
def gateway():
    instance = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    try:
        yield instance
    finally:
        ui02_port = instance.port
        ui01_port = instance.ui01.port
        instance.stop()
        assert instance.port_released()
        assert instance.ui01.service.verify_port_released("127.0.0.1", ui01_port)
        assert not instance.thread or not instance.thread.is_alive()


def test_ui02_shell_serves_local_assets_with_strict_headers_and_no_token(gateway) -> None:
    html, headers = _text_get_with_headers(f"{gateway.url}/")
    css = _text_get(f"{gateway.url}/assets/theme.css")
    state_js = _text_get(f"{gateway.url}/assets/state.js")
    app_js = _text_get(f"{gateway.url}/assets/app.js")
    combined = "\n".join([html, css, state_js, app_js]).lower()

    assert headers["Content-Security-Policy"] == CSP
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Frame-Options"] == "DENY"
    assert LIVE_TRADING_STATUS in html
    assert AUTH_VALUE not in html + css + state_js + app_js
    for forbidden in ("https://", "http://", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function", "unsafe-inline"):
        assert forbidden not in combined


@pytest.mark.parametrize("route,label,endpoint", ROUTES)
def test_ui02_all_routes_load_without_full_page_dependency(gateway, route: str, label: str, endpoint: str) -> None:
    body = _text_get(f"{gateway.url}/route/{route}")

    assert "Jarvis Quant" in body
    assert LIVE_TRADING_STATUS in body


def test_ui02_gateway_proxies_only_approved_read_endpoints_and_keeps_token_server_side(gateway) -> None:
    payload = json.loads(_text_get(f"{gateway.url}/gateway/api/v1/safety"))

    assert payload["provider_validation_status"] == "pending"
    assert payload["safety_state"]["live_trading_enabled"] is False
    assert payload["data"]["is_live"] is False
    assert AUTH_VALUE not in json.dumps(payload)
    assert _status(f"{gateway.url}/gateway/api/v1/not-approved") == 403
    assert _status(f"{gateway.url}/gateway/http://127.0.0.1:1/api/v1/safety") == 403
    assert _status(f"{gateway.url}/assets/../gateway.py") == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"])
def test_ui02_gateway_rejects_mutation_methods(gateway, method: str) -> None:
    payload, status = _request_json(f"{gateway.url}/gateway/api/v1/research", method=method, data=b'{"ignored":true}')

    assert status == 405
    assert payload["status"] == "method_not_allowed"
    assert payload["live_trading_status"] == LIVE_TRADING_STATUS


def test_ui02_sse_gateway_replay_headers_and_disabled_state(gateway) -> None:
    body, headers = _text_get_with_headers(f"{gateway.url}/gateway/api/v1/events?after=0")
    replay = _text_get(f"{gateway.url}/gateway/api/v1/events", headers={"Last-Event-ID": "5"})

    assert headers["Content-Security-Policy"] == CSP
    assert headers["Cache-Control"] == "no-store"
    assert "event: heartbeat" in body
    assert "event: system_health_updated" in body
    assert "event:" in replay
    assert '"provider_validation_status":"pending"' in body
    assert '"is_live":false' in body
    assert AUTH_VALUE not in body + replay


def test_ui02_config_rejects_remote_binding_and_live_provider() -> None:
    with pytest.raises(ValueError):
        GatewayConfig(host="0.0.0.0")
    with pytest.raises(ValueError):
        GatewayConfig(host="192.168.1.20")
    with pytest.raises(ValueError):
        GatewayConfig(source_mode="live_provider")


def test_ui02_self_test_script_prints_sanitized_result() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui02_desktop_shell_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "ui02-self-test-local-session-token" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "ui02.self_test.v1"
    assert payload["live_trading_status"] == LIVE_TRADING_STATUS
    assert all(payload["checks"].values())


def test_ui02_import_boundary_does_not_load_broker_write_modules() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("ui02_desktop_shell").glob("*.py"))
    for marker in ("from broker", "from execution", "paper_executor", "order_intent", "dotenv", "keyring", "submit_order", "route_order"):
        assert marker not in source


def _text_get(url: str, headers: dict[str, str] | None = None) -> str:
    text, _headers = _text_get_with_headers(url, headers=headers)
    return text


def _text_get_with_headers(url: str, headers: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8"), dict(response.headers)


def _request_json(url: str, *, method: str, data: bytes | None = None) -> tuple[dict[str, object], int]:
    request = urllib.request.Request(url, method=method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8") or "{}"), response.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8") or "{}"), exc.code


def _status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
