from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_evidence_pack import (
    ResearchEvidencePackInput,
    build_default_research_evidence_pack_input,
    build_research_evidence_pack_payload,
    render_research_evidence_pack_markdown,
    write_research_evidence_pack,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def test_16a_builds_deterministic_research_evidence_pack_payload() -> None:
    pack_input = build_default_research_evidence_pack_input(now=FIXED_NOW)

    first = build_research_evidence_pack_payload(pack_input)
    second = build_research_evidence_pack_payload(pack_input)

    assert first == second
    assert first["phase"] == "16A"
    assert first["workflow"] == "Research Evidence Pack"
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
    assert first["summary"]["strategy_card_count"] >= 4
    assert first["summary"]["experiment_count"] == len(first["evidence"]["experiment_registry_entries"])
    assert first["evidence"]["weekly_review_output"]["phase"] == "14B"
    assert first["evidence"]["daily_research_command_center"]["phase"] == "15A"
    assert first["evidence"]["operator_runbook_status"]["phase"] == "15B"


def test_16a_writes_json_and_markdown_reports() -> None:
    out_dir = Path("reports/research_evidence_pack_tests") / uuid.uuid4().hex
    try:
        json_path, markdown_path = write_research_evidence_pack(
            build_default_research_evidence_pack_input(now=FIXED_NOW),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_evidence_pack.json"
        assert markdown_path.name == "research_evidence_pack.md"
        assert payload["evidence_date"] == "2026-07-07"
        assert "16A Research Evidence Pack" in markdown
        assert "Strategy Cards" in markdown
        assert "Operator Runbook Status" in markdown
        assert "BLOCKED_BY_SAFETY_GATE findings remain blocked." in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_16a_rejects_unsafe_labels_and_execution_flags() -> None:
    unsafe_label = "BUY" + "_NOW"

    with pytest.raises(ValueError, match="unsafe research evidence label"):
        build_research_evidence_pack_payload(
            ResearchEvidencePackInput(
                pack_id="16A-UNSAFE",
                evidence_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                strategy_cards=(),
                experiments=(
                    {
                        "experiment_id": "EXP-UNSAFE",
                        "engine": "wealth",
                        "label": unsafe_label,
                        "summary": "Unsafe fixture.",
                    },
                ),
            )
        )

    with pytest.raises(ValueError, match="order_execution_used"):
        build_research_evidence_pack_payload(
            ResearchEvidencePackInput(
                pack_id="16A-UNSAFE",
                evidence_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                strategy_cards=(),
                operator_notes=(
                    {
                        "note_id": "NOTE-UNSAFE",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "summary": "Unsafe fixture.",
                        "order_execution_used": True,
                    },
                ),
            )
        )


def test_16a_accepts_supplied_source_payloads_without_enabling_execution() -> None:
    payload = build_research_evidence_pack_payload(
        ResearchEvidencePackInput(
            pack_id="16A-CUSTOM",
            evidence_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            strategy_cards=(),
            experiments=(
                {
                    "experiment_id": "EXP-001",
                    "engine": "wealth",
                    "label": RESEARCH_ONLY,
                    "summary": "Research-only fixture.",
                },
            ),
            daily_research_payload={
                "phase": "15A",
                "workflow": "Daily Research Command Center",
                "report_date": "2026-07-07",
                "summary": {"experiment_count": 1, "safety_scanner_finding_count": 0},
                "safety_boundary": {
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "LIVE TRADING: DISABLED",
                    "live_trading_enabled": False,
                    "broker_order_call_performed": False,
                },
                "safety_scanner": {
                    "status": "passed",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "passed": True,
                    "finding_count": 0,
                    "findings": [],
                },
            },
        )
    )

    assert payload["summary"]["daily_research_included"] is True
    assert payload["summary"]["safety_scanner_status"] == "passed"
    assert payload["evidence"]["safety_scanner_status"]["passed"] is True
    assert payload["safety_boundary"]["live_trading_enabled"] is False


def test_16a_markdown_lists_empty_optional_sections() -> None:
    payload = build_research_evidence_pack_payload(
        ResearchEvidencePackInput(
            pack_id="16A-EMPTY",
            evidence_date="2026-07-07",
            generated_at_utc=FIXED_NOW.isoformat(),
            strategy_cards=(),
            experiments=(),
            promotion_gates=(),
            champion_challenger_outcomes=(),
        )
    )

    markdown = render_research_evidence_pack_markdown(payload)

    assert "- Strategy cards: 0" in markdown
    assert markdown.count("- None recorded.") == 8


def test_16a_runner_writes_reports() -> None:
    out_dir = Path("reports/research_evidence_pack_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_evidence_pack.py",
                "--out-dir",
                str(out_dir),
                "--evidence-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 16A RESEARCH EVIDENCE PACK: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE findings remain blocked" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "research_evidence_pack.json").exists()
        assert (out_dir / "research_evidence_pack.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
