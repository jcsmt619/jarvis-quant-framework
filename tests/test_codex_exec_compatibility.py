from __future__ import annotations

from pathlib import Path

from tools.jarvis_codex_exec import build_codex_args, normalize_prompt_text


def test_codex_wrapper_does_not_emit_broken_approval_flags() -> None:
    text = Path("tools/jarvis_codex_exec.py").read_text(encoding="utf-8")

    assert "--ask-for-approval" not in build_codex_args(sandbox="read-only")
    assert "--approval-policy" not in build_codex_args(sandbox="read-only")
    assert "FORBIDDEN_FLAGS" in text


def test_codex_wrapper_builds_read_only_sandbox_args() -> None:
    assert build_codex_args(sandbox="read-only") == [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
    ]


def test_codex_wrapper_builds_workspace_write_sandbox_args() -> None:
    assert build_codex_args(sandbox="workspace-write") == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
    ]


def test_codex_wrapper_builds_default_args_without_sandbox_flag() -> None:
    assert build_codex_args(sandbox="default") == ["codex", "exec"]


def test_codex_review_script_uses_compatibility_wrapper() -> None:
    text = Path("scripts/run_jarvis_codex_review.ps1").read_text(encoding="utf-8")

    assert "tools\\jarvis_codex_exec.py" in text or "tools/jarvis_codex_exec.py" in text
    assert "--ask-for-approval" not in text
    assert "--approval-policy" not in text
    assert "--sandbox read-only" in text


def test_supervisor_loop_uses_compatibility_wrapper_for_repairs() -> None:
    text = Path("scripts/run_jarvis_supervisor_loop.ps1").read_text(encoding="utf-8")

    assert "tools\\jarvis_codex_exec.py" in text or "tools/jarvis_codex_exec.py" in text
    assert "CodexRepairSandbox" in text
    assert "--ask-for-approval" not in text
    assert "--approval-policy" not in text


def test_codex_wrapper_strips_utf8_bom_from_prompt_text() -> None:
    assert normalize_prompt_text("\ufeffReply with exactly CODEX_OK.") == "Reply with exactly CODEX_OK."


def test_codex_wrapper_uses_explicit_utf8_subprocess_encoding() -> None:
    text = Path("tools/jarvis_codex_exec.py").read_text(encoding="utf-8")

    assert 'encoding="utf-8"' in text
    assert 'errors="replace"' in text
    assert "utf-8-sig" in text
