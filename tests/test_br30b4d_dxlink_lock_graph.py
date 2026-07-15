from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from pathlib import Path

from tools.dxlink_lock_graph_validator import (
    EXPECTED_RUNTIME_DEPENDENCIES,
    IMPORT_PROBE_PACKAGES,
    NPM_CI_COMMAND,
    NPM_LOCK_REGEN_COMMAND,
    PACKAGE_JSON,
    PACKAGE_JSON_SHA256,
    PACKAGE_LOCK,
    PRODUCTION_PREFLIGHT_COMMAND,
    REQUIRED_DXLINK_PACKAGES,
    SDK_PACKAGE,
    SDK_VERSION,
    validate_dxlink_lock_graph,
)


def test_br30b4d_lock_graph_accepts_exact_offline_regenerated_closure() -> None:
    report = validate_dxlink_lock_graph()

    assert report.ok is True
    assert report.code == "pass"
    assert report.required_package_count == 5
    assert report.package_count == 6
    assert report.dependency_edge_count == 8


def test_br30b4d_package_json_remains_byte_for_byte_unchanged() -> None:
    import hashlib

    assert hashlib.sha256(PACKAGE_JSON.read_bytes()).hexdigest() == PACKAGE_JSON_SHA256
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package["dependencies"] == {SDK_PACKAGE: SDK_VERSION}
    assert package["dependencies"][SDK_PACKAGE] == "0.3.0"


def test_br30b4d_required_dxlink_packages_are_locked_exactly() -> None:
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

    assert lock["lockfileVersion"] == 3
    assert lock["requires"] is True
    for package_name, version in REQUIRED_DXLINK_PACKAGES.items():
        record = lock["packages"][f"node_modules/{package_name}"]
        assert record["version"] == version
        assert record["resolved"].startswith("https://registry.npmjs.org/")
        assert record["integrity"].startswith("sha512-")


def test_br30b4d_dependency_closure_matches_required_direct_transitives() -> None:
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

    assert lock["packages"][""]["dependencies"] == {SDK_PACKAGE: SDK_VERSION}
    for package_name, expected_dependencies in EXPECTED_RUNTIME_DEPENDENCIES.items():
        record = lock["packages"][f"node_modules/{package_name}"]
        assert record.get("dependencies", {}) == expected_dependencies


def test_br30b4d_validator_rejects_incomplete_malformed_and_disagreeing_locks() -> None:
    tmp_path = _repo_tmp_dir("incomplete")
    package_path, lock_path = _copy_package_and_lock(tmp_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    del lock["packages"]["node_modules/@dxfeed/dxlink-core"]
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "dependency_closure_incomplete"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "bad_format")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["lockfileVersion"] = 2
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "lockfile_format_invalid"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "disagree")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"][""]["dependencies"][SDK_PACKAGE] = "0.3.1"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "package_lock_disagreement"


def test_br30b4d_validator_rejects_unexpected_versions_names_and_remote_types() -> None:
    tmp_path = _repo_tmp_dir("unexpected")
    package_path, lock_path = _copy_package_and_lock(tmp_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@dxfeed/dxlink-api"]["version"] = "0.3.1"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "unexpected_package_version"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "extra")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/left-pad"] = {
        "version": "1.3.0",
        "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
        "integrity": "sha512-placeholder",
    }
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "unexpected_package_name"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "remote")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@dxfeed/dxlink-api"]["resolved"] = "git+ssh://example.invalid/repo"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "unexpected_remote_type"


def test_br30b4d_validator_rejects_missing_integrity_sensitive_metadata_and_cycles() -> None:
    tmp_path = _repo_tmp_dir("metadata")
    package_path, lock_path = _copy_package_and_lock(tmp_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    del lock["packages"]["node_modules/@dxfeed/dxlink-api"]["integrity"]
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "integrity_missing"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "secret")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@dxfeed/dxlink-api"]["client_secret"] = "redacted"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "sensitive_metadata_detected"

    package_path, lock_path = _copy_package_and_lock(tmp_path / "cycle")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@dxfeed/dxlink-core"]["dependencies"] = {SDK_PACKAGE: SDK_VERSION}
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert validate_dxlink_lock_graph(package_path, lock_path).code == "dependency_metadata_mismatch"


def test_br30b4d_npm_commands_are_offline_ignore_scripts_and_never_update() -> None:
    assert NPM_LOCK_REGEN_COMMAND == (
        "npm",
        "install",
        "--package-lock-only",
        "--offline",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    )
    assert NPM_CI_COMMAND == (
        "npm",
        "ci",
        "--offline",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
        "--omit=dev",
    )
    assert "update" not in NPM_LOCK_REGEN_COMMAND
    assert "update" not in NPM_CI_COMMAND


def test_br30b4d_import_probes_and_production_preflight_reuse_are_fixed() -> None:
    assert IMPORT_PROBE_PACKAGES == tuple(REQUIRED_DXLINK_PACKAGES)
    assert "scripts/run_br30b4c_dxlink_runtime_preflight.py" in PRODUCTION_PREFLIGHT_COMMAND[-1]


def test_br30b4d_disabled_state_flags_remain_documented() -> None:
    doc = Path("docs/brendan_strategy/br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.md").read_text(
        encoding="utf-8"
    )

    for line in (
        "real_paper_wrapper_connected=false",
        "real_paper_wrapper_attempted=false",
        "real_paper_order_submitted=false",
        "broker_order_call_performed=false",
        "live_trading_enabled=false",
        "LIVE TRADING: DISABLED",
    ):
        assert line in doc


def _copy_package_and_lock(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    package_path = tmp_path / "package.json"
    lock_path = tmp_path / "package-lock.json"
    shutil.copyfile(PACKAGE_JSON, package_path)
    lock = deepcopy(json.loads(PACKAGE_LOCK.read_text(encoding="utf-8")))
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    return package_path, lock_path


def _repo_tmp_dir(name: str) -> Path:
    path = Path(".codex_pytest_tmp") / f"br30b4d_{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
