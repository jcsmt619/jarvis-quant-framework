from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br20_paper_research_decision_journal import (
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_EVIDENCE_PATH,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_JOURNAL_SECTIONS,
    build_paper_research_decision_journal,
    paper_research_decision_journal_payload,
    render_markdown_paper_research_decision_journal,
    run_paper_research_decision_journal,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br20_paper_research_decision_journal.py")
SCRIPT_PATH = Path("scripts/run_br20_paper_research_decision_journal.py")
DOC_PATH = Path("docs/brendan_strategy/br20_paper_research_decision_journal.md")


def test_br20_safety_manifest_is_read_only_paper_records_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["module"] == MODULE_NAME
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["read_only_paper_records"] is True
    assert manifest["source_evidence_read_only"] is True
    assert manifest["deterministic_journal_records_only"] is True
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br20_builds_decision_journal_from_committed_source_evidence() -> None:
    journal = build_paper_research_decision_journal()
    payload = paper_research_decision_journal_payload(journal)

    assert DEFAULT_SOURCE_EVIDENCE_PATH.exists()
    assert payload["phase"] == "BR-20"
    assert payload["module"] == "Paper Research Decision Journal"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["source_evidence_path"] == str(DEFAULT_SOURCE_EVIDENCE_PATH)
    assert payload["journal_sections"] == REQUIRED_JOURNAL_SECTIONS
    assert payload["metrics"]["journal_record_count"] == 4
    assert payload["metrics"]["held_count"] == 2
    assert payload["metrics"]["rejected_count"] == 1
    assert payload["metrics"]["sent_for_review_count"] == 1
    assert payload["metrics"]["paper_only_portfolio_state_count"] == 4
    assert payload["metrics"]["monitor_outcome_count"] == 4
    assert payload["metrics"]["human_review_action_count"] == 6
    assert payload["metrics"]["operator_note_count"] == 8
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False


def test_br20_records_link_required_evidence_sections() -> None:
    journal = build_paper_research_decision_journal()
    payload = paper_research_decision_journal_payload(journal)
    first_record = payload["records"][0]

    for section_name in REQUIRED_JOURNAL_SECTIONS:
        assert section_name in first_record
    assert first_record["decision_category"] == "held"
    assert first_record["label"] == PAPER_ONLY
    assert first_record["source_evidence"]["source_phase"] == "BR-19"
    assert first_record["candidate_scores"]["label"] == RESEARCH_ONLY
    assert first_record["option_chain_quality"]["label"] == MONITOR_ONLY
    assert first_record["contract_scores"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["thesis_package_references"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["risk_gate_reasons"]["label"] == PAPER_ONLY
    assert first_record["paper_only_portfolio_state"]["label"] == PAPER_ONLY
    assert first_record["monitor_outcomes"]["label"] == MONITOR_ONLY
    assert payload["rejected_records"][0]["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["sent_for_review_records"][0]["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["source_evidence"][0]["source_replay_id"] == "BR19-REPLAY-001"


def test_br20_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br20_journal_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    journal = run_paper_research_decision_journal(out_dir=out_dir)
    payload = paper_research_decision_journal_payload(journal)

    assert payload["acceptance_criteria"]["read_only_paper_records"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br20_markdown_script_and_doc_record_required_sections() -> None:
    journal = build_paper_research_decision_journal()
    markdown = render_markdown_paper_research_decision_journal(journal)
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-20 Paper Research Decision Journal" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Decision Records" in markdown
    assert "## Held" in markdown
    assert "## Rejected" in markdown
    assert "## Sent For Review" in markdown
    assert "## Source Evidence" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "BR20-JOURNAL-001" in markdown
    assert "sent_for_review" in markdown
    assert "explains why paper candidates were held, rejected, or sent for review" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1


def test_br20_validation_rejects_unsafe_journal_mutations() -> None:
    journal = build_paper_research_decision_journal()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(journal, safety={**journal.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(journal, safety={**journal.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(journal, safety={**journal.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(journal, safety={**journal.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(journal, safety={**journal.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(journal, safety={**journal.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(journal, label=MONITOR_ONLY).validate()


def test_br20_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
    assert "from broker" not in source
    assert "import broker" not in source
