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

AUTH_VALUE = "deterministic-ui02a-test-token"
STATIC_ROOT = Path("ui02_desktop_shell/static")


@pytest.fixture()
def gateway():
    instance = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    try:
        yield instance
    finally:
        ui01_port = instance.ui01.port
        instance.stop()
        assert instance.port_released()
        assert instance.ui01.service.verify_port_released("127.0.0.1", ui01_port)


def test_ui02a_static_visual_contract_assets_are_local_and_complete(gateway) -> None:
    html, headers = _text_get_with_headers(f"{gateway.url}/")
    css = _text_get(f"{gateway.url}/assets/theme.css")
    app_js = _text_get(f"{gateway.url}/assets/app.js")
    state_js = _text_get(f"{gateway.url}/assets/state.js")
    icons = _text_get(f"{gateway.url}/assets/icons.svg")
    combined = "\n".join([html, css, app_js, state_js, icons]).lower().replace("http://www.w3.org/2000/svg", "")

    assert headers["Content-Security-Policy"] == CSP
    assert "jarvis quant" in html.lower()
    assert html.count(LIVE_TRADING_STATUS) == 1
    assert "icons.svg#icon-emblem" in html
    assert "/assets/icons.svg#" in app_js
    assert all(f'id="icon-{name}"' in icons for name in ("overview", "research", "shield", "events", "moonshot"))
    assert all(token in css for token in ("--bg: #020611", "--cyan: #2ee9ff", "--amber: #ffb547", "--red: #ff5b73"))
    assert all(marker in css for marker in ("@media (max-width: 1280px)", "@media (max-width: 1040px)", "@media (max-width: 760px)", "prefers-reduced-motion"))
    assert AUTH_VALUE not in html + css + app_js + state_js + icons
    for forbidden in ("https://", "http://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"):
        assert forbidden not in combined


def test_ui02a_overview_hierarchy_and_collapsed_diagnostics_are_declared() -> None:
    app_js = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    for marker in (
        "Market Regime",
        "Risk Gate",
        "Opportunity Radar",
        "Portfolio and Exposure",
        "Wealth Engine",
        "Moonshot Engine",
        "Market / System Data",
        "Signal-Strength Distribution",
        "Exposure Allocation",
        "Provider Validation",
        "Local Service Health",
        "Human Review",
        "Event Stream",
        "Safe Mode",
        "Overview Diagnostics",
    ):
        assert marker in app_js

    assert "<details" not in html.lower()
    assert 'details.className = "panel diagnostics' in app_js
    assert "JSON.stringify(payload, null, 2)" in app_js


@pytest.mark.parametrize("route,label,endpoint", ROUTES)
def test_ui02a_routes_keep_polished_local_shell(gateway, route: str, label: str, endpoint: str) -> None:
    body = _text_get(f"{gateway.url}/route/{route}")

    assert "JARVIS QUANT" in body
    assert LIVE_TRADING_STATUS in body
    assert "/assets/theme.css" in body
    assert "/assets/icons.svg#icon-emblem" in body


def test_ui02a_provider_pending_non_live_and_mutations_blocked(gateway) -> None:
    payload = json.loads(_text_get(f"{gateway.url}/gateway/api/v1/safety"))

    assert payload["provider_validation_status"] == "pending"
    assert payload["safety_state"]["live_trading_enabled"] is False
    assert payload["data"]["is_live"] is False
    assert all(_method_status(f"{gateway.url}/gateway/api/v1/research", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"))


def test_ui02a_sse_static_contract_prevents_hot_reconnect_loop() -> None:
    app_js = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    state_js = (STATIC_ROOT / "state.js").read_text(encoding="utf-8")

    assert app_js.count("new EventSource(") == 1
    assert "activeEventSource.close()" in app_js
    assert "markFixtureComplete" in app_js
    assert "setTimeout(connectEvents, delay)" in app_js
    assert "500)" not in app_js
    assert "MAX_REJECT_COUNT = 25" in state_js
    assert "MAX_ACCEPTED_IDS = 96" in state_js
    assert "repeatedFixtureHeartbeat" in state_js
    assert "heartbeat_refresh" in state_js


def test_ui02a_visual_shell_self_test_script_prints_sanitized_result() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui02a_visual_shell_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "ui02a-self-test-local-session-token" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "ui02a.visual_shell_self_test.v1"
    assert payload["provider_validation_status"] == "pending"
    assert payload["is_live"] is False
    assert payload["live_trading_status"] == LIVE_TRADING_STATUS
    assert all(payload["checks"].values())


def _text_get(url: str) -> str:
    text, _headers = _text_get_with_headers(url)
    return text


def _text_get_with_headers(url: str) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8"), dict(response.headers)


def _method_status(url: str, method: str) -> int:
    request = urllib.request.Request(url, data=b"{}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
