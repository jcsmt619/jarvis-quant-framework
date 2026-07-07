from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from automation.safety_scanner import scan_paths


def _fixture_file(name: str) -> Path:
    fixture_dir = Path("reports/safety_scanner_tests")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    if name == ".env":
        nested_dir = fixture_dir / uuid.uuid4().hex
        nested_dir.mkdir(parents=True, exist_ok=True)
        return nested_dir / name
    return fixture_dir / f"{uuid.uuid4().hex}_{name}"


def test_safety_scanner_blocks_live_trading_enablement() -> None:
    candidate = _fixture_file("candidate.py")
    try:
        candidate.write_text("live_trading_" + "enabled = " + "True\n", encoding="utf-8")

        result = scan_paths([candidate])

        assert result.passed is False
        assert result.findings[0].rule_id == "LIVE_TRADING_ENABLEMENT"
    finally:
        candidate.unlink(missing_ok=True)


def test_safety_scanner_blocks_broker_order_submission() -> None:
    candidate = _fixture_file("candidate.py")
    try:
        candidate.write_text("client.submit_" + "order(symbol='EEM')\n", encoding="utf-8")

        result = scan_paths([candidate])

        assert result.passed is False
        assert result.findings[0].rule_id == "BROKER_ORDER_SUBMISSION"
    finally:
        candidate.unlink(missing_ok=True)


def test_safety_scanner_redacts_secret_like_assignments() -> None:
    candidate = _fixture_file("candidate.py")
    try:
        candidate.write_text("API_" + "KEY = 'super-sensitive-value'\n", encoding="utf-8")

        result = scan_paths([candidate])

        assert result.passed is False
        assert result.findings[0].rule_id == "SECRET_ASSIGNMENT_OR_EXPOSURE"
        assert "super-sensitive-value" not in result.findings[0].excerpt
        assert "[REDACTED]" in result.findings[0].excerpt
    finally:
        candidate.unlink(missing_ok=True)


def test_safety_scanner_skips_dotenv_without_reading() -> None:
    env_file = _fixture_file(".env")
    try:
        env_file.write_text("API_" + "KEY = 'do-not-read'\n", encoding="utf-8")

        result = scan_paths([env_file])

        assert result.passed is True
        assert result.scanned_files == 0
        assert any(path.endswith(".env") for path in result.skipped_files)
    finally:
        env_file.unlink(missing_ok=True)


def test_safety_scanner_allows_policy_text() -> None:
    policy = _fixture_file("policy.md")
    try:
        policy.write_text("Do not enable live trading\n", encoding="utf-8")

        result = scan_paths([policy])

        assert result.passed is True
    finally:
        policy.unlink(missing_ok=True)


def test_safety_scanner_cli_blocks_and_prints_gate_label() -> None:
    candidate = _fixture_file("candidate.py")
    try:
        candidate.write_text("paper = " + "False\n", encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, "scripts/check_jarvis_safety_scanner.py", str(candidate)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 1
        assert "JARVIS 10D SAFETY SCANNER: BLOCKED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
    finally:
        candidate.unlink(missing_ok=True)


def test_phase_checkpoint_uses_10d_safety_scanner() -> None:
    text = Path("scripts/run_jarvis_phase_checkpoint.ps1").read_text(encoding="utf-8")

    assert "run_jarvis_safety_scanner.ps1" in text
    assert "-DiffOnly" in text
