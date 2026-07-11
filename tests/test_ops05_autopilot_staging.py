from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from automation.autopilot_staging import (
    GitChange,
    intended_phase_paths,
    is_disposable_untracked_artifact,
    missing_changed_paths,
    normalize_eof_whitespace,
    parse_porcelain_z,
    unexpected_paths,
)


def _workspace_tmp_dir() -> Path:
    path = Path("reports/safety_scanner_tests") / f"ops05_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_parse_porcelain_z_covers_staged_unstaged_rename_delete_and_untracked() -> None:
    raw = (
        b"M  scripts/run.py\0"
        b" M docs/notes.md\0"
        b"R  core/new_name.py\0core/old_name.py\0"
        b" D reports/old.json\0"
        b"?? tests/test_new.py\0"
    )

    changes = parse_porcelain_z(raw)

    assert [change.path for change in changes] == [
        "scripts/run.py",
        "docs/notes.md",
        "core/new_name.py",
        "reports/old.json",
        "tests/test_new.py",
    ]
    assert changes[2].original_path == "core/old_name.py"
    assert changes[3].is_deleted is True
    assert changes[4].is_untracked is True


def test_intended_paths_drop_only_untracked_pytest_and_python_cache_outputs() -> None:
    changes = [
        GitChange(".codex_pytest_tmp/cache/output.json", "?", "?"),
        GitChange("__pycache__/module.cpython-312.pyc", "?", "?"),
        GitChange(".codex_pytest_tmp/fixture/evidence.json", "M", " "),
        GitChange("tests/test_phase.py", "?", "?"),
    ]

    assert is_disposable_untracked_artifact(changes[0]) is True
    assert is_disposable_untracked_artifact(changes[2]) is False
    assert intended_phase_paths(changes) == [
        ".codex_pytest_tmp/fixture/evidence.json",
        "tests/test_phase.py",
    ]


def test_unexpected_paths_reject_partial_staging_but_allow_cache_noise() -> None:
    changes = [
        GitChange("scripts/phase.py", "M", " "),
        GitChange("core/engine.py", "M", " "),
        GitChange("tests/test_phase.py", "?", "?"),
        GitChange(".pytest_cache/v/cache/nodeids", "?", "?"),
    ]

    assert unexpected_paths(changes, ["scripts/phase.py", "tests/test_phase.py"]) == [
        "core/engine.py"
    ]


def test_missing_changed_paths_detect_stale_intended_artifacts() -> None:
    changes = [GitChange("scripts/phase.py", "M", " ")]

    assert missing_changed_paths(changes, ["scripts/phase.py", "docs/report.md"]) == [
        "docs/report.md"
    ]


def test_normalize_eof_whitespace_preserves_lf() -> None:
    repo = _workspace_tmp_dir()
    try:
        target = repo / "lf.py"
        target.write_bytes(b"print('x')\n\n  \t")

        assert normalize_eof_whitespace(repo, ["lf.py"]) == ["lf.py"]
        assert target.read_bytes() == b"print('x')\n"
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_normalize_eof_whitespace_preserves_crlf() -> None:
    repo = _workspace_tmp_dir()
    try:
        target = repo / "crlf.py"
        target.write_bytes(b"line1\r\nline2\r\n\r\n   ")

        assert normalize_eof_whitespace(repo, ["crlf.py"]) == ["crlf.py"]
        assert target.read_bytes() == b"line1\r\nline2\r\n"
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_phase_checkpoint_guards_stage_only_explicit_and_scan_same_paths() -> None:
    text = Path("scripts/run_jarvis_phase_checkpoint.ps1").read_text(encoding="utf-8")

    assert "automation.autopilot_staging validate" in text
    assert "automation.autopilot_staging normalize-eof" in text
    assert "git add @ChangedPath" in text
    assert "run_jarvis_safety_scanner.ps1 -DiffOnly -Path $ChangedPath" in text


def test_master_autopilot_uses_porcelain_guard_for_discovery() -> None:
    text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "automation.autopilot_staging discover" in text
    assert "Assert-CleanGitWorktree" in text
    assert "git diff --name-only" not in text
    assert "git status --porcelain --untracked-files=all" not in text


def test_persistent_orchestrator_has_clean_branch_and_merge_failure_recovery_hooks() -> None:
    text = Path("automation/autonomous_master_plan_orchestrator_v2.py").read_text(encoding="utf-8")
    master_text = Path("scripts/run_jarvis_master_plan_autopilot.ps1").read_text(encoding="utf-8")

    assert "assert_clean_repo(repo)" in text
    assert "EOF repair merge failed" in text
    assert "git merge --abort" in text
    assert "git merge --abort" in master_text
    assert "intended_phase_paths(discover_changes(repo))" in text
    assert "normalize_eof_whitespace" in text
