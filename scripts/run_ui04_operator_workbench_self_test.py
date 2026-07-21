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

AUTH_VALUE = "ui04-self-test-local-session-token"
UI04_ROUTES = ("risk-gate", "portfolio", "alerts", "models", "performance", "backtests", "paper-activity", "options", "moonshot-research")


def main() -> int:
    server = run_gateway(GatewayConfig(port=0, source_mode="fixture", local_session_token=AUTH_VALUE))
    output: dict[str, object] = {
        "schema_version": "ui04.operator_workbench_self_test.v1",
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

        route_payloads = {route: _json_get(f"{base}/gateway/api/v1/{route}") for route in UI04_ROUTES}
        risk = route_payloads["risk-gate"]["data"]["ui04"]["risk_gate"]
        portfolio = route_payloads["portfolio"]["data"]["ui04"]["portfolio"]
        alerts = route_payloads["alerts"]["data"]["ui04"]["alerts"]
        models = route_payloads["models"]["data"]["ui04"]["models"]
        performance = route_payloads["performance"]["data"]["ui04"]["performance"]
        backtests = route_payloads["backtests"]["data"]["ui04"]["backtests"]
        paper = route_payloads["paper-activity"]["data"]["ui04"]["paper_activity"]
        options = route_payloads["options"]["data"]["ui04"]["options"]
        moonshot = route_payloads["moonshot-research"]["data"]["ui04"]["moonshot_research"]
        overview_payloads = {route: _json_get(f"{base}/gateway/api/v1/{route}") for route in ("health", "safety", "data-status", "research", "portfolio", "alerts", "models", "risk-gate", "moonshot-research")}
        sse = _text_get(f"{base}/gateway/api/v1/events?after=0")
        replay = _text_get(f"{base}/gateway/api/v1/events", headers={"Last-Event-ID": "5"})

        checks["loopback_only"] = base.startswith("http://127.0.0.1:")
        checks["all_nine_ui04_routes"] = all(_status(f"{base}/route/{route}") == 200 and "ui04" in route_payloads[route]["data"] for route in UI04_ROUTES)
        checks["overview_integrations"] = all(marker in app_js for marker in ("riskGateVm", "portfolioVm", "alertsVm", "moonshotVm", "Model Health"))
        checks["risk_gate"] = risk["decision"] == "BLOCKED_BY_SAFETY_GATE" and "provider_validation_pending" in risk["blocked_reasons"] and risk["human_review_requirement"] == "HUMAN_REVIEW_REQUIRED"
        checks["portfolio_engine_separation"] = portfolio["wealth_engine"]["state"] == "separate" and portfolio["moonshot_engine"]["state"] == "separate"
        checks["alerts"] = len(alerts) >= 2 and all(item["human_review_required"] for item in alerts)
        checks["model_validation_and_drift"] = models[0]["validation_state"] == "partial-evidence" and models[0]["drift_state"] == "unavailable"
        checks["performance_no_data"] = performance["return_series"]["state"] == "unavailable" and "do_not_infer_performance_from_incomplete_outcomes" in performance["warnings"]
        checks["backtest_evidence_and_warnings"] = backtests[0]["promotion_gate_state"] == "blocked" and backtests[0]["insufficient_trade_warning"] == "trade_count_unavailable"
        checks["paper_activity_read_only"] = "live_order_routing" in paper[0]["rejected_actions"] and "renderPaperActivity" in app_js
        checks["options_no_data"] = options["chain_quality_state"] == "no-data" and options["delta"] == "unavailable"
        checks["moonshot_separation_and_review"] = all(item["engine"] == "Moonshot Engine" for item in moonshot) and any(item["risk_state"] == "HUMAN_REVIEW_REQUIRED" for item in moonshot)
        checks["ui03_responsive_table_corrections"] = all(marker in css + app_js for marker in ("table-layout: auto", "overflow-x: auto", "readableLabel", "td:first-child"))
        checks["collapsed_diagnostics"] = "<details" not in html.lower() and "diagnosticsPanel(found[1] + \" Diagnostics\", payload, true)" in app_js
        checks["one_sse_connection"] = app_js.count("new EventSource(") == 1
        checks["fixture_completion_no_hot_loop"] = "markFixtureComplete" in app_js and "setTimeout(connectEvents, delay)" in app_js and "MAX_RECONNECTS" in state_js
        checks["restrictive_csp"] = headers.get("Content-Security-Policy") == CSP and "'unsafe-inline'" not in headers.get("Content-Security-Policy", "")
        checks["no_external_references"] = not any(marker in lowered for marker in ("https://", "http://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"))
        checks["token_isolation"] = AUTH_VALUE not in fetched_text + sse + replay + json.dumps(output)
        checks["unsupported_methods_fail_closed"] = all(_method_status(f"{base}/gateway/api/v1/risk-gate", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"))
        checks["provider_pending"] = all(payload["provider_validation_status"] == "pending" for payload in route_payloads.values())
        checks["is_live_false"] = all(payload["safety_state"]["is_live"] is False and payload["data"]["ui04"]["is_live"] is False for payload in route_payloads.values())
        checks["live_trading_disabled"] = all(payload["safety_state"]["live_trading_enabled"] is False and payload["safety_state"]["live_trading_status"] == LIVE_TRADING_STATUS for payload in route_payloads.values())
        checks["sse_fixture_completion"] = all(fragment in sse + replay for fragment in ("event: heartbeat", "event: system_health_updated", "provider_validation_status"))
        checks["cli_independence"] = overview_payloads["health"]["data"]["ui_required_for_engine_operation"] is False
    except Exception as exc:
        output["errors"] = [{"code": "ui04_self_test_failed", "message": exc.__class__.__name__}]
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
        print(json.dumps({"schema_version": "ui04.operator_workbench_self_test.v1", "errors": [{"code": "sanitization_failed"}]}, sort_keys=True))
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
