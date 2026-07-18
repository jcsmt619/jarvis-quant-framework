from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui_service.http_adapter import run_local_service
from ui_service.service import ServiceConfig


def main() -> int:
    auth_value = "ui01-self-test-token"
    server = run_local_service(ServiceConfig(host="127.0.0.1", port=0, source_mode="fixture", local_session_token=auth_value))
    base = server.url
    results: dict[str, object] = {
        "schema_version": "ui01.self_test.v1",
        "source_mode": "fixture",
        "live_trading_status": "LIVE TRADING: DISABLED",
        "checks": {},
        "warnings": [],
        "errors": [],
    }
    try:
        checks = results["checks"]
        assert isinstance(checks, dict)
        checks["health"] = _json_get(f"{base}/api/v1/health")["data"]["status"] == "ready"
        headers = {"Authorization": f"Bearer {auth_value}", "X-Correlation-ID": "corr-ui01-self-test"}
        for endpoint in ("safety", "data-status", "research", "risk-gate"):
            payload = _json_get(f"{base}/api/v1/{endpoint}", headers=headers)
            checks[endpoint] = payload["provider_validation_status"] == "pending" and payload["safety_state"]["live_trading_enabled"] is False
        sse = _text_get(f"{base}/api/v1/events?after=0", headers=headers)
        checks["sse_heartbeat"] = "event: heartbeat" in sse
        checks["sse_fixture_event"] = "event: system_health_updated" in sse
        replay = _text_get(f"{base}/api/v1/events", headers={**headers, "Last-Event-ID": "5"})
        checks["sse_replay_last_event_id"] = "event:" in replay
        checks["mutations_405"] = all(_method_status(f"{base}/api/v1/research", method) == 405 for method in ("POST", "PUT", "PATCH", "DELETE"))
    except Exception as exc:
        results["errors"] = [{"code": "self_test_failed", "message": exc.__class__.__name__}]
    finally:
        port = server.port
        server.stop()
        time.sleep(0.05)
        results["port_released"] = server.service.verify_port_released("127.0.0.1", port)
    print(json.dumps(results, sort_keys=True, indent=2))
    checks_ok = all(bool(value) for value in results.get("checks", {}).values())
    return 0 if checks_ok and results.get("port_released") and not results.get("errors") else 1


def _json_get(url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    return json.loads(_text_get(url, headers=headers))


def _text_get(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8")


def _method_status(url: str, method: str) -> int:
    request = urllib.request.Request(url, data=b"{}", method=method)
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        return exc.code
    return 200


if __name__ == "__main__":
    raise SystemExit(main())
