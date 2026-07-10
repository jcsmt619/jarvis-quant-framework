from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br23_promotion_gate_evidence_checklist import (
    CHECKLIST_CLASSIFICATIONS,
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_EVIDENCE_CATEGORIES,
    build_promotion_gate_evidence_checklist,
    promotion_gate_evidence_checklist_payload,
    render_markdown_promotion_gate_evidence_checklist,
    run_promotion_gate_evidence_checklist,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br23_promotion_gate_evidence_checklist.py")
SCRIPT_PATH = Path("scripts/run_br23_promotion_gate_evidence_checklist.py")
DOC_PATH = Path("docs/brendan_strategy/br23_promotion_gate_evidence_checklist.md")


def test_br23_safety_manifest_is_read_only_offline_and_disabled() -> None:
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
    assert manifest["read_only"] is True
    assert manifest["offline_only"] is True
    assert manifest["committed_report_inputs_only"] is True
    assert manifest["deterministic_checklist_records_only"] is True
    assert manifest["live_trading_authorized"] is False
    assert manifest["broker_actions_authorized"] is False
    assert manifest["order_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["paper_state_mutation_allowed"] is False
    assert manifest["trading_state_mutation_allowed"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br23_builds_checklist_from_committed_promotion_evidence() -> None:
    checklist = build_promotion_gate_evidence_checklist()
    payload = promotion_gate_evidence_checklist_payload(checklist)

    assert all(path.exists() for path in DEFAULT_SOURCE_PATHS.values())
    assert payload["phase"] == "BR-23"
    assert payload["module"] == "Promotion Gate Evidence Checklist"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["source_paths"]) == {"BR-18", "BR-19", "BR-20", "BR-21", "BR-22"}
    assert payload["required_evidence_categories"] == REQUIRED_EVIDENCE_CATEGORIES
    assert payload["checklist_classifications"] == CHECKLIST_CLASSIFICATIONS
    assert payload["metrics"]["checklist_record_count"] == 4
    assert payload["metrics"]["blocked_count"] == 1
    assert payload["metrics"]["review_required_count"] == 1
    assert payload["metrics"]["paper_only_count"] == 2
    assert payload["metrics"]["missing_evidence_count"] == 0
    assert payload["metrics"]["unresolved_review_item_count"] >= 10
    assert payload["metrics"]["required_human_review_action_count"] == 6
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["later_review_stage_allowed"] is True
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert payload["readiness_state"]["order_paths_allowed"] is False
    assert payload["readiness_state"]["data_provider_calls_allowed"] is False
    assert payload["readiness_state"]["paper_state_mutation_allowed"] is False
    assert payload["readiness_state"]["trading_state_mutation_allowed"] is False


def test_br23_records_cover_required_evidence_and_classification_boundaries() -> None:
    checklist = build_promotion_gate_evidence_checklist()
    payload = promotion_gate_evidence_checklist_payload(checklist)
    first_record = payload["records"][0]
    blocked_record = payload["records_by_classification"]["blocked"][0]
    review_record = payload["records_by_classification"]["review_required"][0]

    assert set(first_record["evidence"]) == set(REQUIRED_EVIDENCE_CATEGORIES)
    assert first_record["classification"] == "paper_only"
    assert first_record["label"] == PAPER_ONLY
    assert first_record["evidence"]["source_freshness"]["label"] == RESEARCH_ONLY
    assert first_record["evidence"]["scenario_coverage"]["label"] == MONITOR_ONLY
    assert first_record["evidence"]["decision_journal_completeness"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["evidence"]["paper_outcome_tracking"]["label"] == PAPER_ONLY
    assert first_record["evidence"]["stale_data_rejection"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert first_record["evidence"]["liquidity_rejection"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert first_record["advancement_boundary"]["later_review_stage_allowed"] is True
    assert first_record["advancement_boundary"]["live_trading_authorized"] is False
    assert first_record["advancement_boundary"]["broker_actions_authorized"] is False
    assert first_record["advancement_boundary"]["order_paths_authorized"] is False
    assert blocked_record["classification"] == "blocked"
    assert blocked_record["label"] == BLOCKED_BY_SAFETY_GATE
    assert blocked_record["advancement_boundary"]["later_review_stage_allowed"] is False
    assert review_record["classification"] == "review_required"
    assert review_record["label"] == HUMAN_REVIEW_REQUIRED


def test_br23_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br23_promotion_gate_checklist_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    checklist = run_promotion_gate_evidence_checklist(out_dir=out_dir)
    payload = promotion_gate_evidence_checklist_payload(checklist)

    assert payload["acceptance_criteria"]["stale_data_rejection_recorded"] is True
    assert payload["acceptance_criteria"]["liquidity_rejection_recorded"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br23_markdown_script_and_doc_record_required_sections() -> None:
    checklist = build_promotion_gate_evidence_checklist()
    markdown = render_markdown_promotion_gate_evidence_checklist(checklist)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-23 Promotion Gate Evidence Checklist" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Required Evidence" in markdown
    assert "## Checklist Records" in markdown
    assert "## Classifications" in markdown
    assert "BR23-CHECKLIST-001" in markdown
    for category in REQUIRED_EVIDENCE_CATEGORIES:
        assert category in markdown
        assert category in doc_text
    for classification in CHECKLIST_CLASSIFICATIONS:
        assert classification in markdown
    assert "blocked, review-required, or paper-only" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br23_validation_rejects_unsafe_checklist_mutations() -> None:
    checklist = build_promotion_gate_evidence_checklist()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(checklist, safety={**checklist.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(checklist, safety={**checklist.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(checklist, safety={**checklist.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(checklist, safety={**checklist.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(checklist, safety={**checklist.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot allow live_trading_authorized"):
        replace(checklist, safety={**checklist.safety, "live_trading_authorized": True}).validate()

    with pytest.raises(ValueError, match="cannot allow broker_actions_authorized"):
        replace(checklist, safety={**checklist.safety, "broker_actions_authorized": True}).validate()

    with pytest.raises(ValueError, match="cannot allow order_paths_authorized"):
        replace(checklist, safety={**checklist.safety, "order_paths_authorized": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(checklist, safety={**checklist.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(checklist, label=MONITOR_ONLY).validate()


def test_br23_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
