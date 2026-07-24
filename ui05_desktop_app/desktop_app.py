from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ui02_desktop_shell.constants import HOST, LIVE_TRADING_STATUS, SHELL_SCHEMA_VERSION
from ui02_desktop_shell.gateway import GatewayConfig, UI02GatewayServer, run_gateway

APP_VERSION = "UI-05.0"
APP_SCHEMA_VERSION = "ui05.desktop_app.v1"
LOCK_NAME = "jarvis-ui05-desktop.lock"
LOG_NAME = "jarvis-ui05.log"
MAX_LOG_BYTES = 64 * 1024
MAX_LOG_BACKUPS = 3
STALE_LOCK_SECONDS = 12 * 60 * 60
MAX_RESTARTS = 2
HEALTH_TIMEOUT_SECONDS = 5.0
SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"(?i)(token|secret|password|authorization|api[_-]?key)\s*[:=]\s*[^,\s}]+"),
    re.compile(r"[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
)


@dataclass(frozen=True)
class BrowserCandidate:
    name: str
    path: Path


@dataclass(frozen=True)
class LockState:
    path: Path
    exists: bool
    stale: bool
    owner_pid: int | None
    reason: str


@dataclass
class DesktopAppConfig:
    repo_root: Path
    host: str = HOST
    port: int = 0
    source_mode: str = "fixture"
    open_window: bool = True
    app_data_dir: Path | None = None
    browser_profile_dir: Path | None = None
    browser_path: Path | None = None
    dry_run: bool = False
    restart_limit: int = MAX_RESTARTS

    def resolved_app_data_dir(self) -> Path:
        return self.app_data_dir or default_app_data_dir()


class SingleInstanceLock:
    def __init__(self, path: Path, *, now: Callable[[], float] = time.time) -> None:
        self.path = path
        self.now = now
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = inspect_lock(self.path, now=self.now)
        if state.exists and state.stale:
            self.path.unlink(missing_ok=True)
        elif state.exists:
            raise RuntimeError("ui05_desktop_app_already_running")
        payload = {
            "schema_version": APP_SCHEMA_VERSION,
            "pid": os.getpid(),
            "created_at": self.now(),
            "repo_root": str(Path.cwd().resolve()),
            "live_trading_status": LIVE_TRADING_STATUS,
        }
        fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
        self.acquired = True

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


class SanitizedRotatingLog:
    def __init__(self, path: Path, *, max_bytes: int = MAX_LOG_BYTES) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: object) -> None:
        self._rotate_if_needed()
        payload = {
            "schema_version": APP_SCHEMA_VERSION,
            "event": sanitize_log_text(event),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "live_trading_status": LIVE_TRADING_STATUS,
        }
        for key, value in fields.items():
            if key.lower() in {"token", "authorization", "password", "secret", "api_key"}:
                payload[key] = "[REDACTED]"
            else:
                payload[key] = sanitize_log_text(str(value))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

    def tail(self, limit: int = 40) -> list[str]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [sanitize_log_text(line) for line in lines[-max(1, min(limit, 200)):]]

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return
        for index in range(MAX_LOG_BACKUPS - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f".{index}")
            dst = self.path.with_suffix(self.path.suffix + f".{index + 1}")
            if src.exists():
                if index + 1 > MAX_LOG_BACKUPS:
                    src.unlink(missing_ok=True)
                else:
                    src.replace(dst)
        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))


