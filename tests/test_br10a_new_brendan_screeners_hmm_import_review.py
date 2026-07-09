from __future__ import annotations

import json
from pathlib import Path


BR_PLAN_PATH = Path("config/jarvis_brendan_master_plan.json")
REVIEW_PATH = Path("docs/brendan_strategy/br10a_new_screeners_hmm_import_review.md")
SUMMARY_PATH = Path("docs/brendan_strategy/skool_modules/new_screeners_hmm_module_summary.md")
GAP_PATH = Path("docs/brendan_strategy/skool_modules/new_modules_gap_analysis.md")
RECOMMENDATIONS_PATH = Path(
    "docs/brendan_strategy/skool_modules/implementation_recommendations.md"
)


def _load_plan() -> list[dict[str, str]]:
    return json.loads(BR_PLAN_PATH.read_text(encoding="utf-8-sig"))


def test_br10a_review_docs_exist_and_are_sanitized() -> None:
    for path in [REVIEW_PATH, SUMMARY_PATH, GAP_PATH, RECOMMENDATIONS_PATH]:
        assert path.exists()

    review = REVIEW_PATH.read_text(encoding="utf-8")

    required_markers = [
        "RESEARCH_ONLY",
        "MONITOR_ONLY",
        "PAPER_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "LIVE TRADING: DISABLED",
        "docs-only",
        "does not copy raw paid source content",
        "before BR-11 and BR-12",
    ]

    for marker in required_markers:
        assert marker in review


def test_br10a_review_does_not_introduce_execution_language() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [REVIEW_PATH, SUMMARY_PATH, GAP_PATH, RECOMMENDATIONS_PATH]
    )

    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in combined


def test_br10a_phase_is_docs_only_and_before_broker_boundary() -> None:
    plan = _load_plan()
    phases = [item["phase"] for item in plan]

    assert phases.index("BR-10A") < phases.index("BR-11")
    assert phases.index("BR-10A") < phases.index("BR-12")

    br10a = next(item for item in plan if item["phase"] == "BR-10A")

    assert br10a["title"] == "New Brendan Screeners and HMM Import Review"
    assert br10a["commit_message"].startswith("docs:")
    assert "docs-only review" in br10a["spec"]
    assert "Do not copy raw paid source content" in br10a["spec"]
    assert "LIVE TRADING: DISABLED" in br10a["spec"]
