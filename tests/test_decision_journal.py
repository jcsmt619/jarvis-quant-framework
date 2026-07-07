from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.decision_journal import (
    DecisionJournalInput,
    build_decision_journal_payload,
    build_default_decision_journal_input,
    render_decision_journal_markdown,
    write_decision_journal,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def test_16b_builds_deterministic_decision_journal_payload() -> None:
    journal_input = build_default_decision_journal_input(now=FIXED_NOW)

    first = build_decision_journal_payload(journal_input)
    second = build_decision_journal_payload(journal_input)

    assert first == second
    assert first["phase"] == "16B"
    assert first["workflow"] == "Decision Journal"
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
    assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    assert first["summary"]["decision_record_count"] == 1
    assert first["summary"]["blocked_outcome_count"] == 1
    assert first["summary"]["follow_up_action_count"] == 1
    assert first["summary"]["evidence_pack_reference_count"] == 1
    assert first["summary"]["history_event_count"] == 4


def test_16b_labels_allowed_review_and_blocked_workflows() -> None:
    payload = build_decision_journal_payload(build_default_decision_journal_input(now=FIXED_NOW))

    allowed = payload["allowed_review_workflows"]
    blocked = payload["blocked_workflows"]

    assert {item["status"] for item in allowed} == {
        "allowed_review_only",
        "allowed_blocked_record_only",
    }
    assert {item["workflow_id"] for item in allowed} == {
        "record_human_review_outcome",
        "record_blocked_outcome",
        "record_follow_up_action",
        "reference_evidence_pack",
        "record_operator_note",
    }
    assert {item["label"] for item in blocked} == {BLOCKED_BY_SAFETY_GATE}
    assert {item["status"] for item in blocked} == {"blocked"}
    assert {item["workflow_id"] for item in blocked} == {
        "live_trading",
        "broker_order_routing",
        "broker_order_call",
        "order_execution",
        "secret_or_credential_access",
    }


def test_16b_accepts_supplied_decisions_evidence_and_safety_status() -> None:
    payload = build_decision_journal_payload(
        DecisionJournalInput(
            journal_id="16B-CUSTOM",
            journal_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            decision_records=(
                {
                    "decision_id": "DECISION-001",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "reviewed",
                    "summary": "Research memo reviewed; no execution state changed.",
                    "evidence_reference_id": "16A-RESEARCH-EVIDENCE-PACK-2026-07-07",
                },
            ),
            blocked_outcomes=(
                {
                    "decision_id": "BLOCK-001",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": "Missing safety scanner evidence keeps workflow blocked.",
                },
            ),
            follow_up_actions=(
                {
                    "action_id": "ACTION-001",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "open_review_item",
                    "summary": "Attach updated safety scanner output next cycle.",
                },
            ),
            evidence_pack_references=(
                {
                    "reference_id": "16A-RESEARCH-EVIDENCE-PACK-2026-07-07",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "referenced",
                    "summary": "Evidence pack fixture.",
                },
            ),
            safety_scanner_status={
                "status": "passed",
                "label": HUMAN_REVIEW_REQUIRED,
                "passed": True,
                "finding_count": 0,
                "findings": [],
            },
            operator_notes=(
                {
                    "note_id": "NOTE-001",
                    "label": RESEARCH_ONLY,
                    "summary": "Operator note fixture.",
                },
            ),
        )
    )

    assert payload["summary"]["decision_record_count"] == 1
    assert payload["summary"]["blocked_outcome_count"] == 1
    assert payload["summary"]["safety_scanner_status"] == "passed"
    assert payload["journal"]["safety_scanner_status"]["passed"] is True
    assert payload["journal"]["history"][0]["source_type"] == "blocked_outcome"
    assert payload["safety_boundary"]["live_trading_enabled"] is False


def test_16b_writes_json_and_markdown_reports() -> None:
    out_dir = Path("reports/decision_journal_tests") / uuid.uuid4().hex
    try:
        json_path, markdown_path = write_decision_journal(
            build_default_decision_journal_input(now=FIXED_NOW),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "decision_journal.json"
        assert markdown_path.name == "decision_journal.md"
        assert payload["journal_date"] == "2026-07-07"
        assert "16B Decision Journal" in markdown
        assert "Allowed Review Workflows" in markdown
        assert "Blocked Workflows" in markdown
        assert "Evidence Pack References" in markdown
        assert "Audit History" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_16b_rejects_unsafe_labels_and_execution_flags() -> None:
    unsafe_label = "SELL" + "_NOW"

    with pytest.raises(ValueError, match="unsafe decision journal label"):
        build_decision_journal_payload(
            DecisionJournalInput(
                journal_id="16B-UNSAFE",
                journal_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                decision_records=(
                    {
                        "decision_id": "DECISION-UNSAFE",
                        "label": unsafe_label,
                        "summary": "Unsafe fixture.",
                    },
                ),
            )
        )

    with pytest.raises(ValueError, match="broker_order_call_performed"):
        build_decision_journal_payload(
            DecisionJournalInput(
                journal_id="16B-UNSAFE",
                journal_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                operator_notes=(
                    {
                        "note_id": "NOTE-UNSAFE",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "summary": "Unsafe fixture.",
                        "broker_order_call_performed": True,
                    },
                ),
            )
        )


def test_16b_markdown_lists_empty_optional_sections() -> None:
    payload = build_decision_journal_payload(
        DecisionJournalInput(
            journal_id="16B-EMPTY",
            journal_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
        )
    )

    markdown = render_decision_journal_markdown(payload)

    assert "- Decision records: 0" in markdown
    assert markdown.count("- None recorded.") == 6


def test_16b_runner_writes_reports() -> None:
    out_dir = Path("reports/decision_journal_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_decision_journal.py",
                "--out-dir",
                str(out_dir),
                "--journal-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 16B DECISION JOURNAL: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE workflows and outcomes remain blocked" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "decision_journal.json").exists()
        assert (out_dir / "decision_journal.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