class DesktopAppSupervisor:
    def __init__(self, config: DesktopAppConfig) -> None:
        self.config = config
        self.repo_root = config.repo_root.resolve()
        self.app_data_dir = config.resolved_app_data_dir()
        self.lock = SingleInstanceLock(self.app_data_dir / LOCK_NAME)
        self.log = SanitizedRotatingLog(self.app_data_dir / "logs" / LOG_NAME)
        self.server: UI02GatewayServer | None = None
        self.browser_process: subprocess.Popen[bytes] | None = None
        self.browser_profile_dir: Path | None = None
        self.restart_count = 0
        self.owned_gateway_port: int | None = None
        self.owned_ui01_port: int | None = None
        self.state = "stopped"

    def startup_health(self) -> dict[str, object]:
        checks = {
            "repo_root_exists": self.repo_root.is_dir(),
            "launcher_path_exists": (self.repo_root / "scripts" / "run_ui05_desktop_app.py").is_file(),
            "loopback_only": is_loopback_host(self.config.host),
            "source_mode_safe": self.config.source_mode in {"fixture", "recorded_response"},
            "port_available": port_available(self.config.host, self.config.port) if self.config.port else True,
            "provider_validation_status": "pending",
            "is_live": False,
            "live_trading_status": LIVE_TRADING_STATUS,
        }
        healthy = (
            checks["repo_root_exists"] is True
            and checks["launcher_path_exists"] is True
            and checks["loopback_only"] is True
            and checks["source_mode_safe"] is True
            and checks["port_available"] is True
            and checks["provider_validation_status"] == "pending"
            and checks["is_live"] is False
            and checks["live_trading_status"] == LIVE_TRADING_STATUS
        )
        return {
            "schema_version": APP_SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "state": "healthy" if healthy else "failed",
            "checks": checks,
        }

    def start(self) -> dict[str, object]:
        self._validate_startup()
        self.lock.acquire()
        atexit.register(self.shutdown)
        self.state = "starting"
        self.log.write("startup_begin", source_mode=self.config.source_mode, port=self.config.port or "ephemeral")
        try:
            self.server = self._start_gateway_with_retries()
            self.owned_gateway_port = self.server.port
            self.owned_ui01_port = self.server.ui01.port
            self._verify_health()
            if self.config.open_window and not self.config.dry_run:
                self.browser_process = self._launch_browser()
            self.state = "running"
            self.log.write("startup_complete", gateway_port=self.owned_gateway_port, ui01_port=self.owned_ui01_port)
            return self.status()
        except Exception:
            self.shutdown()
            raise

    def run_until_stopped(self) -> int:
        self.start()
        try:
            while True:
                if self.browser_process is not None and self.browser_process.poll() is not None:
                    self.state = "stopped"
                    return 0
                if self.server and not self._service_healthy():
                    if not self._restart_owned_gateway():
                        return 1
                time.sleep(0.5)
        except KeyboardInterrupt:
            return 0
        finally:
            self.shutdown()

    def status(self) -> dict[str, object]:
        gateway_state = "running" if self.server else "stopped"
        window_state = "not_opened"
        if self.browser_process is not None:
            window_state = "running" if self.browser_process.poll() is None else "closed"
        return {
            "schema_version": APP_SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "state": self.state,
            "local_service_state": "running" if self.server and self.server.ui01.thread and self.server.ui01.thread.is_alive() else "stopped",
            "gateway_state": gateway_state,
            "event_stream_state": "fixture_complete_or_connected",
            "source_mode": self.config.source_mode,
            "provider_validation_status": "pending",
            "is_live": False,
            "restart_count": self.restart_count,
            "window_state": window_state,
            "url": self.server.url if self.server else "",
            "live_trading_status": LIVE_TRADING_STATUS,
        }

    def shutdown(self) -> None:
        if self.state in {"stopping", "stopped"}:
            return
        self.state = "stopping"
        self.log.write("shutdown_begin")
        if self.browser_process is not None and self.browser_process.poll() is None:
            self.browser_process.terminate()
            try:
                self.browser_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.browser_process.kill()
        if self.server is not None:
            self.server.stop()
            self.server = None
        if self.browser_profile_dir is not None:
            shutil.rmtree(self.browser_profile_dir, ignore_errors=True)
            self.browser_profile_dir = None
        self.lock.release()
        self.state = "stopped"
        self.log.write("shutdown_complete")

    def _validate_startup(self) -> None:
        health = self.startup_health()
        if health["state"] != "healthy":
            raise RuntimeError("ui05_startup_health_failed")

    def _start_gateway_with_retries(self) -> UI02GatewayServer:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return run_gateway(GatewayConfig(host=self.config.host, port=self.config.port, source_mode=self.config.source_mode))
            except Exception as exc:
                last_error = exc
                self.log.write("gateway_start_retry", attempt=attempt + 1, error=exc.__class__.__name__)
                time.sleep(0.15 * (attempt + 1))
        raise RuntimeError("ui05_gateway_start_failed") from last_error

    def _verify_health(self) -> None:
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._service_healthy():
                return
            time.sleep(0.1)
        raise RuntimeError("ui05_gateway_health_failed")

    def _service_healthy(self) -> bool:
        if self.server is None:
            return False
        try:
            with urllib.request.urlopen(f"{self.server.url}/gateway/api/v1/health", timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return (
                response.status == 200
                and payload.get("provider_validation_status") == "pending"
                and payload.get("safety_state", {}).get("is_live") is False
                and payload.get("safety_state", {}).get("live_trading_status") == LIVE_TRADING_STATUS
            )
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return False

    def _restart_owned_gateway(self) -> bool:
        if self.restart_count >= self.config.restart_limit:
            self.state = "failed"
            self.log.write("restart_limit_reached", restart_count=self.restart_count)
            return False
        self.restart_count += 1
        self.log.write("gateway_restart", restart_count=self.restart_count)
        if self.server is not None:
            self.server.stop()
        self.server = self._start_gateway_with_retries()
        self.owned_gateway_port = self.server.port
        self.owned_ui01_port = self.server.ui01.port
        return self._service_healthy()

    def _launch_browser(self) -> subprocess.Popen[bytes] | None:
        candidate = BrowserCandidate("explicit", self.config.browser_path) if self.config.browser_path else discover_browser()
        if candidate is None:
            self.log.write("browser_fallback_default")
            webbrowser.open(self.server.url + "/", new=1, autoraise=True)
            return None
        profile = self.config.browser_profile_dir or Path(tempfile.mkdtemp(prefix="jarvis-ui05-profile-"))
        profile.mkdir(parents=True, exist_ok=True)
        self.browser_profile_dir = profile
        args = browser_app_arguments(candidate.path, self.server.url + "/", profile)
        self.log.write("browser_launch", browser=candidate.name)
        return subprocess.Popen(args, cwd=str(self.repo_root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def default_app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / "JarvisQuant" / "UI05"


def is_loopback_host(host: str) -> bool:
    return host == HOST


def port_available(host: str, port: int) -> bool:
    if not is_loopback_host(host) or not (0 < int(port) <= 65535):
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind((host, int(port)))
        except OSError:
            return False
    return True


def inspect_lock(path: Path, *, now: Callable[[], float] = time.time) -> LockState:
    if not path.exists():
        return LockState(path=path, exists=False, stale=False, owner_pid=None, reason="missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid", 0)) or None
        created_at = float(payload.get("created_at", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return LockState(path=path, exists=True, stale=True, owner_pid=None, reason="malformed")
    if pid and _pid_running(pid):
        return LockState(path=path, exists=True, stale=False, owner_pid=pid, reason="owner_running")
    age = now() - created_at if created_at else STALE_LOCK_SECONDS + 1
    return LockState(path=path, exists=True, stale=age >= 0, owner_pid=pid, reason="owner_missing")


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def discover_browser(extra_paths: Iterable[Path] | None = None) -> BrowserCandidate | None:
    candidates: list[tuple[str, Path]] = []
    candidates.extend((("edge", path) for path in _edge_paths()))
    candidates.extend((("chrome", path) for path in _chrome_paths()))
    if extra_paths:
        candidates.extend(("custom", path) for path in extra_paths)
    for name, path in candidates:
        if path and path.is_file():
            return BrowserCandidate(name=name, path=path)
    return None


def _edge_paths() -> list[Path]:
    roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
    return [Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe" for root in roots if root]


def _chrome_paths() -> list[Path]:
    roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
    return [Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe" for root in roots if root]


def browser_app_arguments(browser_path: Path, url: str, profile_dir: Path) -> list[str]:
    if "token" in url.lower() or "authorization" in url.lower():
        raise ValueError("ui05_refuses_secret_bearing_url")
    return [
        str(browser_path),
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-sync",
    ]


def sanitize_log_text(value: str) -> str:
    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized[:2000]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Jarvis UI-05 Windows desktop app. LIVE TRADING: DISABLED.")
    sub = parser.add_subparsers(dest="command")
    launch = sub.add_parser("launch")
    launch.add_argument("--port", type=int, default=0)
    launch.add_argument("--fixture", action="store_true")
    launch.add_argument("--recorded-response", action="store_true")
    launch.add_argument("--no-open", action="store_true")
    launch.add_argument("--health-only", action="store_true")
    launch.add_argument("--app-data-dir", type=Path)
    launch.add_argument("--browser-profile-dir", type=Path)
    launch.add_argument("--dry-run", action="store_true")
    sub.add_parser("startup-health")
    sub.add_parser("inspect-lock")
    sub.add_parser("clean-shutdown")
    logs = sub.add_parser("logs")
    logs.add_argument("--limit", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "launch"
    repo_root = Path(__file__).resolve().parents[1]
    if command in {"startup-health", "inspect-lock", "clean-shutdown", "logs"}:
        config = DesktopAppConfig(repo_root=repo_root)
        app_dir = config.resolved_app_data_dir()
        if command == "startup-health":
            print(json.dumps(DesktopAppSupervisor(config).startup_health(), sort_keys=True))
            return 0
        if command == "inspect-lock":
            state = inspect_lock(app_dir / LOCK_NAME)
            print(json.dumps({"schema_version": APP_SCHEMA_VERSION, "exists": state.exists, "stale": state.stale, "reason": state.reason, "live_trading_status": LIVE_TRADING_STATUS}, sort_keys=True))
            return 0
        if command == "clean-shutdown":
            state = inspect_lock(app_dir / LOCK_NAME)
            if state.exists and state.stale:
                state.path.unlink(missing_ok=True)
            print(json.dumps({"schema_version": APP_SCHEMA_VERSION, "stale_lock_removed": state.exists and state.stale, "live_trading_status": LIVE_TRADING_STATUS}, sort_keys=True))
            return 0
        log = SanitizedRotatingLog(app_dir / "logs" / LOG_NAME)
        print(json.dumps({"schema_version": APP_SCHEMA_VERSION, "lines": log.tail(args.limit), "live_trading_status": LIVE_TRADING_STATUS}, sort_keys=True))
        return 0

    source_mode = "recorded_response" if args.recorded_response else "fixture"
    config = DesktopAppConfig(
        repo_root=repo_root,
        port=args.port,
        source_mode=source_mode,
        open_window=not args.no_open,
        app_data_dir=args.app_data_dir,
        browser_profile_dir=args.browser_profile_dir,
        dry_run=args.dry_run,
    )
    supervisor = DesktopAppSupervisor(config)
    if args.health_only:
        print(json.dumps(supervisor.startup_health(), sort_keys=True))
        return 0
    if args.dry_run:
        print(json.dumps(supervisor.start(), sort_keys=True))
        supervisor.shutdown()
        return 0
    return supervisor.run_until_stopped()


if __name__ == "__main__":
    raise SystemExit(main())
