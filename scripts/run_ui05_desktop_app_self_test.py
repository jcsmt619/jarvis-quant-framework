from __future__ import annotations

import json
import socket
import sys
import time
import urllib.request
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui02_desktop_shell.constants import LIVE_TRADING_STATUS, ROUTES
from ui05_desktop_app import DesktopAppConfig, DesktopAppSupervisor, inspect_lock


def main() -> int:
    output: dict[str, object] = {
        "schema_version": "ui05.desktop_app_self_test.v1",
        "source_mode": "fixture",
        "provider_validation_status": "pending",
        "is_live": False,
        "live_trading_status": LIVE_TRADING_STATUS,
        "checks": {},
        "errors": [],
    }
    temp_root = ROOT / ".tmp" / "ui05-self-test"
    run_root = temp_root / uuid.uuid4().hex
    app_dir = run_root / "appdata"
    profile_dir = run_root / "profile"
    app_dir.mkdir(parents=True, exist_ok=False)
    profile_dir.mkdir(parents=True, exist_ok=False)
    try:
        supervisor = DesktopAppSupervisor(
            DesktopAppConfig(
                repo_root=ROOT,
                source_mode="fixture",
                open_window=False,
                app_data_dir=app_dir,
                browser_profile_dir=profile_dir,
            )
        )
        checks = output["checks"]
        assert isinstance(checks, dict)
        fetched = ""
        try:
            health = supervisor.startup_health()
            checks["startup_health"] = health["state"] == "healthy"
            status = supervisor.start()
            base = str(status["url"])
            fetched = "\n".join(_text_get(f"{base}/route/{route_id}") for route_id, _label, _endpoint in ROUTES)
            fetched += "\n" + _text_get(f"{base}/assets/app.js") + "\n" + _text_get(f"{base}/assets/theme.css")
            route_payloads = {route_id: _json_get(f"{base}/gateway/api/v1/{endpoint}") for route_id, _label, endpoint in ROUTES}
            checks["loopback_only"] = base.startswith("http://127.0.0.1:")
            checks["all_routes_present"] = all(_status(f"{base}/route/{route_id}") == 200 for route_id, _label, _endpoint in ROUTES)
            checks["ui03_ui04_modules_present"] = all(marker in fetched for marker in ("renderScreener", "renderBacktests", "renderModels", "renderPaperActivity", "renderOptions", "renderAlerts"))
            checks["responsive_table_markers"] = all(marker in fetched for marker in ("data-responsive-table", "compact-card-mode", "table-card-grid", "tabular-nums"))
            checks["no_vertical_fragmentation_contract"] = "word-break: normal" in fetched and "overflow-wrap: anywhere" in fetched and "status-chip" in fetched
            checks["card_mode"] = "@media (max-width: 760px)" in fetched and ".table-card-grid" in fetched
            checks["single_instance_rejection"] = _single_instance_rejected(app_dir)
            supervisor.shutdown()
            stale = app_dir / "jarvis-ui05-desktop.lock"
            stale.write_text(json.dumps({"pid": 999999, "created_at": 1}), encoding="utf-8")
            stale_supervisor = DesktopAppSupervisor(DesktopAppConfig(repo_root=ROOT, open_window=False, app_data_dir=app_dir))
            stale_supervisor.start()
            checks["stale_lock_recovery"] = not inspect_lock(stale).stale
            checks["bounded_restart_behavior"] = stale_supervisor.restart_count <= stale_supervisor.config.restart_limit
            payload = _json_get(f"{stale_supervisor.server.url}/gateway/api/v1/health") if stale_supervisor.server else {}
            checks["provider_pending"] = payload.get("provider_validation_status") == "pending"
            checks["is_live_false"] = payload.get("safety_state", {}).get("is_live") is False
            checks["live_trading_disabled"] = payload.get("safety_state", {}).get("live_trading_status") == LIVE_TRADING_STATUS
            gateway_port = stale_supervisor.owned_gateway_port
            ui01_port = stale_supervisor.owned_ui01_port
            stale_supervisor.shutdown()
            time.sleep(0.05)
            checks["port_release"] = _port_released(gateway_port) and _port_released(ui01_port)
            checks["lock_removed"] = not stale.exists()
            checks["profile_cleanup"] = not profile_dir.exists() or not any(profile_dir.iterdir())
            logs = "\n".join((app_dir / "logs" / "jarvis-ui05.log").read_text(encoding="utf-8").splitlines())
            checks["log_sanitization"] = "ui05" in logs and "Authorization" not in logs and "Bearer " not in logs and "secret" not in logs.lower()
            checks["installer_dry_run_no_shortcut"] = not any(app_dir.rglob("*.lnk"))
            checks["no_token_in_output"] = "token" not in fetched.lower()
        except Exception as exc:
            output["errors"] = [{"code": "ui05_self_test_failed", "message": exc.__class__.__name__}]
            supervisor.shutdown()
    finally:
        shutil.rmtree(run_root, ignore_errors=True)

    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0 if all(bool(value) for value in output["checks"].values()) and not output["errors"] else 1


def _single_instance_rejected(app_dir: Path) -> bool:
    other = DesktopAppSupervisor(DesktopAppConfig(repo_root=ROOT, open_window=False, app_data_dir=app_dir))
    try:
        other.start()
    except RuntimeError as exc:
        return "already_running" in str(exc)
    finally:
        other.shutdown()
    return False


def _json_get(url: str) -> dict[str, object]:
    return json.loads(_text_get(url))


def _text_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def _status(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as response:
        response.read()
        return response.status


def _port_released(port: int | None) -> bool:
    if not port:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) != 0


if __name__ == "__main__":
    raise SystemExit(main())
