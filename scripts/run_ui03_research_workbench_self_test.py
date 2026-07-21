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

from ui02_desktop_shell.constants import CSP, LIVE_TRADING_STATUS, SHELL_SCHEMA_VERSION
from ui02_desktop_shell.gateway import GatewayConfig, run_gateway

AUTH_VALUE = "ui03-self-test-local-session-token"
UI03_ROUTES = ("research", "screener", "opportunities", "analyst-theses", "market-regime", "lifecycle")
STATIC_ROOT = ROOT / "ui02_desktop_shell" / "static"


def main() -> int:
    server = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    output: dict[str, object] = {
        "schema_version": "ui03.research_workbench_self_test.v1",
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

        route_payloads = {route: _json_get(f"{base}/gateway/api/v1/{route}") for route in UI03_ROUTES}
        screener = route_payloads["screener"]["data"]["ui03"]
        opportunities = route_payloads["opportunities"]["data"]["ui03"]
        theses = route_payloads["analyst-theses"]["data"]["ui03"]
        regime = route_payloads["market-regime"]["data"]["ui03"]
        lifecycle = route_payloads["lifecycle"]["data"]["ui03"]
        sse = _text_get(f"{base}/gateway/api/v1/events?after=0")
        replay = _text_get(f"{base}/gateway/api/v1/events", headers={"Last-Event-ID": "5"})

        checks["loopback_only"] = base.startswith("http://127.0.0.1:")
        checks["all_six_ui03_routes"] = all(_status(f"{base}/route/{route}") == 200 and "ui03" in route_payloads[route]["data"] for route in UI03_ROUTES)
        checks["overview_integrations"] = all(marker in app_js for marker in ("researchVm", "screenerVm", "opportunitiesVm", "marketRegimeVm", "Opportunity Radar is a read-only review queue"))
        checks["search_sort_filter_selection_detail_links"] = all(marker in app_js for marker in ("filterCandidates", "sortCandidates", "selectedCandidateId", "candidateDetailPanel", "route-links", "Open details"))
        checks["no_data_and_partial_states"] = regime["status"] == "unavailable" and regime["market_regime"]["confidence"] is None and screener["freshness"]["state"] == "stale"
        checks["collapsed_diagnostics"] = "<details" not in html.lower() and "diagnosticsPanel(found[1] + \" Diagnostics\", payload, true)" in app_js
        checks["one_sse_connection"] = app_js.count("new EventSource(") == 1
        checks["fixture_completion_no_hot_loop"] = "markFixtureComplete" in app_js and "setTimeout(connectEvents, delay)" in app_js and "MAX_RECONNECTS" in state_js
        checks["no_external_references"] = not any(marker in lowered for marker in ("https://", "http://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"))
        checks["restrictive_csp"] = headers.get("Content-Security-Policy") == CSP and "'unsafe-inline'" not in headers.get("Content-Security-Policy", "")
        checks["token_isolation"] = AUTH_VALUE not in fetched_text + sse + replay + json.dumps(output)
        checks["unsupported_methods_fail_closed"] = all(_method_status(f"{base}/gateway/api/v1/research", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"))
        checks["provider_pending_is_live_false"] = all(payload["provider_validation_status"] == "pending" and payload["safety_state"]["is_live"] is False for payload in route_payloads.values())
        checks["live_trading_disabled"] = all(payload["safety_state"]["live_trading_enabled"] is False and payload["safety_state"]["live_trading_status"] == LIVE_TRADING_STATUS for payload in route_payloads.values())
        checks["sse_fixture_completion"] = all(fragment in sse + replay for fragment in ("event: heartbeat", "event: system_health_updated", "provider_validation_status"))
        checks["candidate_data_present"] = len(screener["candidates"]) >= 3 and len(opportunities["opportunities"]) >= 3 and len(theses["theses"]) >= 2
        checks["lifecycle_transitions"] = lifecycle["lifecycle"]["allowed_transitions"] and lifecycle["lifecycle"]["stage_counts"]["paper_only"] == 2
        checks["cli_independence"] = _json_get(f"{base}/gateway/api/v1/health")["data"]["ui_required_for_engine_operation"] is False
    except Exception as exc:
        output["errors"] = [{"code": "ui03_self_test_failed", "message": exc.__class__.__name__}]
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
        print(json.dumps({"schema_version": "ui03.research_workbench_self_test.v1", "errors": [{"code": "sanitization_failed"}]}, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    checks_ok = all(bool(value) for value in output.get("checks", {}).values())
    return 0 if checks_ok and not output.get("errors") else 1


def _json_get(url: str) -> dict[str, object]:
    return json.loads(_text_get(url))


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
