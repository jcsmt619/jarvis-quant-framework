from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "engines"

EXPECTED_ENGINE_PATHS = (
    "README.md",
    "__init__.py",
    "wealth/README.md",
    "wealth/__init__.py",
    "wealth/deterministic/README.md",
    "wealth/deterministic/__init__.py",
    "wealth/analyst_outputs/README.md",
    "wealth/analyst_outputs/__init__.py",
    "moonshot/README.md",
    "moonshot/__init__.py",
    "moonshot/deterministic/README.md",
    "moonshot/deterministic/__init__.py",
    "moonshot/analyst_outputs/README.md",
    "moonshot/analyst_outputs/__init__.py",
)

EXPECTED_DOCS = (
    REPO_ROOT / "docs" / "DUAL_ENGINE_STRUCTURE.md",
)

ALLOWED_LABELS = {
    "RESEARCH_ONLY",
    "MONITOR_ONLY",
    "PAPER_ONLY",
    "HUMAN_REVIEW_REQUIRED",
    "BLOCKED_BY_SAFETY_GATE",
}


def _phase_files() -> list[Path]:
    return [ENGINE_ROOT / rel_path for rel_path in EXPECTED_ENGINE_PATHS] + list(EXPECTED_DOCS)


def test_dual_engine_phase_11a_paths_exist() -> None:
    for rel_path in EXPECTED_ENGINE_PATHS:
        assert (ENGINE_ROOT / rel_path).is_file(), rel_path

    for doc_path in EXPECTED_DOCS:
        assert doc_path.is_file(), doc_path


def test_dual_engine_boundaries_are_documented() -> None:
    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in _phase_files())

    for expected in ("wealth", "moonshot", "deterministic", "analyst_outputs"):
        assert expected in combined_text

    for label in ALLOWED_LABELS:
        assert label in combined_text

    assert "LIVE TRADING: DISABLED" in combined_text


def test_dual_engine_structure_contains_no_order_routing_terms() -> None:
    prohibited_terms = {
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
        "submit" + "_order(",
        "place" + "_order(",
        "create" + "_order(",
        "live_trading_" + "enabled = True",
    }

    for path in _phase_files():
        text = path.read_text(encoding="utf-8")
        for term in prohibited_terms:
            assert term not in text, f"{term} found in {path.relative_to(REPO_ROOT)}"
