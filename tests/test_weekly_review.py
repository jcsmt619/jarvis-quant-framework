from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from core.weekly_review import (
    WeeklyReviewInput,
    build_weekly_review_payload,
    render_weekly_review_markdown,
    write_weekly_review,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _review_input(**overrides) -> WeeklyReviewInput:
    values = {
        "review_id": "14B-WEEKLY-2026-07-07",
        "week_start": "2026-07-01",
        "week_end": "2026-07-07",
        "generated_at_utc": "2026-07-07T19:00:00+00:00",
        "wealth_research_results": (
            {
                "strategy_id": "WEALTH-B",
                "summary": "Wealth residual momentum monitor stayed research-only.",
                "label": RESEARCH_ONLY,
            },
            {
                "strategy_id": "WEALTH-A",
                "summary": "Wealth mean reversion lab completed deterministic validation.",
                "label": PAPER_ONLY,
            },
        ),
        "moonshot_research_results": (
            {
                "strategy_id": "MOONSHOT-LEAPS-QUALITY",
                "summary": "LEAPS quality monitor found stale option-chain data.",
                "label": MONITOR_ONLY,
            },
        ),
        "experiments": (
            {
                "experiment_id": "EXP-MOONSHOT-001",
                "engine": "moonshot",
                "summary": "Moonshot replay fixture completed.",
                "label": MONITOR_ONLY,
            },
            {
                "experiment_id": "EXP-WEALTH-001",
                "engine": "wealth",
                "summary": "Wealth walk-forward fixture completed.",
                "label": RESEARCH_ONLY,
            },
        ),
        "promotion_gates": (
            {
                "strategy_id": "WEALTH-A",
                "engine": "wealth",
                "promotion_status": "paper_only",
                "summary": "Paper history incomplete.",
                "label": PAPER_ONLY,
            },
            {
                "strategy_id": "MOONSHOT-LEAPS-QUALITY",
                "engine": "moonshot",
                "promotion_status": "blocked_by_safety_gate",
                "summary": "Stale option-chain data blocked review.",
                "label": BLOCKED_BY_SAFETY_GATE,
            },
        ),
        "champion_challenger_outcomes": (
            {
                "incumbent_strategy_id": "WEALTH-A",
                "challenger_strategy_id": "WEALTH-C",
                "engine": "wealth",
                "challenger_status": "challenger_human_review_required",
                "summary": "Challenger beat incumbent and remains review-gated.",
                "label": HUMAN_REVIEW_REQUIRED,
            },
        ),
        "safety_scanner_findings": (
            {
                "finding_id": "SAFETY-001",
                "path": "candidate.py",
                "summary": "Unsafe execution phrase was blocked.",
                "label": BLOCKED_BY_SAFETY_GATE,
            },
        ),
        "blocked_decisions": (
            {
                "decision_id": "BLOCKED-MANUAL-001",
                "engine": "wealth",
                "summary": "Manual review blocked pending missing stop evidence.",
                "label": BLOCKED_BY_SAFETY_GATE,
            },
        ),
        "next_review_actions": (
            {
                "action_id": "NEXT-001",
                "summary": "Re-run option-chain freshness check before next review.",
                "label": HUMAN_REVIEW_REQUIRED,
            },
        ),
    }
    values.update(overrides)
    return WeeklyReviewInput(**values)


def test_14b_builds_deterministic_weekly_review_payload() -> None:
    payload = build_weekly_review_payload(_review_input())

    assert payload["phase"] == "14B"
    assert payload["workflow"] == "Weekly Review"
    assert payload["safety_boundary"]["live_trading_enabled"] is False
    assert payload["safety_boundary"]["broker_order_routing_enabled"] is False
    assert payload["safety_boundary"]["broker_order_call_performed"] is False
    assert payload["safety_boundary"]["real_paper_order_submitted"] is False
    assert payload["safety_boundary"]["secrets_required"] is False
    assert payload["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"

    assert [item["strategy_id"] for item in payload["wealth_research_results"]] == [
        "WEALTH-A",
        "WEALTH-B",
    ]
    assert payload["summary"]["wealth_research_result_count"] == 2
    assert payload["summary"]["moonshot_research_result_count"] == 1
    assert payload["summary"]["experiment_counts_by_engine"] == {"moonshot": 1, "wealth": 1}
    assert payload["summary"]["promotion_gate_counts_by_status"] == {
        "blocked_by_safety_gate": 1,
        "paper_only": 1,
    }
    assert payload["summary"]["blocked_decision_count"] == 2


def test_14b_writes_json_and_markdown_reports() -> None:
    out_dir = Path("reports/weekly_review_tests") / uuid.uuid4().hex
    try:
        json_path, markdown_path = write_weekly_review(_review_input(), out_dir=out_dir)

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "weekly_review.json"
        assert markdown_path.name == "weekly_review.md"
        assert payload["review_id"] == "14B-WEEKLY-2026-07-07"
        assert "14B Weekly Review" in markdown
        assert "HUMAN_REVIEW_REQUIRED" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No broker routing or order submission is enabled." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_14b_markdown_lists_empty_sections() -> None:
    payload = build_weekly_review_payload(
        _review_input(
            wealth_research_results=(),
            moonshot_research_results=(),
            experiments=(),
            promotion_gates=(),
            champion_challenger_outcomes=(),
            safety_scanner_findings=(),
            blocked_decisions=(),
            next_review_actions=(),
        )
    )

    markdown = render_weekly_review_markdown(payload)

    assert "- Wealth research results: 0" in markdown
    assert markdown.count("- None recorded.") == 8


def test_14b_rejects_unsafe_labels_and_execution_flags() -> None:
    unsafe_label = "BUY" + "_NOW"

    with pytest.raises(ValueError, match="unsafe weekly review label"):
        build_weekly_review_payload(
            _review_input(
                wealth_research_results=(
                    {
                        "strategy_id": "WEALTH-UNSAFE",
                        "summary": "Unsafe label fixture.",
                        "label": unsafe_label,
                    },
                )
            )
        )

    with pytest.raises(ValueError, match="live_trading_enabled"):
        build_weekly_review_payload(
            _review_input(
                experiments=(
                    {
                        "experiment_id": "EXP-UNSAFE",
                        "engine": "wealth",
                        "summary": "Unsafe execution flag fixture.",
                        "label": RESEARCH_ONLY,
                        "live_trading_enabled": True,
                    },
                )
            )
        )


def test_14b_rejects_invalid_review_window() -> None:
    with pytest.raises(ValueError, match="week_start cannot be after week_end"):
        build_weekly_review_payload(
            _review_input(week_start="2026-07-08", week_end="2026-07-07")
        )
