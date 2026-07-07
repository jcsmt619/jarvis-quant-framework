from __future__ import annotations

import json
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
    assert "codex exec" in text
    assert "safe_to_patch" in text
