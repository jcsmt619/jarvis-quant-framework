from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br22_paper_outcome_tracker import (
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    OUTCOME_CLASSIFICATIONS,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_OUTCOME_FIELDS,
    build_paper_outcome_tracker,
    paper_outcome_tracker_payload,
    render_markdown_paper_outcome_tracker,
    run_paper_outcome_tracker,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br22_paper_outcome_tracker.py")
SCRIPT_PATH = Path("scripts/run_br22_paper_outcome_tracker.py")
DOC_PATH = Path("docs/brendan_strategy/br22_paper_outcome_tracker.md")


def test_br22_safety_manifest_is_offline_report_only_and_disabled() -> None:
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
    assert manifest["deterministic_outcome_records_only"] is True
    assert manifest["paper_state_mutation_allowed"] is False
    assert manifest["trading_state_mutation_allowed"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br22_builds_outcome_tracker_from_committed_br20_and_br21_reports() -> None:
    tracker = build_paper_outcome_tracker()
    payload = paper_outcome_tracker_payload(tracker)

    assert all(path.exists() for path in DEFAULT_SOURCE_PATHS.values())
    assert payload["phase"] == "BR-22"
    assert payload["module"] == "Paper Outcome Tracker"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["source_paths"]) == {"BR-20", "BR-21"}
    assert payload["outcome_classifications"] == OUTCOME_CLASSIFICATIONS
    assert payload["required_outcome_fields"] == REQUIRED_OUTCOME_FIELDS
    assert payload["metrics"]["outcome_record_count"] == 4
    assert payload["metrics"]["paper_held_count"] == 2
    assert payload["metrics"]["rejected_count"] == 1
    assert payload["metrics"]["sent_for_review_count"] == 1
    assert payload["metrics"]["paper_entry_state_count"] == 4
    assert payload["metrics"]["hypothetical_mark_change_count"] == 4
    assert payload["metrics"]["monitoring_observation_count"] == 4
    assert payload["metrics"]["unresolved_review_item_count"] >= 10
    assert payload["metrics"]["required_human_review_action_count"] == 6
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert payload["readiness_state"]["order_paths_allowed"] is False
    assert payload["readiness_state"]["paper_state_mutation_allowed"] is False
    assert payload["readiness_state"]["trading_state_mutation_allowed"] is False


def test_br22_records_track_required_outcome_fields() -> None:
    tracker = build_paper_outcome_tracker()
    payload = paper_outcome_tracker_payload(tracker)
    first_record = payload["records"][0]

    for field_name in REQUIRED_OUTCOME_FIELDS:
        assert field_name in first_record
    assert first_record["outcome_classification"] == "paper_held"
    assert first_record["label"] == PAPER_ONLY
    assert first_record["source_evidence"]["source_phase"] == "BR-20"
    assert first_record["source_evidence"]["resolution_source_phase"] == "BR-21"
    assert first_record["source_evidence"]["read_only"] is True
    assert first_record["paper_only_entry_state"]["label"] == PAPER_ONLY
    assert first_record["paper_only_entry_state"]["paper_position_open"] is True
    assert first_record["hypothetical_mark_change"]["label"] == MONITOR_ONLY
    assert first_record["hypothetical_mark_change"]["method"] == "deterministic_fixture_proxy"
    assert first_record["monitoring_observations"]["label"] == MONITOR_ONLY
    assert first_record["thesis_status"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["risk_gate_status"]["label"] == PAPER_ONLY
    assert first_record["dashboard_state"]["LIVE TRADING"] == "DISABLED"
    assert payload["records_by_outcome_classification"]["rejected"][0]["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["records_by_outcome_classification"]["sent_for_review"][0]["label"] == HUMAN_REVIEW_REQUIRED
    assert all(item["label"] == RESEARCH_ONLY for item in payload["source_evidence"])


def test_br22_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br22_outcome_tracker_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    tracker = run_paper_outcome_tracker(out_dir=out_dir)
    payload = paper_outcome_tracker_payload(tracker)

    assert payload["acceptance_criteria"]["mark_changes_are_hypothetical_monitor_only"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br22_markdown_script_and_doc_record_required_sections() -> None:
    tracker = build_paper_outcome_tracker()
    markdown = render_markdown_paper_outcome_tracker(tracker)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-22 Paper Outcome Tracker" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Source Evidence" in markdown
    assert "## Outcome Records" in markdown
    assert "## Classifications" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "BR22-OUTCOME-001" in markdown
    for classification in OUTCOME_CLASSIFICATIONS:
        assert classification in markdown
    assert "paper-held, rejected, and sent-for-review outcomes" in doc_text
    assert "hypothetical mark changes" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br22_validation_rejects_unsafe_tracker_mutations() -> None:
    tracker = build_paper_outcome_tracker()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(tracker, safety={**tracker.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(tracker, safety={**tracker.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(tracker, safety={**tracker.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(tracker, safety={**tracker.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(tracker, safety={**tracker.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot allow paper state mutation"):
        replace(tracker, safety={**tracker.safety, "paper_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow trading state mutation"):
        replace(tracker, safety={**tracker.safety, "trading_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(tracker, safety={**tracker.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(tracker, label=MONITOR_ONLY).validate()


def test_br22_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
