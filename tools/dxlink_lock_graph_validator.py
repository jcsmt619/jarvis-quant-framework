from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DXLINK_DIR = REPO_ROOT / "integrations" / "tastytrade_dxlink"
PACKAGE_JSON = DXLINK_DIR / "package.json"
PACKAGE_LOCK = DXLINK_DIR / "package-lock.json"
PACKAGE_JSON_SHA256 = "7b35c3621d068317c84a5b84feff30a4a6129c8a81dbbf224cb14b6576a941bc"
ROOT_PACKAGE_NAME = "jarvis-tastytrade-dxlink-read-only-sidecar"
SDK_PACKAGE = "@dxfeed/dxlink-api"
SDK_VERSION = "0.3.0"

REQUIRED_DXLINK_PACKAGES: dict[str, str] = {
    "@dxfeed/dxlink-api": "0.3.0",
    "@dxfeed/dxlink-core": "0.3.0",
    "@dxfeed/dxlink-dom": "0.3.0",
    "@dxfeed/dxlink-feed": "0.3.0",
    "@dxfeed/dxlink-websocket-client": "0.3.0",
}

EXPECTED_RUNTIME_DEPENDENCIES: dict[str, dict[str, str]] = {
    "@dxfeed/dxlink-api": {
        "@dxfeed/dxlink-core": "0.3.0",
        "@dxfeed/dxlink-dom": "0.3.0",
        "@dxfeed/dxlink-feed": "0.3.0",
        "@dxfeed/dxlink-websocket-client": "0.3.0",
    },
    "@dxfeed/dxlink-core": {},
    "@dxfeed/dxlink-dom": {"@dxfeed/dxlink-core": "0.3.0"},
    "@dxfeed/dxlink-feed": {"@dxfeed/dxlink-core": "0.3.0"},
    "@dxfeed/dxlink-websocket-client": {"@dxfeed/dxlink-core": "0.3.0"},
}

NPM_LOCK_REGEN_COMMAND = (
    "npm",
    "install",
    "--package-lock-only",
    "--offline",
    "--ignore-scripts",
    "--no-audit",
    "--no-fund",
)
NPM_CI_COMMAND = (
    "npm",
    "ci",
    "--offline",
    "--ignore-scripts",
    "--no-audit",
    "--no-fund",
    "--omit=dev",
)
IMPORT_PROBE_PACKAGES = tuple(REQUIRED_DXLINK_PACKAGES)
PRODUCTION_PREFLIGHT_COMMAND = (
    sys.executable,
    "scripts/run_br30b4c_dxlink_runtime_preflight.py",
)

PACKAGE_RECORD_FIELDS = {"version", "resolved", "integrity", "license", "dependencies", "engines"}
ROOT_RECORD_FIELDS = {"name", "version", "dependencies", "engines", "license"}
SENSITIVE_MARKERS = (
    "access_token",
    "refresh_token",
    "client_secret",
    "oauth",
    "password",
    "private_key",
    "apikey",
    "api_key",
    "quote_token",
    "quote-token",
    "account_id",
    "account-number",
    "customer_id",
    "authorization",
    "bearer ",
)


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    code: str
    package_count: int
    dependency_edge_count: int
    required_package_count: int
    runtime_checks: tuple[str, ...] = ()

    def sanitized(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "package_count": self.package_count,
            "dependency_edge_count": self.dependency_edge_count,
            "required_package_count": self.required_package_count,
            "runtime_checks": list(self.runtime_checks),
        }


class LockGraphValidationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_dxlink_lock_graph(
    package_json_path: Path = PACKAGE_JSON,
    package_lock_path: Path = PACKAGE_LOCK,
) -> ValidationReport:
    try:
        package_bytes = package_json_path.read_bytes()
        lock_bytes = package_lock_path.read_bytes()
        if sha256(package_bytes).hexdigest() != PACKAGE_JSON_SHA256:
            raise LockGraphValidationError("package_json_changed")
        package = json.loads(package_bytes.decode("utf-8"))
        lock = json.loads(lock_bytes.decode("utf-8"))
        _reject_sensitive_fields(package)
        _reject_sensitive_fields(lock)
        package_count, edge_count = _validate_graph(package, lock)
        return ValidationReport(
            ok=True,
            code="pass",
            package_count=package_count,
            dependency_edge_count=edge_count,
            required_package_count=len(REQUIRED_DXLINK_PACKAGES),
        )
    except LockGraphValidationError as error:
        return ValidationReport(
            ok=False,
            code=error.code,
            package_count=0,
            dependency_edge_count=0,
            required_package_count=len(REQUIRED_DXLINK_PACKAGES),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ValidationReport(
            ok=False,
            code="metadata_malformed",
            package_count=0,
            dependency_edge_count=0,
            required_package_count=len(REQUIRED_DXLINK_PACKAGES),
        )


def run_full_dxlink_lock_graph_check() -> ValidationReport:
    static_report = validate_dxlink_lock_graph()
    if not static_report.ok:
        return static_report

    checks: list[str] = []
    _run_sanitized(NPM_CI_COMMAND, DXLINK_DIR, "npm_ci_failed")
    checks.append("npm_ci_offline")
    _verify_installed_manifests()
    checks.append("installed_manifests")
    _run_import_probe(esm=True)
    checks.append("esm_import_probe")
    _run_import_probe(esm=False)
    checks.append("commonjs_dynamic_import_probe")
    _run_preflight_probe()
    checks.append("production_preflight")

    return ValidationReport(
        ok=True,
        code="pass",
        package_count=static_report.package_count,
        dependency_edge_count=static_report.dependency_edge_count,
        required_package_count=static_report.required_package_count,
        runtime_checks=tuple(checks),
    )


def _validate_graph(package: dict[str, Any], lock: dict[str, Any]) -> tuple[int, int]:
    if not isinstance(package, dict) or not isinstance(lock, dict):
        raise LockGraphValidationError("metadata_malformed")
    if package.get("name") != ROOT_PACKAGE_NAME or package.get("private") is not True:
        raise LockGraphValidationError("package_json_changed")
    if package.get("dependencies") != {SDK_PACKAGE: SDK_VERSION}:
        raise LockGraphValidationError("package_json_dependency_mismatch")
    if lock.get("lockfileVersion") != 3 or lock.get("requires") is not True:
        raise LockGraphValidationError("lockfile_format_invalid")
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise LockGraphValidationError("lockfile_format_invalid")
    root = packages.get("")
    if not isinstance(root, dict):
        raise LockGraphValidationError("root_package_missing")
    if root.get("name") != ROOT_PACKAGE_NAME or root.get("version") != "0.0.0":
        raise LockGraphValidationError("root_package_mismatch")
    if root.get("dependencies") != package["dependencies"]:
        raise LockGraphValidationError("package_lock_disagreement")

    locked_names: dict[str, str] = {}
    edge_count = 0
    for entry_path, record in packages.items():
        if not isinstance(record, dict):
            raise LockGraphValidationError("package_record_malformed")
        allowed_fields = ROOT_RECORD_FIELDS if entry_path == "" else PACKAGE_RECORD_FIELDS
        if set(record) - allowed_fields:
            raise LockGraphValidationError("package_record_malformed")
        if entry_path == "":
            continue
        name = _name_from_lock_path(entry_path)
        locked_names[name] = entry_path
        if name not in REQUIRED_DXLINK_PACKAGES:
            raise LockGraphValidationError("unexpected_package_name")
        if record.get("version") != REQUIRED_DXLINK_PACKAGES[name]:
            raise LockGraphValidationError("unexpected_package_version")
        _validate_resolved_artifact(name, record)
        deps = record.get("dependencies", {})
        if deps != EXPECTED_RUNTIME_DEPENDENCIES[name]:
            raise LockGraphValidationError("dependency_metadata_mismatch")
        edge_count += len(deps)

    if set(locked_names) != set(REQUIRED_DXLINK_PACKAGES):
        raise LockGraphValidationError("dependency_closure_incomplete")

    visited: set[str] = set()
    stack: set[str] = set()
    _walk_dependency(SDK_PACKAGE, locked_names, packages, visited, stack)
    if visited != set(REQUIRED_DXLINK_PACKAGES):
        raise LockGraphValidationError("dependency_closure_incomplete")
    return len(packages), edge_count + 1


def _walk_dependency(
    name: str,
    locked_names: dict[str, str],
    packages: dict[str, Any],
    visited: set[str],
    stack: set[str],
) -> None:
    if name in stack:
        raise LockGraphValidationError("dependency_cycle_detected")
    entry_path = locked_names.get(name)
    if not entry_path:
        raise LockGraphValidationError("dependency_closure_incomplete")
    stack.add(name)
    visited.add(name)
    deps = packages[entry_path].get("dependencies", {})
    if not isinstance(deps, dict):
        raise LockGraphValidationError("dependency_metadata_mismatch")
    for dependency_name, dependency_version in deps.items():
        if dependency_version != REQUIRED_DXLINK_PACKAGES.get(dependency_name):
            raise LockGraphValidationError("dependency_metadata_mismatch")
        _walk_dependency(dependency_name, locked_names, packages, visited, stack)
    stack.remove(name)


def _name_from_lock_path(entry_path: str) -> str:
    prefix = "node_modules/"
    if not entry_path.startswith(prefix) or "\\" in entry_path:
        raise LockGraphValidationError("package_record_malformed")
    return entry_path[len(prefix) :]


def _validate_resolved_artifact(name: str, record: dict[str, Any]) -> None:
    resolved = record.get("resolved")
    integrity = record.get("integrity")
    if not isinstance(resolved, str):
        raise LockGraphValidationError("resolved_artifact_missing")
    if not resolved.startswith("https://registry.npmjs.org/"):
        raise LockGraphValidationError("unexpected_remote_type")
    if any(marker in resolved for marker in ("git+", "ssh://", "file:", "http://")):
        raise LockGraphValidationError("unexpected_remote_type")
    if f"/{name.split('/')[-1]}-{SDK_VERSION}.tgz" not in resolved:
        raise LockGraphValidationError("unexpected_remote_type")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise LockGraphValidationError("integrity_missing")


def _reject_sensitive_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_sensitive_string(str(key))
            _reject_sensitive_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_fields(item)
    elif isinstance(value, str):
        _reject_sensitive_string(value)


def _reject_sensitive_string(value: str) -> None:
    lowered = value.lower()
    if any(marker in lowered for marker in SENSITIVE_MARKERS):
        raise LockGraphValidationError("sensitive_metadata_detected")


def _verify_installed_manifests() -> None:
    for name, expected_version in REQUIRED_DXLINK_PACKAGES.items():
        manifest = DXLINK_DIR / "node_modules" / Path(*name.split("/")) / "package.json"
        try:
            package = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise LockGraphValidationError("installed_manifest_missing") from None
        if package.get("name") != name or package.get("version") != expected_version:
            raise LockGraphValidationError("installed_manifest_mismatch")


def _run_import_probe(*, esm: bool) -> None:
    package_list = json.dumps(list(IMPORT_PROBE_PACKAGES))
    if esm:
        command = ("node", "--input-type=module", "-e", f"await Promise.all({package_list}.map((name) => import(name)));")
        code = "esm_import_probe_failed"
    else:
        command = ("node", "-e", f"Promise.all({package_list}.map((name) => import(name))).catch(() => process.exit(1));")
        code = "commonjs_import_probe_failed"
    _run_sanitized(command, DXLINK_DIR, code)


def _run_preflight_probe() -> None:
    completed = _run_sanitized(PRODUCTION_PREFLIGHT_COMMAND, REPO_ROOT, "production_preflight_failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise LockGraphValidationError("production_preflight_failed") from None
    if payload != {
        "ok": True,
        "sdk": SDK_PACKAGE,
        "contract": SDK_VERSION,
        "connection_attempted": False,
        "credentials_accepted": False,
    }:
        raise LockGraphValidationError("production_preflight_failed")


def _run_sanitized(command: tuple[str, ...], cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
    env = _sanitized_runtime_environment()
    resolved_command = _resolve_windows_command(command, env)
    try:
        completed = subprocess.run(
            resolved_command,
            cwd=cwd,
            text=True,
            input="",
            capture_output=True,
            timeout=60,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LockGraphValidationError(failure_code) from None
    if completed.returncode != 0:
        raise LockGraphValidationError(failure_code)
    return completed


def _resolve_windows_command(command: tuple[str, ...], env: dict[str, str]) -> tuple[str, ...]:
    if os.name != "nt":
        return command
    executable = command[0]
    if executable.lower() == "npm":
        resolved = shutil.which("npm.cmd", path=env.get("PATH") or env.get("Path"))
        if resolved:
            return (resolved, *command[1:])
    return command


def _sanitized_runtime_environment() -> dict[str, str]:
    keep = (
        "PATH",
        "Path",
        "PATHEXT",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    )
    env: dict[str, str] = {}
    for key in keep:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["NODE_NO_WARNINGS"] = "1"
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the BR-30B4D DXLink lock graph.")
    parser.add_argument("--runtime", action="store_true", help="also run offline npm ci, import probes, and preflight")
    args = parser.parse_args(argv)

    try:
        report = run_full_dxlink_lock_graph_check() if args.runtime else validate_dxlink_lock_graph()
    except LockGraphValidationError as error:
        report = ValidationReport(
            ok=False,
            code=error.code,
            package_count=0,
            dependency_edge_count=0,
            required_package_count=len(REQUIRED_DXLINK_PACKAGES),
        )
    sys.stdout.write(json.dumps(report.sanitized(), sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
