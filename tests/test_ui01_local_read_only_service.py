from __future__ import annotations

import importlib
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ui_service.constants import FORBIDDEN_IMPORT_PREFIXES, MUTATION_METHODS
from ui_service.events import EventBackbone
from ui_service.http_adapter import run_local_service
from ui_service.service import ServiceConfig

AUTH_VALUE = "deterministic-ui01-test-token"


@pytest.fixture()
def server():
    instance = run_local_service(ServiceConfig(host="127.0.0.1", port=0, source_mode="fixture", local_session_token=AUTH_VALUE, replay_buffer_size=16, subscriber_queue_size=1))
    try:
        yield instance
    finally:
        port = instance.port
        instance.stop()
        assert instance.service.verify_port_released("127.0.0.1", port)
        assert not instance.thread or not instance.thread.is_alive()


def test_ui01_health_is_public_and_read_envelope_is_canonical(server) -> None:
    payload = _json_get(f"{server.url}/api/v1/health")

    assert payload["schema_version"] == "ui01.local_service.v1"
    assert payload["source_mode"] == "fixture"
    assert payload["provider_validation_status"] == "pending"
    assert payload["safety_state"]["live_trading_enabled"] is False
    assert payload["safety_state"]["broker_order_call_performed"] is False
    assert payload["safety_state"]["live_trading_status"] == "LIVE TRADING: DISABLED"
    assert payload["data"]["status"] == "ready"
    assert payload["data"]["is_live"] is False


@pytest.mark.parametrize(
    "endpoint",
    [
        "safety",
        "data-status",
        "research",
        "screener",
        "opportunities",
        "analyst-theses",
        "market-regime",
        "lifecycle",
        "risk-gate",
        "portfolio",
        "alerts",
        "models",
        "performance",
        "backtests",
        "paper-activity",
        "options",
        "moonshot-research",
    ],
)
def test_ui01_all_data_endpoints_require_authorization_and_report_pending_non_live(server, endpoint: str) -> None:
    assert _status(f"{server.url}/api/v1/{endpoint}") == 401

    payload = _json_get(f"{server.url}/api/v1/{endpoint}", headers=_auth())

    assert payload["errors"] == []
    assert payload["provider_validation_status"] == "pending"
    assert payload["data"]["is_live"] is False
    assert payload["data"]["live_trading_status"] == "LIVE TRADING: DISABLED"


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer wrong"])
def test_ui01_authorization_rejects_missing_malformed_and_invalid_without_echo(server, header: str | None) -> None:
    headers = {"Authorization": header} if header else {}
    payload, status = _json_get_with_status(f"{server.url}/api/v1/research", headers=headers)

    assert status == 401
    assert "wrong" not in json.dumps(payload)
    assert "abc" not in json.dumps(payload)
    assert payload["data"]["status"] == "authorization_required"


def test_ui01_authorization_rejects_duplicated_header_without_echo(server) -> None:
    request = urllib.request.Request(f"{server.url}/api/v1/research", method="GET")
    request.add_header("Authorization", f"Bearer {AUTH_VALUE}")
    request.add_header("Authorization", "Bearer duplicate-token")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(request, timeout=5)

    body = exc_info.value.read().decode("utf-8")
    assert exc_info.value.code == 401
    assert "duplicate-token" not in body


@pytest.mark.parametrize("method", sorted(MUTATION_METHODS))
def test_ui01_mutation_methods_fail_closed_with_405(server, method: str) -> None:
    payload, status = _request_json(f"{server.url}/api/v1/research", method=method, data=b'{"ignored":true}')

    assert status == 405
    assert payload["data"]["status"] == "method_not_allowed"
    assert payload["safety_state"]["live_trading_enabled"] is False


def test_ui01_head_options_correlation_and_audit_are_safe(server) -> None:
    head = urllib.request.Request(f"{server.url}/api/v1/research", headers=_auth({"X-Correlation-ID": "corr-ui01-test"}), method="HEAD")
    with urllib.request.urlopen(head, timeout=5) as response:
        assert response.status == 200
        assert response.read() == b""

    options = urllib.request.Request(f"{server.url}/api/v1/research", method="OPTIONS")
    with urllib.request.urlopen(options, timeout=5) as response:
        assert response.status == 204
        assert response.headers["Allow"] == "GET, HEAD, OPTIONS"

    assert _status(f"{server.url}/api/v1/research", headers=_auth({"X-Correlation-ID": "bad id with spaces"})) == 400
    audit = server.service.audit.records[-1]
    assert set(audit) == {
        "created_at",
        "endpoint",
        "method",
        "status",
        "duration_class",
        "request_id",
        "correlation_id",
        "source_mode",
        "authorization_result",
        "safety_state",
    }
    assert "Authorization" not in json.dumps(audit)
    assert AUTH_VALUE not in json.dumps(audit)


def test_ui01_sse_heartbeat_fixture_event_and_last_event_id_replay(server) -> None:
    body = _text_get(f"{server.url}/api/v1/events?after=0", headers=_auth())

    assert "event: heartbeat" in body
    assert "event: system_health_updated" in body
    assert '"schema_version":"ui01.event.v1"' in body

    replay = _text_get(f"{server.url}/api/v1/events", headers=_auth({"Last-Event-ID": "5"}))
    assert "event: risk_gate_updated" in replay or "event: portfolio_snapshot_updated" in replay


