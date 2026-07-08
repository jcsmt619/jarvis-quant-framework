from __future__ import annotations

from pathlib import Path

from automation.autonomous_master_plan_orchestrator_v2 import (
    find_phase_index,
    output_contains_usage_limit,
    parse_eof_blank_line_paths,
    ps_array,
    trim_extra_blank_line_at_eof,
)


def test_parse_eof_blank_line_paths_extracts_unique_python_paths() -> None:
    output = """
core/example.py:12: new blank line at EOF.
scripts/run_example.py:2: new blank line at EOF.
core/example.py:12: new blank line at EOF.
"""

    assert parse_eof_blank_line_paths(output) == [
        "core/example.py",
        "scripts/run_example.py",
    ]


def test_output_contains_usage_limit_detects_codex_limit_text() -> None:
    output = "ERROR: You've hit your usage limit. Purchase more credits or try again later."

    assert output_contains_usage_limit(output) is True


def test_output_contains_usage_limit_ignores_normal_failure() -> None:
    output = "Focused tests failed. STOP."

    assert output_contains_usage_limit(output) is False


def test_trim_extra_blank_line_at_eof_removes_extra_blank_lines(tmp_path: Path) -> None:
    target = tmp_path / "core" / "sample.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('ok')\n\n\n", encoding="utf-8")

    fixed = trim_extra_blank_line_at_eof(tmp_path, ["core/sample.py"])

    assert fixed == ["core/sample.py"]
    assert target.read_text(encoding="utf-8") == "print('ok')\n"


def test_find_phase_index_finds_requested_phase() -> None:
    queue = [
        {"phase": "26B", "title": "Previous"},
        {"phase": "27A", "title": "Next"},
    ]

    assert find_phase_index(queue, "27A") == 1


def test_ps_array_quotes_values_for_powershell() -> None:
    assert ps_array(["core/a.py", "tests/test_a.py"]) == "@('core/a.py', 'tests/test_a.py')"
    assert ps_array([]) == "@()"


def test_run_command_uses_utf8_decode_with_replacement() -> None:
    source = Path("automation/autonomous_master_plan_orchestrator_v2.py").read_text(encoding="utf-8")

    assert 'encoding="utf-8"' in source
    assert 'errors="replace"' in source
    assert '"PYTHONUTF8": "1"' in source
    assert '"PYTHONIOENCODING": "utf-8"' in source


def test_safe_text_decodes_bad_bytes_without_crashing() -> None:
    from automation.autonomous_master_plan_orchestrator_v2 import _safe_text

    assert _safe_text(None) == ""
    assert _safe_text("ok") == "ok"
    assert "\ufffd" in _safe_text(b"bad-byte-\x9d")
