from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br21_human_review_resolution_ledger import (
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_LEDGER_FIELDS,
    RESOLUTION_CATEGORIES,
    build_human_review_resolution_ledger,
    human_review_resolution_ledger_payload,
    render_markdown_human_review_resolution_ledger,
    run_human_review_resolution_ledger,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br21_human_review_resolution_ledger.py")
SCRIPT_PATH = Path("scripts/run_br21_human_review_resolution_ledger.py")
DOC_PATH = Path("docs/brendan_strategy/br21_human_review_resolution_ledger.md")


def test_br21_safety_manifest_is_read_only_offline_and_disabled() -> None:
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
    assert manifest["deterministic_ledger_records_only"] is True
    assert manifest["trading_state_mutation_allowed"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br21_builds_resolution_ledger_from_br17_through_br20_sources() -> None:
    ledger = build_human_review_resolution_ledger()
    payload = human_review_resolution_ledger_payload(ledger)

    assert all(path.exists() for path in DEFAULT_SOURCE_PATHS.values())
    assert payload["phase"] == "BR-21"
    assert payload["module"] == "Human Review Resolution Ledger"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["source_paths"]) == {"BR-17", "BR-18", "BR-19", "BR-20"}
    assert payload["resolution_categories"] == RESOLUTION_CATEGORIES
    assert payload["required_ledger_fields"] == REQUIRED_LEDGER_FIELDS
    assert payload["metrics"]["source_phase_count"] == 4
    assert payload["metrics"]["resolution_record_count"] >= 20
    for category in RESOLUTION_CATEGORIES:
        assert payload["metrics"][f"{category}_count"] > 0
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert payload["readiness_state"]["trading_state_mutation_allowed"] is False


def test_br21_records_include_required_resolution_fields_and_boundaries() -> None:
    ledger = build_human_review_resolution_ledger()
    payload = human_review_resolution_ledger_payload(ledger)
    first_record = payload["records"][0]

    for field_name in REQUIRED_LEDGER_FIELDS:
        assert field_name in first_record
    assert first_record["source_evidence"]["label"] == RESEARCH_ONLY
    assert first_record["source_evidence"]["read_only"] is True
    assert first_record["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["immutable_safety_boundaries"]["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert first_record["immutable_safety_boundaries"]["trading_state_mutation_allowed"] is False
    assert first_record["immutable_safety_boundaries"]["broker_actions_allowed"] is False
    assert first_record["immutable_safety_boundaries"]["order_paths_allowed"] is False
    assert first_record["immutable_safety_boundaries"]["LIVE TRADING"] == "DISABLED"
    assert set(item["source_phase"] for item in payload["source_evidence"]) == {"BR-17", "BR-18", "BR-19", "BR-20"}


def test_br21_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br21_resolution_ledger_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    ledger = run_human_review_resolution_ledger(out_dir=out_dir)
    payload = human_review_resolution_ledger_payload(ledger)

    assert payload["acceptance_criteria"]["source_evidence_is_read_only"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br21_markdown_script_and_doc_record_required_sections() -> None:
    ledger = build_human_review_resolution_ledger()
    markdown = render_markdown_human_review_resolution_ledger(ledger)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-21 Human Review Resolution Ledger" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Source Evidence" in markdown
    assert "## Resolution Records" in markdown
    assert "## Categories" in markdown
    assert "## Required Follow-Up" in markdown
    assert "BR21-RESOLUTION-001" in markdown
    for category in RESOLUTION_CATEGORIES:
        assert category in markdown
        assert category in doc_text
    assert "without changing trading state" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br21_validation_rejects_unsafe_ledger_mutations() -> None:
    ledger = build_human_review_resolution_ledger()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(ledger, safety={**ledger.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(ledger, safety={**ledger.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(ledger, safety={**ledger.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(ledger, safety={**ledger.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(ledger, safety={**ledger.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot allow trading state mutation"):
        replace(ledger, safety={**ledger.safety, "trading_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(ledger, safety={**ledger.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(ledger, label=MONITOR_ONLY).validate()


def test_br21_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
