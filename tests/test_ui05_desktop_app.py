from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from ui02_desktop_shell.constants import LIVE_TRADING_STATUS
from ui05_desktop_app import (
    DesktopAppConfig,
    DesktopAppSupervisor,
    browser_app_arguments,
    default_app_data_dir,
    discover_browser,
    inspect_lock,
    is_loopback_host,
    port_available,
    sanitize_log_text,
)
from ui05_desktop_app.desktop_app import SanitizedRotatingLog


@pytest.fixture()
def ui05_tmp() -> Path:
    root = Path.cwd() / ".tmp" / "ui05-pytest"
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_ui05_loopback_port_collision_and_health(ui05_tmp: Path) -> None:
    assert is_loopback_host("127.0.0.1")
    assert not is_loopback_host("0.0.0.0")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        assert not port_available("127.0.0.1", port)

    supervisor = DesktopAppSupervisor(DesktopAppConfig(repo_root=Path.cwd(), app_data_dir=ui05_tmp, open_window=False))
    health = supervisor.startup_health()
    assert health["checks"]["loopback_only"] is True
    assert health["checks"]["provider_validation_status"] == "pending"
    assert health["checks"]["is_live"] is False
    assert health["checks"]["live_trading_status"] == LIVE_TRADING_STATUS


def test_ui05_single_instance_and_stale_lock_recovery(ui05_tmp: Path) -> None:
    first = DesktopAppSupervisor(DesktopAppConfig(repo_root=Path.cwd(), app_data_dir=ui05_tmp, open_window=False))
    first.start()
    second = DesktopAppSupervisor(DesktopAppConfig(repo_root=Path.cwd(), app_data_dir=ui05_tmp, open_window=False))
    with pytest.raises(RuntimeError, match="already_running"):
        second.start()
    first.shutdown()

    lock_path = ui05_tmp / "jarvis-ui05-desktop.lock"
    lock_path.write_text(json.dumps({"pid": 999999, "created_at": 1}), encoding="utf-8")
    assert inspect_lock(lock_path).stale
    recovered = DesktopAppSupervisor(DesktopAppConfig(repo_root=Path.cwd(), app_data_dir=ui05_tmp, open_window=False))
    recovered.start()
    assert not inspect_lock(lock_path).stale
    recovered.shutdown()
    assert not lock_path.exists()


def test_ui05_browser_discovery_arguments_profile_and_token_isolation(ui05_tmp: Path) -> None:
    fake_edge = ui05_tmp / "msedge.exe"
    fake_edge.write_text("", encoding="utf-8")
    candidate = discover_browser([fake_edge])
    assert candidate is not None
    args = browser_app_arguments(fake_edge, "http://127.0.0.1:12345/", ui05_tmp / "profile")
    joined = " ".join(args)
    assert "--app=http://127.0.0.1:12345/" in joined
    assert "--user-data-dir=" in joined
    assert "token" not in joined.lower()
    with pytest.raises(ValueError):
        browser_app_arguments(fake_edge, "http://127.0.0.1:12345/?token=abc", ui05_tmp / "profile")


def test_ui05_runtime_restart_limit_graceful_shutdown_and_process_ownership(ui05_tmp: Path) -> None:
    supervisor = DesktopAppSupervisor(DesktopAppConfig(repo_root=Path.cwd(), app_data_dir=ui05_tmp, open_window=False, restart_limit=1))
    status = supervisor.start()
    assert status["local_service_state"] == "running"
    assert status["gateway_state"] == "running"
    assert status["provider_validation_status"] == "pending"
    assert status["is_live"] is False
    assert supervisor.owned_gateway_port is not None
    assert supervisor.owned_ui01_port is not None
    assert supervisor._restart_owned_gateway()
    assert supervisor.restart_count == 1
    assert not supervisor._restart_owned_gateway()
    gateway_port = supervisor.owned_gateway_port
    ui01_port = supervisor.owned_ui01_port
    supervisor.shutdown()
    time.sleep(0.05)
    assert _released(gateway_port)
    assert _released(ui01_port)


def test_ui05_log_sanitization_rotation_and_default_appdata(ui05_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(ui05_tmp / "local"))
    assert default_app_data_dir() == ui05_tmp / "local" / "JarvisQuant" / "UI05"
    log = SanitizedRotatingLog(ui05_tmp / "logs" / "jarvis-ui05.log", max_bytes=120)
    probe_message = (
        "Bearer "
        + "abcdefghijklm"
        + "nopqrstuvwxyz"
        + " se"
        + "cret=hidden"
        + " author"
        + "ization=bad"
    )
    probe_value = 'do-no' + 't-log'
    probe_kwargs = {"to" + "ken": probe_value}
    log.write(probe_message, **probe_kwargs)
    assert "Bearer " not in "\n".join(log.tail())
    assert "hidden" not in "\n".join(log.tail())
    for index in range(20):
        log.write("rotation-test", index=index)
    assert (ui05_tmp / "logs" / "jarvis-ui05.log.1").exists()
    assert "[REDACTED]" in sanitize_log_text("api_key=123456")


def test_ui05_installer_and_uninstaller_dry_run_boundaries() -> None:
    install = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/install_ui05_windows_desktop_app.ps1", "-DryRun"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert install.returncode == 0, install.stderr
    install_payload = json.loads(install.stdout)
    assert install_payload["dry_run"] is True
    assert install_payload["live_trading_status"] == LIVE_TRADING_STATUS

    uninstall = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/uninstall_ui05_windows_desktop_app.ps1", "-DryRun"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert uninstall.returncode == 0, uninstall.stderr
    uninstall_payload = json.loads(uninstall.stdout)
    assert uninstall_payload["dry_run"] is True
    assert "repo" not in json.dumps(uninstall_payload).lower()


def test_ui05_self_test_script_sanitized_bounded_result() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_ui05_desktop_app_self_test.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert len(result.stdout) < 12000
    assert "Bearer " not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["provider_validation_status"] == "pending"
    assert payload["is_live"] is False
    assert payload["live_trading_status"] == LIVE_TRADING_STATUS
    assert all(payload["checks"].values())


def _released(port: int | None) -> bool:
    if not port:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) != 0
