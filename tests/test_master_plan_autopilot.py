from __future__ import annotations

import json
from pathlib import Path


def test_master_plan_queue_exists_and_starts_at_10d() -> None:
    queue_path = Path("config/jarvis_master_plan_queue.json")
    assert queue_path.exists()

    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))

    assert queue[0]["phase"] == "10D"
    assert queue[0]["title"] == "Safety Scanner"
    assert len(queue) >= 10


def test_master_plan_queue_entries_have_required_fields() -> None:
    queue = json.loads(Path("config/jarvis_master_plan_queue.json").read_text(encoding="utf-8-sig"))

    required = {"phase", "title", "branch", "commit_message", "spec"}

    for entry in queue:
        assert required.issubset(entry)
        assert entry["branch"].startswith("agent/")
        assert entry["commit_message"]
        assert "live trading" in entry["spec"].lower() or "research" in entry["spec"].lower() or "safety" in entry["spec"].lower()


def test_master_plan_autopilot_script_exists_and_uses_safe_tools() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "tools\\jarvis_codex_exec.py" in text or "tools/jarvis_codex_exec.py" in text
    assert "run_jarvis_phase_checkpoint.ps1" in text
    assert "run_jarvis_supervised_repair_checkpoint.ps1" in text
    assert "workspace-write" in text
    assert "AutoRepairWithCodex" in text
    assert "MergeToMain" in text


def test_master_plan_autopilot_has_explicit_execute_gate() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "Autopilot did not execute because -Execute was not supplied." in text
    assert "if (-not $Execute" in text
    assert "DryRun" in text


def test_master_plan_autopilot_safety_boundaries_are_present() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "Do not touch .env." in text
    assert "Do not enable live trading." in text
    assert "Do not submit broker orders." in text
    assert "Do not add broker order routing." in text
    assert "Use only approved research-state labels and safety-gate classifications." in text
    assert ("BUY_" + "NOW") not in text
    assert ("SELL_" + "NOW") not in text
    assert ("EXECUTE_" + "TRADE") not in text
    assert ("AUTO_" + "TRADE") not in text


def test_master_plan_autopilot_avoids_known_bad_patterns() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "--ask-for-approval" not in text
    assert "--approval-policy" not in text
    assert "git add ." not in text


def test_master_plan_reports_are_ignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")

    assert "reports/master_plan_autopilot/" in text


def test_master_plan_queue_file_has_no_utf8_bom() -> None:
    raw = Path("config/jarvis_master_plan_queue.json").read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")


def test_master_plan_autopilot_uses_repo_root_parent_directory() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $PSScriptRoot ".."' in text
    assert 'Join-Path $PSScriptRoot "."' not in text


def test_master_plan_autopilot_handles_missing_codex_log_on_wrapper_crash() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "Codex log was not created" in text
    assert "Test-Path $codexLog" in text


def test_master_plan_autopilot_salvages_nonzero_codex_changes() -> None:
    text = Path(
        "scripts/run_jarvis_master_plan_autopilot.ps1"
    ).read_text(encoding="utf-8")

    exit_capture = "$codexExitCode = $LASTEXITCODE"
    discovery = "$changedPaths = Get-ChangedPathsForCheckpoint"
    nonzero_gate = "if ($codexExitCode -ne 0)"
    empty_gate = "if ($changedPaths.Count -eq 0)"
    salvage_marker = (
        "Codex returned non-zero after writing changes; "
        "continuing to checkpoint validation."
    )
    no_change_failure = (
        "without producing checkpointable changes. STOP."
    )

    assert exit_capture in text
    assert discovery in text
    assert nonzero_gate in text
    assert empty_gate in text
    assert salvage_marker in text
    assert no_change_failure in text

    assert text.index(exit_capture) < text.index(discovery)
    assert text.index(discovery) < text.index(nonzero_gate)
