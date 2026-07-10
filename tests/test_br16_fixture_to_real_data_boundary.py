from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br16_fixture_to_real_data_boundary import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REDACTED_FIELDS,
    build_fixture_to_real_data_boundary_report,
    fixture_to_real_data_boundary_payload,
    render_markdown_fixture_to_real_data_boundary,
    run_fixture_to_real_data_boundary,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br16_fixture_to_real_data_boundary.py")
SCRIPT_PATH = Path("scripts/run_br16_fixture_to_real_data_boundary.py")
DOC_PATH = Path("docs/brendan_strategy/br16_fixture_to_real_data_boundary.md")


def test_br16_safety_manifest_keeps_boundary_design_offline_and_disabled() -> None:
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
    assert manifest["fixture_data_default"] is True
    assert manifest["offline_tests_preserved"] is True
    assert manifest["read_only_real_data_design_only"] is True
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br16_builds_boundary_payload_from_fixture_without_credentials_or_fetches() -> None:
    report = build_fixture_to_real_data_boundary_report()
    payload = fixture_to_real_data_boundary_payload(report)

    assert payload["phase"] == "BR-16"
    assert payload["module"] == "Fixture to Real Data Boundary Design"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["metrics"]["interface_count"] == 2
    assert payload["metrics"]["validation_rule_count"] >= 4
    assert payload["metrics"]["schema_count"] == 2
    assert payload["metrics"]["staleness_rule_count"] == 3
    assert payload["metrics"]["provenance_record_count"] == 2
    assert payload["metrics"]["cache_policy_count"] == 1
    assert set(REDACTED_FIELDS).issubset(set(payload["redaction_rules"]))
    assert all(item["credential_required"] is False for item in payload["provenance_records"])
    assert all(item["read_only"] is True for item in payload["provenance_records"])
    assert all("credentials" in item["prohibited_inputs"] for item in payload["interfaces"])
    assert all("env_file" in item["prohibited_inputs"] for item in payload["interfaces"])
    assert all(any("broker" in value for value in item["prohibited_inputs"]) for item in payload["interfaces"])
    assert all(any("order" in value for value in item["prohibited_inputs"]) for item in payload["interfaces"])
    assert all(item["failure_label"] == BLOCKED_BY_SAFETY_GATE for item in payload["validation_rules"])
    assert all(payload["acceptance_criteria"].values())
    assert payload["safety"]["real_data_fetch_attempted"] is False
    assert payload["safety"]["external_network_call_attempted"] is False
    assert payload["safety"]["broker_connection_attempted"] is False
    assert payload["safety"]["live_trading_enabled"] is False


def test_br16_runner_writes_reports_to_requested_output_directory() -> None:
    out_dir = Path(".codex_pytest_tmp/br16_boundary_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    report = run_fixture_to_real_data_boundary(out_dir=out_dir)
    payload = fixture_to_real_data_boundary_payload(report)

    assert payload["acceptance_criteria"]["fixture_data_remains_default"] is True
    assert (out_dir / "fixture_to_real_data_boundary.json").exists()
    assert (out_dir / "fixture_to_real_data_boundary.md").exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br16_markdown_script_and_doc_record_required_boundary_sections() -> None:
    report = build_fixture_to_real_data_boundary_report()
    markdown = render_markdown_fixture_to_real_data_boundary(report)
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-16 Fixture to Real Data Boundary Design" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Interfaces" in markdown
    assert "## Validation Rules" in markdown
    assert "## Schemas" in markdown
    assert "## Staleness Checks" in markdown
    assert "## Provenance Records" in markdown
    assert "## Cache Boundaries" in markdown
    assert "## Fallback Behavior" in markdown
    assert "## Redaction Rules" in markdown
    assert "## Test Fixtures" in markdown
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1
    assert "does not read `.env`" in doc_text
    assert "does not fetch real market data at runtime" in doc_text
    assert "does not create order paths" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert "fixture_to_real_data_boundary.json" in doc_text
    assert "fixture_to_real_data_boundary.md" in doc_text


def test_br16_validation_rejects_unsafe_boundary_mutations() -> None:
    report = build_fixture_to_real_data_boundary_report()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(report, safety={**report.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set env_file_read_attempted"):
        replace(report, safety={**report.safety, "env_file_read_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(report, safety={**report.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set real_data_fetch_attempted"):
        replace(report, safety={**report.safety, "real_data_fetch_attempted": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(report, label=MONITOR_ONLY).validate()


def test_br16_fixture_file_is_used_and_preserves_offline_test_references() -> None:
    assert DEFAULT_FIXTURE_PATH.exists()
    report = build_fixture_to_real_data_boundary_report(DEFAULT_FIXTURE_PATH)
    payload = fixture_to_real_data_boundary_payload(report)

    assert "br16_fixture_to_real_data_boundary.json" in payload["test_fixtures"]
    assert "br03_options_chain_quality.json" in payload["test_fixtures"]
    assert "br02_candidate_universe.json" in payload["test_fixtures"]
    assert "fixture_snapshot_is_default_when_no_read_only_input_is_supplied" in payload["fallback_behaviors"]
    assert any(item["fallback_on_stale"] == "use_fixture_snapshot" for item in payload["staleness_rules"])
    assert any(item["fallback_behavior"] == "preserve_last_valid_fixture" for item in payload["cache_policies"])


def test_br16_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed_labels = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed_labels:
        assert label not in source
    assert "from broker" not in source
    assert "import broker" not in source
