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

AUTH_VALUE = "deterministic-ui03-test-token"
UI03_ROUTES = ("research", "screener", "opportunities", "analyst-theses", "market-regime", "lifecycle")


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


@pytest.mark.parametrize("route", UI03_ROUTES)
def test_ui03_routes_return_canonical_view_model_and_disabled_safety(gateway, route: str) -> None:
    payload, headers = _json_get_with_headers(f"{gateway.url}/gateway/api/v1/{route}")
    ui03 = payload["data"]["ui03"]

    assert headers["Content-Security-Policy"] == CSP
    assert payload["provider_validation_status"] == "pending"
    assert payload["safety_state"]["is_live"] is False
    assert payload["safety_state"]["live_trading_enabled"] is False
    assert payload["safety_state"]["broker_order_call_performed"] is False
    assert payload["safety_state"]["real_paper_wrapper_connected"] is False
    assert payload["safety_state"]["real_paper_wrapper_attempted"] is False
    assert payload["safety_state"]["real_paper_order_submitted"] is False
    assert payload["safety_state"]["live_trading_status"] == LIVE_TRADING_STATUS
    assert ui03["schema_version"] == "ui03.research_workbench.view_model.v1"
    assert ui03["provider_validation_status"] == "pending"
    assert ui03["is_live"] is False
    assert ui03["live_trading_status"] == LIVE_TRADING_STATUS
    assert ui03["provenance"]["validation_state"] in {"partial-evidence", "blocked"}
    assert ui03["freshness"]["state"] in {"stale", "no-data"}


def test_ui03_research_screener_opportunity_thesis_regime_and_lifecycle_content(gateway) -> None:
    research = _json_get(f"{gateway.url}/gateway/api/v1/research")["data"]["ui03"]
    screener = _json_get(f"{gateway.url}/gateway/api/v1/screener")["data"]["ui03"]
    opportunities = _json_get(f"{gateway.url}/gateway/api/v1/opportunities")["data"]["ui03"]
    theses = _json_get(f"{gateway.url}/gateway/api/v1/analyst-theses")["data"]["ui03"]
    regime = _json_get(f"{gateway.url}/gateway/api/v1/market-regime")["data"]["ui03"]
    lifecycle = _json_get(f"{gateway.url}/gateway/api/v1/lifecycle")["data"]["ui03"]

    assert research["research"]["status"] == "HUMAN_REVIEW_REQUIRED"
    assert "Do not claim alpha" in " ".join(research["research"]["human_review_requirements"])
    assert len(screener["candidates"]) == 3
    assert all("rank" in item and "risk_state" in item and "evidence_refs" in item for item in screener["candidates"])
    assert opportunities["opportunities"][0]["required_human_action"]
    assert theses["theses"][0]["confidence"] is None
    assert theses["theses"][0]["uncertainty"]
    assert regime["status"] == "unavailable"
    assert regime["market_regime"]["confidence"] is None
    assert lifecycle["lifecycle"]["stage_counts"]["paper_only"] == 2
    assert lifecycle["lifecycle"]["allowed_transitions"]


def test_ui03_static_assets_have_workflows_no_storage_no_external_refs() -> None:
    html = Path("ui02_desktop_shell/static/index.html").read_text(encoding="utf-8")
    css = Path("ui02_desktop_shell/static/theme.css").read_text(encoding="utf-8")
    state_js = Path("ui02_desktop_shell/static/state.js").read_text(encoding="utf-8")
    app_js = Path("ui02_desktop_shell/static/app.js").read_text(encoding="utf-8")
    combined = "\n".join([html, css, state_js, app_js]).lower()

    for marker in (
        "renderResearchWorkbench",
        "renderScreener",
        "renderOpportunities",
        "renderTheses",
        "renderMarketRegime",
        "renderLifecycle",
        "candidateDetailPanel",
        "filterCandidates",
        "sortCandidates",
        "selectedCandidateId",
        "diagnosticsPanel(found[1] + \" Diagnostics\", payload, true)",
    ):
        assert marker in app_js + state_js
    assert "Opportunity Radar is a read-only review queue" in app_js
    assert "Market regime is unavailable unless committed evidence supports it." in app_js
    assert "new EventSource(" in app_js and app_js.count("new EventSource(") == 1
    assert "<details" not in html.lower()
    for forbidden in ("https://", "http://", "//cdn", "googleapis", "analytics", "telemetry", "localstorage", "sessionstorage", "indexeddb", "serviceworker", "eval(", "new function"):
        assert forbidden not in combined
    assert AUTH_VALUE.lower() not in combined


def test_ui03_security_gateway_sse_and_cli_independence(gateway) -> None:
    base = gateway.url
    html, headers = _text_get_with_headers(f"{base}/")
    sse = _text_get(f"{base}/gateway/api/v1/events?after=0")
    safety = _json_get(f"{base}/gateway/api/v1/safety")
    health = _json_get(f"{base}/gateway/api/v1/health")

    assert headers["Content-Security-Policy"] == CSP
    assert LIVE_TRADING_STATUS in html
    assert "event: heartbeat" in sse
    assert "event: system_health_updated" in sse
    assert _method_status(f"{base}/gateway/api/v1/research", "POST") == 405
    assert _status(f"{base}/gateway/api/v1/research?mutate=true") == 400
    assert _status(f"{base}/gateway/http://example.test/api/v1/research") == 403
    assert health["data"]["ui_required_for_engine_operation"] is False
    assert safety["provider_validation_status"] == "pending"
    assert safety["data"]["is_live"] is False
    assert AUTH_VALUE not in html + sse + json.dumps(safety)


def test_ui03_self_test_script_prints_sanitized_bounded_result() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui03_research_workbench_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=25,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "ui03-self-test-local-session-token" not in result.stdout
    assert len(result.stdout) < 12000
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "ui03.research_workbench_self_test.v1"
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
