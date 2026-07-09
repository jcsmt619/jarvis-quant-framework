from __future__ import annotations

import json
from pathlib import Path


BR_PLAN_PATH = Path("config/jarvis_brendan_master_plan.json")
WORKFLOW_PATH = Path(
    "docs/brendan_strategy/br10b_track_a_manual_screener_operator_workflow.md"
)


def _load_plan() -> list[dict[str, str]]:
    return json.loads(BR_PLAN_PATH.read_text(encoding="utf-8-sig"))


def test_br10b_operator_workflow_doc_exists_and_covers_required_sections() -> None:
    assert WORKFLOW_PATH.exists()

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    required_markers = [
        "BR-10B - Track A Manual Screener Operator Workflow",
        "RESEARCH_ONLY",
        "MONITOR_ONLY",
        "PAPER_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "LIVE TRADING: DISABLED",
        "docs-only",
        "Universe Definition",
        "Filter Families",
        "Screen-Not-Signal Discipline",
        "Regime-Matched Screens",
        "Review Checklist",
        "Paper-Only Handoff",
        "not raw course content",
    ]

    for marker in required_markers:
        assert marker in workflow


def test_br10b_workflow_preserves_manual_research_boundary() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    required_safety_phrases = [
        "candidate research queue only",
        "not a signal",
        "Do not paste secrets",
        "Do not request broker connectivity",
        "empty results as valid outcomes",
        "existing paper-only Jarvis review workflows",
        "creates no code",
        "no broker integration",
        "no execution path",
    ]

    for phrase in required_safety_phrases:
        assert phrase in workflow


def test_br10b_workflow_does_not_introduce_forbidden_execution_labels() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in workflow


def test_br10b_phase_is_docs_only_and_before_broker_boundary() -> None:
    plan = _load_plan()
    phases = [item["phase"] for item in plan]

    assert phases.index("BR-10B") < phases.index("BR-11")
    assert phases.index("BR-10B") < phases.index("BR-12")

    br10b = next(item for item in plan if item["phase"] == "BR-10B")

    assert br10b["title"] == "Track A Manual Screener Operator Workflow"
    assert br10b["commit_message"].startswith("docs:")
    assert "docs-only Track A operator workflow" in br10b["spec"]
    assert "Do not implement code" in br10b["spec"]
    assert "Do not copy raw course content" in br10b["spec"]
    assert "LIVE TRADING: DISABLED" in br10b["spec"]
