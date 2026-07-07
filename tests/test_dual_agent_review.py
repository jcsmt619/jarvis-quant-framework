from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engines.moonshot.deterministic.dual_agent_review import (
    REQUIRED_LABELS,
    AgentReviewOutput,
    build_dual_agent_review,
    build_dual_agent_review_payload,
    render_markdown_review,
    safety_manifest,
    write_dual_agent_review_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _review(**overrides: object) -> AgentReviewOutput:
    values = {
        "agent": "claude",
        "review_type": "research",
        "summary": "Research memo is clearly labeled for analyst review.",
        "findings": ("RESEARCH_ONLY output includes HUMAN_REVIEW_REQUIRED language.",),
        "verdict": "pass",
        "label": HUMAN_REVIEW_REQUIRED,
    }
    values.update(overrides)
    return AgentReviewOutput(**values)


def test_13g_safety_manifest_is_disabled_and_review_only() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13G"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["ingests_agent_outputs_only"] is True
    assert manifest["external_agent_calls_enabled"] is False
    assert manifest["claude_api_call_performed"] is False
    assert manifest["openai_api_call_performed"] is False
    assert manifest["codex_exec_performed"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13g_builds_complete_dual_agent_research_and_code_safety_review() -> None:
    report = build_dual_agent_review(
        [
            _review(agent="claude", review_type="research"),
            _review(
                agent="openai",
                review_type="code_safety",
                summary="Code safety review found no broker routing or live execution.",
                findings=("Safety gates remain intact.",),
            ),
        ],
        source_artifact="reports/moonshot/leaps_memo.md",
    )
    payload = build_dual_agent_review_payload(report)

    assert report.label == HUMAN_REVIEW_REQUIRED
    assert report.consensus_status == "dual_agent_review_complete"
    assert report.warnings == ()
    assert payload["phase"] == "13G"
    assert payload["metrics"]["distinct_agent_count"] == 2
    assert set(payload["metrics"]["review_types"]) == {"research", "code_safety"}
    assert payload["reviews"][0]["human_review_required"] is True
    assert payload["safety"]["broker_order_submitted"] is False


def test_13g_blocks_incomplete_or_conflicting_reviews() -> None:
    incomplete = build_dual_agent_review(
        [_review(agent="codex", review_type="code_safety")],
        source_artifact="git diff",
    )
    conflict = build_dual_agent_review(
        [
            _review(agent="claude", review_type="research", verdict="pass"),
            _review(agent="openai", review_type="code_safety", verdict="review"),
        ],
        source_artifact="git diff",
    )

    assert incomplete.label == BLOCKED_BY_SAFETY_GATE
    assert "insufficient_distinct_agent_coverage" in incomplete.warnings
    assert "missing_research_review" in incomplete.warnings
    assert conflict.label == BLOCKED_BY_SAFETY_GATE
    assert conflict.consensus_status == "requires_human_reconciliation"
    assert "agent_verdict_conflict" in conflict.warnings


def test_13g_blocks_unsafe_trade_labels_and_order_phrases_in_agent_text() -> None:
    unsafe_label = "BUY" + "_NOW"
    report = build_dual_agent_review(
        [
            _review(
                agent="claude",
                review_type="research",
                summary=f"Unsafe analyst output included {unsafe_label}.",
            ),
            _review(
                agent="openai",
                review_type="code_safety",
                summary="Unsafe instruction attempted to enable live trading.",
            ),
        ],
        source_artifact="agent transcript",
    )

    assert report.label == BLOCKED_BY_SAFETY_GATE
    assert report.consensus_status == "blocked_by_safety_gate"
    assert "claude:research:unsafe_trade_label" in report.warnings
    assert "openai:code_safety:unsafe_action_phrase" in report.warnings


def test_13g_redacts_secret_like_assignments_from_payload_and_markdown() -> None:
    report = build_dual_agent_review(
        [
            _review(
                agent="claude",
                review_type="research",
                summary="API_" + "KEY = 'super-sensitive-value'",
            ),
            _review(agent="openai", review_type="code_safety"),
        ],
        source_artifact="agent transcript",
    )
    payload = build_dual_agent_review_payload(report)
    markdown = render_markdown_review(report)

    assert report.label == BLOCKED_BY_SAFETY_GATE
    assert "secret_like_assignment_redacted" in " ".join(report.warnings)
    assert "super-sensitive-value" not in json.dumps(payload)
    assert "super-sensitive-value" not in markdown
    assert "[REDACTED]" in json.dumps(payload)


def test_13g_write_report_outputs_json_and_markdown() -> None:
    report = build_dual_agent_review(
        [
            _review(agent="claude", review_type="research"),
            _review(agent="codex", review_type="code_safety"),
        ],
        source_artifact="git diff",
    )
    out_dir = Path(".codex_pytest_tmp/dual_agent_review_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_dual_agent_review_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "13G"
    assert "Claude OpenAI Dual Agent Review" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_13g_validation_rejects_invalid_agent_label_and_threshold() -> None:
    with pytest.raises(ValueError, match="agent must be"):
        build_dual_agent_review([_review(agent="other")], source_artifact="memo")

    with pytest.raises(ValueError, match="label must be a safe"):
        build_dual_agent_review([_review(label="unsafe")], source_artifact="memo")

    with pytest.raises(ValueError, match="min_distinct_agents"):
        build_dual_agent_review(
            [_review(agent="claude"), _review(agent="openai")],
            source_artifact="memo",
            min_distinct_agents=1,
        )
