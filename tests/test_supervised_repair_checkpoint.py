from __future__ import annotations

from pathlib import Path


def test_supervised_repair_checkpoint_script_exists() -> None:
    assert Path("scripts/run_jarvis_supervised_repair_checkpoint.ps1").exists()


def test_supervised_repair_checkpoint_uses_supervisor_codex_wrapper_and_checkpoint() -> None:
    text = Path("scripts/run_jarvis_supervised_repair_checkpoint.ps1").read_text(encoding="utf-8")

    assert "run_jarvis_openai_supervisor.ps1" in text
    assert "tools\\jarvis_codex_exec.py" in text or "tools/jarvis_codex_exec.py" in text
    assert "run_jarvis_phase_checkpoint.ps1" in text
    assert "AutoRepairWithCodex" in text
    assert "DryRunSupervisor" in text
    assert "PlanOnly" in text
    assert "MaxRepairAttempts" in text


def test_supervised_repair_checkpoint_uses_hashtable_splatting() -> None:
    text = Path("scripts/run_jarvis_supervised_repair_checkpoint.ps1").read_text(encoding="utf-8")

    assert "$supervisorArgs = @{" in text
    assert "$checkpointArgs = @{" in text
    assert "FailedCommand = $CommandText" in text
    assert "ExitCode = [int]$result.ExitCode" in text


def test_supervised_repair_checkpoint_blocks_unsafe_commit_shape() -> None:
    text = Path("scripts/run_jarvis_supervised_repair_checkpoint.ps1").read_text(encoding="utf-8")

    assert "Refusing supervised repair checkpoint commit on main" in text
    assert "ChangedPath is empty" in text
    assert "CommitMessage is empty" in text
    assert "safe_to_patch" in text
    assert "dangerous_action_detected" in text


def test_supervised_repair_checkpoint_avoids_broken_codex_flags_and_bulk_stage() -> None:
    text = Path("scripts/run_jarvis_supervised_repair_checkpoint.ps1").read_text(encoding="utf-8")

    assert "--ask-for-approval" not in text
    assert "--approval-policy" not in text
    assert "git add ." not in text


def test_supervised_repair_reports_are_ignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")

    assert "reports/supervised_repair/" in text
