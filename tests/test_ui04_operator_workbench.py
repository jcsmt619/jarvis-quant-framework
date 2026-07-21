from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ui02_desktop_shell.constants import CSP, LIVE_TRADING_STATUS
from ui02_desktop_shell.gateway import GatewayConfig, run_gateway

AUTH_VALUE = "deterministic-ui04-test-token"
UI04_ROUTES = ("risk-gate", "portfolio", "alerts", "models", "performance", "backtests", "paper-activity", "options", "moonshot-research")


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
        assert not instance.thread or not instance.thread.is_alive()


@pytest.mark.parametrize("route", UI04_ROUTES)
def test_ui04_routes_return_canonical_disabled_operator_view_model(gateway, route: str) -> None:
    payload, headers = _json_get_with_headers(f"{gateway.url}/gateway/api/v1/{route}")
    ui04 = payload["data"]["ui04"]

    assert headers["Content-Security-Policy"] == CSP
    assert ui04["schema_version"] == "ui04.operator_workbench.view_model.v1"
    assert ui04["provider_validation_status"] == "pending"
    assert ui04["is_live"] is False
    assert ui04["live_trading_status"] == LIVE_TRADING_STATUS
    assert ui04["freshness"]["state"] in {"stale", "no-data"}
    assert ui04["validation_state"] in {"partial-evidence", "no-data"}
    assert set(ui04["safety_labels"]) >= {"RESEARCH_ONLY", "MONITOR_ONLY", "PAPER_ONLY", "HUMAN_REVIEW_REQUIRED", "BLOCKED_BY_SAFETY_GATE"}
    assert payload["safety_state"]["live_trading_enabled"] is False
    assert payload["safety_state"]["broker_order_call_performed"] is False
    assert payload["safety_state"]["real_paper_wrapper_connected"] is False
    assert payload["safety_state"]["real_paper_wrapper_attempted"] is False
    assert payload["safety_state"]["real_paper_order_submitted"] is False


def test_ui04_workbench_content_truthful_states(gateway) -> None:
    risk = _json_get(f"{gateway.url}/gateway/api/v1/risk-gate")["data"]["ui04"]["risk_gate"]
    portfolio = _json_get(f"{gateway.url}/gateway/api/v1/portfolio")["data"]["ui04"]["portfolio"]
    alerts = _json_get(f"{gateway.url}/gateway/api/v1/alerts")["data"]["ui04"]["alerts"]
    models = _json_get(f"{gateway.url}/gateway/api/v1/models")["data"]["ui04"]["models"]
    performance = _json_get(f"{gateway.url}/gateway/api/v1/performance")["data"]["ui04"]["performance"]
    backtests = _json_get(f"{gateway.url}/gateway/api/v1/backtests")["data"]["ui04"]["backtests"]
    paper = _json_get(f"{gateway.url}/gateway/api/v1/paper-activity")["data"]["ui04"]["paper_activity"]
    options = _json_get(f"{gateway.url}/gateway/api/v1/options")["data"]["ui04"]["options"]
    moonshot = _json_get(f"{gateway.url}/gateway/api/v1/moonshot-research")["data"]["ui04"]["moonshot_research"]

    assert risk["decision"] == "BLOCKED_BY_SAFETY_GATE"
    assert "provider_validation_pending" in risk["blocked_reasons"]
    assert portfolio["wealth_engine"]["state"] == "separate"
    assert portfolio["moonshot_engine"]["state"] == "separate"
    assert portfolio["cash"]["state"] == "unavailable"
    assert all(item["human_review_required"] for item in alerts)
    assert models[0]["promotion_eligibility"] == "blocked"
    assert models[0]["drift_state"] == "unavailable"
    assert performance["return_series"]["state"] == "unavailable"
    assert "do_not_infer_performance_from_incomplete_outcomes" in performance["warnings"]
    assert backtests[0]["promotion_gate_state"] == "blocked"
    assert backtests[0]["insufficient_trade_warning"] == "trade_count_unavailable"
    assert "live_order_routing" in paper[0]["rejected_actions"]
    assert options["chain_quality_state"] == "no-data"
    assert options["delta"] == "unavailable"
    assert all(item["risk_state"] in {"HUMAN_REVIEW_REQUIRED", "BLOCKED_BY_SAFETY_GATE"} for item in moonshot)


def test_ui04_static_assets_security_responsive_tables_and_no_mutations() -> None:
    html = Path("ui02_desktop_shell/static/index.html").read_text(encoding="utf-8")
    css = Path("ui02_desktop_shell/static/theme.css").read_text(encoding="utf-8")
    state_js = Path("ui02_desktop_shell/static/state.js").read_text(encoding="utf-8")
    app_js = Path("ui02_desktop_shell/static/app.js").read_text(encoding="utf-8")
    combined = "\n".join([html, css, state_js, app_js]).lower()

    for marker in ("normalizeUi04Envelope", "renderRiskGate", "renderPortfolio", "renderAlerts", "renderModels", "renderPerformance", "renderBacktests", "renderPaperActivity", "renderOptions", "renderMoonshotResearch", "tablePanel"):
        assert marker in app_js + state_js
    for forbidden_control in ("Approve</button>", "Submit</button>", "Execute</button>", "Route</button>", "Ack</button>", "Dismiss</button>"):
        assert forbidden_control not in app_js
    assert "route controls" in app_js
    assert "table-layout: auto" in css
    assert ".table-scroll { overflow-x: auto" in css
    assert "readableLabel" in app_js
    assert "new EventSource(" in app_js and app_js.count("new EventSource(") == 1
    assert "<details" not in html.lower()
    for forbidden in ("https://", "http://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"):
        assert forbidden not in combined
    assert AUTH_VALUE.lower() not in combined


def test_ui04_gateway_security_overview_and_cli_independence(gateway) -> None:
    base = gateway.url
    html, headers = _text_get_with_headers(f"{base}/")
    sse = _text_get(f"{base}/gateway/api/v1/events?after=0")
    health = _json_get(f"{base}/gateway/api/v1/health")

    assert headers["Content-Security-Policy"] == CSP
    assert LIVE_TRADING_STATUS in html
    assert "event: heartbeat" in sse
    assert "event: system_health_updated" in sse
    assert _method_status(f"{base}/gateway/api/v1/risk-gate", "POST") == 405
    assert _method_status(f"{base}/gateway/api/v1/paper-activity", "DELETE") == 405
    assert _status(f"{base}/gateway/api/v1/risk-gate?mutate=true") == 400
    assert health["data"]["ui_required_for_engine_operation"] is False
    assert AUTH_VALUE not in html + sse + json.dumps(health)


def test_ui04_self_test_script_prints_sanitized_bounded_result() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui04_operator_workbench_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=25,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "ui04-self-test-local-session-token" not in result.stdout
    assert len(result.stdout) < 14000
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "ui04.operator_workbench_self_test.v1"
    assert payload["provider_validation_status"] == "pending"
    assert payload["is_live"] is False
    assert payload["live_trading_status"] == LIVE_TRADING_STATUS
    assert all(payload["checks"].values())


def _json_get(url: str) -> dict[str, object]:
    payload, _headers = _json_get_with_headers(url)
    return payload


def _json_get_with_headers(url: str) -> tuple[dict[str, object], dict[str, str]]:
    text, headers = _text_get_with_headers(url)
    return json.loads(text), headers


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


def _status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
