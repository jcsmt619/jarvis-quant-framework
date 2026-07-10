from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br15_session_evidence_review_gate import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_REPORT_DIR,
    EXPECTED_ARTIFACTS,
    EXPECTED_SESSION_FLOW,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    build_session_evidence_review_report,
    render_markdown_session_evidence_review,
    run_session_evidence_review_gate,
    safety_manifest,
    session_evidence_review_payload,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br15_session_evidence_review_gate.py")
SCRIPT_PATH = Path("scripts/run_br15_session_evidence_review_gate.py")
DOC_PATH = Path("docs/brendan_strategy/br15_session_evidence_review_gate.md")


def test_br15_safety_manifest_is_evidence_review_only_and_disabled() -> None:
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
    assert manifest["evidence_review_only"] is True
    assert manifest["read_only_evidence_access"] is True
    assert manifest["session_rerun_attempted"] is False
    assert manifest["evidence_mutation_attempted"] is False
    assert manifest["artifact_deletion_attempted"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br15_reviews_committed_br14_evidence_without_mutating_source_files() -> None:
    out_dir = Path(".codex_pytest_tmp/br15_review_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    before_hashes = _hash_evidence_files(DEFAULT_EVIDENCE_DIR)
    report = run_session_evidence_review_gate(out_dir=out_dir)
    payload = session_evidence_review_payload(report)
    after_hashes = _hash_evidence_files(DEFAULT_EVIDENCE_DIR)

    assert before_hashes == after_hashes
    assert payload["phase"] == "BR-15"
    assert payload["source_phase"] == "BR-14"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["evidence_integrity"]["expected_artifact_count"] == len(EXPECTED_ARTIFACTS)
    assert payload["evidence_integrity"]["json_artifacts_present"] == len(EXPECTED_ARTIFACTS)
    assert payload["evidence_integrity"]["markdown_artifacts_present"] == len(EXPECTED_ARTIFACTS)
    assert payload["evidence_integrity"]["json_artifacts_valid"] == len(EXPECTED_ARTIFACTS)
    assert payload["evidence_integrity"]["session_written_artifacts_empty"] is True
    assert payload["session_metrics"]["simulated_paper_fill_count"] == 2
    assert payload["session_flow_completeness"]["observed_flow"] == EXPECTED_SESSION_FLOW
    assert payload["session_flow_completeness"]["complete"] is True
    assert payload["simulated_paper_contracts"] == ("NVDA-20271217-C-140", "NVDA-20271217-C-180")
    assert payload["monitor_alerts"] == ()
    assert payload["readiness_state"]["state"] == "BLOCKED_BY_SAFETY_GATE_HUMAN_REVIEW_REQUIRED"
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert all(payload["acceptance_criteria"].values())
    assert "source_written_artifacts_field_empty_review_file_presence_instead" in payload["unresolved_review_items"]
    assert (out_dir / "session_evidence_review_gate.json").exists()
    assert (out_dir / "session_evidence_review_gate.md").exists()

    shutil.rmtree(out_dir)


def test_br15_markdown_and_script_record_review_gate_sections() -> None:
    report = build_session_evidence_review_report()
    markdown = render_markdown_session_evidence_review(report)

    assert "BR-15 Session Evidence Review Gate" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Evidence Integrity" in markdown
    assert "## Safety Manifest" in markdown
    assert "## Session Metrics" in markdown
    assert "## Generated Artifact Presence" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "Evidence review only; the BR-14 session is not rerun." in markdown
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)


def test_br15_validation_rejects_unsafe_review_mutations() -> None:
    report = build_session_evidence_review_report()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(report, safety={**report.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set session_rerun_attempted"):
        replace(report, safety={**report.safety, "session_rerun_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set evidence_mutation_attempted"):
        replace(report, safety={**report.safety, "evidence_mutation_attempted": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(report, safety={**report.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(report, label=MONITOR_ONLY).validate()


def test_br15_detects_missing_artifacts_in_copied_evidence() -> None:
    source_dir = DEFAULT_EVIDENCE_DIR
    temp_dir = Path(".codex_pytest_tmp/br15_missing_artifact")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    shutil.copytree(source_dir, temp_dir)
    (temp_dir / "br08_position_monitor" / "daily_position_monitor_alerts.md").unlink()

    report = build_session_evidence_review_report(evidence_dir=temp_dir)
    payload = session_evidence_review_payload(report)

    assert payload["evidence_integrity"]["missing_artifacts"] == ("position_monitor",)
    assert payload["acceptance_criteria"]["expected_json_and_markdown_artifacts_present"] is False
    assert "acceptance_criterion_failed:expected_json_and_markdown_artifacts_present" in payload["unresolved_review_items"]

    shutil.rmtree(temp_dir)


def test_br15_doc_records_scope_outputs_and_safety_flags() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-15 Session Evidence Review Gate" in text
    assert "LIVE TRADING: DISABLED" in text
    assert "committed BR-14 local paper research session evidence" in text
    assert "does not rerun the BR-14 session" in text
    assert "does not mutate evidence" in text
    assert "does not delete artifacts" in text
    assert "does not load credentials" in text
    assert "does not connect to Alpaca, IBKR, TradeStation, or any broker" in text
    assert "does not call broker endpoints" in text
    assert "does not create broker actions" in text
    assert "does not create order paths" in text
    assert "does not enable live trading" in text
    assert "session_rerun_attempted=false" in text
    assert "evidence_mutation_attempted=false" in text
    assert "artifact_deletion_attempted=false" in text
    assert "broker_order_call_performed=false" in text
    assert "broker_order_submitted=false" in text
    assert "broker_order_routing_enabled=false" in text
    assert "live_trading_enabled=false" in text
    assert "session_evidence_review_gate.json" in text
    assert "session_evidence_review_gate.md" in text


def test_br15_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source


def _hash_evidence_files(evidence_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_json, relative_md in EXPECTED_ARTIFACTS.values():
        for relative_path in (relative_json, relative_md):
            path = evidence_dir / relative_path
            hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
            json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else None
    return hashes
