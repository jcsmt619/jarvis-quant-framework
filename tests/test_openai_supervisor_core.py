from __future__ import annotations

import json
import pytest
import subprocess
from pathlib import Path


def test_openai_supervisor_dry_run_outputs_valid_json(tmp_path: Path) -> None:
    output_path = tmp_path / "supervisor.json"

    completed = subprocess.run(
        [
            "python",
            "tools/jarvis_openai_supervisor.py",
            "--phase-name",
            "TEST_PHASE",
            "--failed-command",
            "codex exec broken command",
            "--exit-code",
            "9",
            "--error-summary",
            "unsupported flag test",
            "--output-json",
            str(output_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout

    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["status"] == "repair_needed"
    assert data["recommended_agent"] == "codex"
    assert data["safe_to_patch"] is True
    assert data["dangerous_action_detected"] is False


def test_openai_supervisor_prompt_blocks_live_trading() -> None:
    text = Path("prompts/jarvis_openai_supervisor_system.md").read_text(encoding="utf-8")

    assert "Do not enable live trading." in text
    assert "Do not submit broker orders." in text
    assert "Do not touch .env." in text
    assert "Return JSON only" in text


def test_supervisor_reads_context_docs_function_exists() -> None:
    text = Path("tools/jarvis_openai_supervisor.py").read_text(encoding="utf-8")

    assert "read_supervisor_context" in text
    assert "docs" in text
    assert "supervisor_context" in text
    assert "AGENTS.md" in text
    assert "CLAUDE.md" in text


def test_supervisor_loop_script_exists_and_mentions_auto_repair() -> None:
    text = Path("scripts/run_jarvis_supervisor_loop.ps1").read_text(encoding="utf-8")

    assert "AutoRepairWithCodex" in text
    assert "ASKING OPENAI SUPERVISOR" in text
    assert "tools\\jarvis_codex_exec.py" in text or "tools/jarvis_codex_exec.py" in text
    assert "CodexRepairSandbox" in text
    assert "safe_to_patch" in text


def _valid_supervisor_plan(repair_prompt: str) -> dict:
    return {
        "status": "repair_needed",
        "root_cause": "test root cause",
        "safe_repair_plan": ["small safe patch"],
        "recommended_agent": "codex",
        "repair_prompt_for_agent": repair_prompt,
        "commands_to_run_after_patch": ["python -m pytest tests/ -q"],
        "files_to_change": ["tools/jarvis_openai_supervisor.py"],
        "stop_conditions": ["Any secret, live trading, or broker order request."],
        "dangerous_action_detected": False,
        "safe_to_patch": True,
    }


def test_supervisor_allows_negated_live_trading_safety_instruction() -> None:
    from tools.jarvis_openai_supervisor import validate_plan

    plan = _valid_supervisor_plan(
        "Fix the unsupported Codex CLI flag. Do not enable live trading. Do not submit broker orders."
    )

    validate_plan(plan)


def test_supervisor_blocks_affirmative_live_trading_instruction() -> None:
    from tools.jarvis_openai_supervisor import validate_plan

    plan = _valid_supervisor_plan(
        "Fix the unsupported Codex CLI flag, then enable live trading."
    )

    with pytest.raises(ValueError, match="unsafe forbidden phrase"):
        validate_plan(plan)


def test_supervisor_blocks_affirmative_api_key_print_instruction() -> None:
    from tools.jarvis_openai_supervisor import validate_plan

    plan = _valid_supervisor_plan(
        "Fix the unsupported Codex CLI flag, then print api key for debugging."
    )

    with pytest.raises(ValueError, match="unsafe forbidden phrase"):
        validate_plan(plan)


def test_openai_supervisor_supports_arg_file_wrapper_for_quoted_failed_commands() -> None:
    supervisor_text = Path("tools/jarvis_openai_supervisor.py").read_text(encoding="utf-8")
    wrapper_text = Path("scripts/run_jarvis_openai_supervisor.ps1").read_text(encoding="utf-8")

    assert 'fromfile_prefix_chars="@"' in supervisor_text
    assert "$argLines = @(" in wrapper_text
    assert "[System.IO.File]::WriteAllLines" in wrapper_text
    assert '"@$argFile"' in wrapper_text
    assert "python @argsList" not in wrapper_text