def test_ui01_loopback_only_binding_and_live_provider_fail_closed() -> None:
    with pytest.raises(ValueError):
        ServiceConfig(host="0.0.0.0").validate()
    with pytest.raises(ValueError):
        ServiceConfig(host=socket.gethostbyname(socket.gethostname())).validate()

    instance = run_local_service(ServiceConfig(host="127.0.0.1", port=0, source_mode="live_provider", local_session_token=AUTH_VALUE))
    try:
        payload, status = _json_get_with_status(f"{instance.url}/api/v1/data-status", headers=_auth())
        assert status == 503
        assert payload["data"]["status"] == "unavailable"
        assert payload["data"]["reason"] == "live_provider_mode_unavailable_pending_br30_dxlink_validation"
    finally:
        port = instance.port
        instance.stop()
        assert instance.service.verify_port_released("127.0.0.1", port)


def test_ui01_recorded_response_mode_uses_committed_sanitized_evidence() -> None:
    instance = run_local_service(ServiceConfig(host="127.0.0.1", port=0, source_mode="recorded_response", local_session_token=AUTH_VALUE))
    try:
        payload = _json_get(f"{instance.url}/api/v1/data-status", headers=_auth())
        assert payload["source_mode"] == "recorded_response"
        assert payload["data"]["is_live"] is False
        assert payload["data"]["provider_validation_status"] == "pending"
        assert "br30_tastytrade_recorded_response_valid.json" in json.dumps(payload["data"]["source_artifacts"])
    finally:
        instance.stop()


def test_ui01_event_backbone_ordering_replay_gaps_and_rejections() -> None:
    bus = EventBackbone(buffer_size=3, subscriber_queue_size=1)
    subscriber = bus.subscribe()
    first = bus.publish(event_type="system_health_updated", correlation_id="corr-event-test", payload={"ok": True})
    bus.publish(event_type="data_status_updated", correlation_id="corr-event-test", payload={"ok": True})
    bus.publish(event_type="research_refreshed", correlation_id="corr-event-test", payload={"ok": True})

    assert first.event_id == "evt-ui01-000001"
    assert [event.sequence for event in bus.replay_after(1)]
    assert all(event.sequence > 1 for event in bus.replay_after(1))
    assert any(event.event_type == "stream_gap" for event in bus.replay_after(0))

    with pytest.raises(ValueError, match="duplicate_event_id"):
        bus.publish(event_type="alert_created", correlation_id="corr-event-test", payload={"ok": True}, event_id=first.event_id)
    with pytest.raises(ValueError, match="unsupported_event_type"):
        bus.publish(event_type="order_route_created", correlation_id="corr-event-test", payload={"ok": True})
    with pytest.raises(ValueError, match="secret_bearing_event"):
        bus.publish(event_type="alert_created", correlation_id="corr-event-test", payload={"api_key": "redacted"})
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="future_event"):
        bus.publish(event_type="alert_created", correlation_id="corr-event-test", payload={"ok": True}, occurred_at=future)
    bus.unsubscribe(subscriber)


def test_ui01_import_boundary_does_not_load_credentials_broker_writes_or_execution_modules() -> None:
    before = set(sys.modules)
    importlib.import_module("ui_service")
    imported = set(sys.modules) - before

    assert not any(name == prefix.rstrip(".") or name.startswith(prefix) for name in imported for prefix in FORBIDDEN_IMPORT_PREFIXES)

    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("ui_service").glob("*.py"))
    forbidden_text = [
        "import keyring",
        "import win32cred",
        "from broker",
        "from paper_trading",
        "from execution",
        "_".join(("submit", "order")) + "(",
        "route_order(",
        "dotenv",
    ]
    for marker in forbidden_text:
        assert marker not in source


def test_ui01_self_test_script_prints_sanitized_envelope() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui01_local_service_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert AUTH_VALUE not in result.stdout
    assert "ui01-self-test-token" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "ui01.self_test.v1"
    assert payload["live_trading_status"] == "LIVE TRADING: DISABLED"
    assert payload["port_released"] is True
    assert all(payload["checks"].values())


def test_ui01_service_is_optional_for_existing_cli_imports() -> None:
    import main  # noqa: F401
    import run_all  # noqa: F401

    assert "ui_service" in sys.modules


def _auth(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {AUTH_VALUE}"}
    headers.update(extra or {})
    return headers


def _json_get(url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    payload, status = _json_get_with_status(url, headers=headers)
    assert status == 200
    return payload


def _json_get_with_status(url: str, headers: dict[str, str] | None = None) -> tuple[dict[str, object], int]:
    return _request_json(url, method="GET", headers=headers)


def _request_json(url: str, *, method: str, headers: dict[str, str] | None = None, data: bytes | None = None) -> tuple[dict[str, object], int]:
    request = urllib.request.Request(url, headers=headers or {}, method=method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8") or "{}"), response.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8") or "{}"), exc.code


def _text_get(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8")


def _status(url: str, headers: dict[str, str] | None = None) -> int:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
