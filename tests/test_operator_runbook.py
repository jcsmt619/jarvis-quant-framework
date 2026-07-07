from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.operator_runbook import (
    OperatorRunbookInput,
    build_default_operator_runbook_input,
    build_operator_runbook_payload,
    render_operator_runbook_markdown,
    write_operator_runbook,
)
from core.weekly_review import WeeklyReviewInput, build_weekly_review_payload
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _weekly_payload() -> dict:
    return build_weekly_review_payload(
        WeeklyReviewInput(
            review_id="14B-WEEKLY-2026-07-07",
            week_start="2026-07-01",
            week_end="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            experiments=(
                {
                    "experiment_id": "EXP-001",
                    "engine": "wealth",
                    "label": RESEARCH_ONLY,
                    "summary": "Experiment fixture.",
                },
            ),
            blocked_decisions=(
                {
                    "decision_id": "BLOCK-001",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "summary": "Blocked fixture.",
                },
            ),
        )
    )


def test_15b_builds_deterministic_operator_runbook_payload() -> None:
    runbook_input = build_default_operator_runbook_input(now=FIXED_NOW)

    first = build_operator_runbook_payload(runbook_input)
    second = build_operator_runbook_payload(runbook_input)

    assert first == second
    assert first["phase"] == "15B"
    assert first["workflow"] == "Operator Runbook"
    assert first["safety_boundary"]["real_paper_wrapper_connected"] is False
    assert first["safety_boundary"]["real_paper_wrapper_attempted"] is False
    assert first["safety_boundary"]["real_paper_order_submitted"] is False
    assert first["safety_boundary"]["broker_order_call_performed"] is False
    assert first["safety_boundary"]["broker_order_routing_enabled"] is False
    assert first["safety_boundary"]["broker_routing_used"] is False
    assert first["safety_boundary"]["broker_call_used"] is False
    assert first["safety_boundary"]["order_execution_used"] is False
    assert first["safety_boundary"]["live_trading_enabled"] is False
    assert first["safety_boundary"]["secrets_required"] is False
    assert first["safety_boundary"]["credential_file_used"] is False
    assert first["safety_boundary"]["prohibited_trade_labels_present"] is False
    assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    assert first["required_labels"] == [
        "RESEARCH_ONLY",
        "MONITOR_ONLY",
        "PAPER_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "BLOCKED_BY_SAFETY_GATE",
    ]
    assert [section["section_id"] for section in first["checklists"]] == [
        "daily_startup",
        "safety_preflight",
        "research_review",
        "experiment_review",
        "weekly_review",
        "promotion_review",
        "shutdown",
    ]
    assert first["summary"]["allowed_human_review_workflow_count"] == 4
    assert first["summary"]["blocked_workflow_count"] == 5


def test_15b_labels_allowed_human_review_and_blocked_workflows() -> None:
    payload = build_operator_runbook_payload(build_default_operator_runbook_input(now=FIXED_NOW))

    allowed = payload["allowed_human_review_workflows"]
    blocked = payload["blocked_workflows"]

    assert {item["label"] for item in allowed} == {HUMAN_REVIEW_REQUIRED}
    assert {item["status"] for item in allowed} == {"allowed_review_only"}
    assert {item["label"] for item in blocked} == {BLOCKED_BY_SAFETY_GATE}
    assert {item["status"] for item in blocked} == {"blocked"}
    assert {item["workflow_id"] for item in blocked} == {
        "live_trading",
        "broker_order_routing",
        "broker_order_call",
        "order_execution",
        "secret_or_credential_access",
    }


def test_15b_includes_context_summaries_without_enabling_execution() -> None:
    daily_payload = {
        "phase": "15A",
        "workflow": "Daily Research Command Center",
        "report_date": "2026-07-07",
        "summary": {"experiment_count": 2, "safety_scanner_finding_count": 0},
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "LIVE TRADING: DISABLED",
            "live_trading_enabled": False,
            "broker_order_call_performed": False,
        },
    }
    payload = build_operator_runbook_payload(
        OperatorRunbookInput(
            runbook_id="15B-OPERATOR-RUNBOOK-2026-07-07",
            runbook_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            daily_research_payload=daily_payload,
            weekly_review_payload=_weekly_payload(),
            experiment_review_items=(
                {
                    "experiment_id": "EXP-001",
                    "engine": "wealth",
                    "summary": "Review deterministic evidence.",
                    "label": RESEARCH_ONLY,
                },
            ),
            promotion_review_items=(
                {
                    "strategy_id": "STRAT-001",
                    "summary": "Promotion review remains human-gated.",
                    "label": HUMAN_REVIEW_REQUIRED,
                },
            ),
        )
    )

    assert payload["context"]["daily_research"]["status"] == "LIVE TRADING: DISABLED"
    assert payload["context"]["weekly_review"]["review_id"] == "14B-WEEKLY-2026-07-07"
    assert payload["summary"]["experiment_review_item_count"] == 1
    assert payload["summary"]["promotion_review_item_count"] == 1
    assert payload["safety_boundary"]["live_trading_enabled"] is False


def test_15b_writes_json_and_markdown_reports() -> None:
    out_dir = Path("reports/operator_runbook_tests") / uuid.uuid4().hex
    try:
        json_path, markdown_path = write_operator_runbook(
            build_default_operator_runbook_input(now=FIXED_NOW),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "operator_runbook.json"
        assert markdown_path.name == "operator_runbook.md"
        assert payload["runbook_date"] == "2026-07-07"
        assert "15B Operator Runbook" in markdown
        assert "Allowed Human-Review Workflows" in markdown
        assert "Blocked Workflows" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_15b_rejects_unsafe_labels_and_execution_flags() -> None:
    unsafe_label = "AUTO" + "_TRADE"

    with pytest.raises(ValueError, match="unsafe operator runbook label"):
        build_operator_runbook_payload(
            OperatorRunbookInput(
                runbook_id="15B-UNSAFE",
                runbook_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                experiment_review_items=(
                    {
                        "experiment_id": "EXP-UNSAFE",
                        "label": unsafe_label,
                        "summary": "Unsafe fixture.",
                    },
                ),
            )
        )

    with pytest.raises(ValueError, match="broker_order_call_performed"):
        build_operator_runbook_payload(
            OperatorRunbookInput(
                runbook_id="15B-UNSAFE",
                runbook_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                safety_findings=(
                    {
                        "finding_id": "FINDING-UNSAFE",
                        "label": BLOCKED_BY_SAFETY_GATE,
                        "summary": "Unsafe fixture.",
                        "broker_order_call_performed": True,
                    },
                ),
            )
        )


def test_15b_markdown_lists_empty_context_sections() -> None:
    payload = build_operator_runbook_payload(
        OperatorRunbookInput(
            runbook_id="15B-EMPTY",
            runbook_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
        )
    )

    markdown = render_operator_runbook_markdown(payload)

    assert "Daily Startup" in markdown
    assert markdown.count("- None recorded.") == 4


def test_15b_runner_writes_reports() -> None:
    out_dir = Path("reports/operator_runbook_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_operator_runbook.py",
                "--out-dir",
                str(out_dir),
                "--runbook-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 15B OPERATOR RUNBOOK: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE workflows remain blocked" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "operator_runbook.json").exists()
        assert (out_dir / "operator_runbook.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
