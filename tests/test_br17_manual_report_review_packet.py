from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br17_manual_report_review_packet import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_REPORT_DIR,
    EVIDENCE_ARTIFACTS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    build_manual_report_review_packet,
    manual_report_review_packet_payload,
    render_markdown_manual_report_review_packet,
    run_manual_report_review_packet,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br17_manual_report_review_packet.py")
SCRIPT_PATH = Path("scripts/run_br17_manual_report_review_packet.py")
DOC_PATH = Path("docs/brendan_strategy/br17_manual_report_review_packet.md")


def test_br17_safety_manifest_is_read_only_and_disabled() -> None:
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
    assert manifest["manual_review_packet_only"] is True
    assert manifest["session_rerun_attempted"] is False
    assert manifest["evidence_mutation_attempted"] is False
    assert manifest["artifact_deletion_attempted"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br17_builds_packet_from_committed_br14_evidence_without_mutation() -> None:
    out_dir = Path(".codex_pytest_tmp/br17_packet_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    before_hashes = _hash_evidence_files(DEFAULT_EVIDENCE_DIR)
    packet = run_manual_report_review_packet(out_dir=out_dir)
    payload = manual_report_review_packet_payload(packet)
    after_hashes = _hash_evidence_files(DEFAULT_EVIDENCE_DIR)

    assert before_hashes == after_hashes
    assert payload["phase"] == "BR-17"
    assert payload["source_phase"] == "BR-14"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["source_session_summary"]["metrics"]["simulated_paper_fill_count"] == 2
    assert payload["candidate_universe_summary"]["metrics"]["candidate_count"] == 5
    assert payload["options_chain_quality_summary"]["metrics"]["passed_chain_count"] == 1
    assert payload["contract_scoring_summary"]["metrics"]["suitable_contract_count"] == 4
    assert payload["llm_thesis_package_summary"]["metrics"]["prompt_package_count"] == 1
    assert payload["deterministic_risk_gate_summary"]["metrics"]["paper_only_count"] == 2
    assert payload["paper_portfolio_state"]["net_liquidation_value"] == 100143.2
    assert payload["monitor_alert_summary"]["metrics"]["alert_count"] == 0
    assert payload["operator_dashboard_references"]["metrics"]["candidate_count"] == 5
    assert payload["simulated_paper_contracts"][0]["simulated_fill"] is True
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["broker_actions_allowed"] is False
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()

    shutil.rmtree(out_dir)


def test_br17_hold_reject_review_categories_are_deterministic() -> None:
    packet = build_manual_report_review_packet()
    payload = manual_report_review_packet_payload(packet)
    categories = payload["hold_reject_review_categories"]

    assert categories["hold"] == ("NVDA-20271217-C-140", "NVDA-20271217-C-180")
    assert categories["review"] == ("NVDA-20271217-C-220",)
    assert categories["reject"] == (
        "NVDA-20271217-C-260",
        "ABCD-20260821-C-45",
        "ABCD-20260821-C-55",
    )
    assert "Should hold-category paper contracts remain paper-only monitored items" in payload["review_questions"][3]
    assert "Human reviewer must verify PAPER_ONLY items are simulated paper records" in payload["required_human_review_actions"][2]


def test_br17_markdown_script_and_doc_record_required_sections() -> None:
    packet = build_manual_report_review_packet()
    markdown = render_markdown_manual_report_review_packet(packet)
    doc = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-17 BR-14 Manual Report Review Packet" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Candidate Universe" in markdown
    assert "## Options Chain Quality" in markdown
    assert "## Contract Scoring" in markdown
    assert "## LLM Thesis Package" in markdown
    assert "## Deterministic Risk Gate Decisions" in markdown
    assert "## Simulated Paper Contracts" in markdown
    assert "## Paper Portfolio State" in markdown
    assert "## Monitor Alerts" in markdown
    assert "## Operator Dashboard References" in markdown
    assert "## Hold Reject Review Categories" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "No session rerun, evidence edit, credential loading, data-provider call" in markdown
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1
    assert "does not rerun the BR-14 session" in doc
    assert "does not edit evidence" in doc
    assert "does not load credentials" in doc
    assert "does not call data providers" in doc
    assert "does not create broker actions" in doc
    assert "does not create order paths" in doc
    assert "live_trading_enabled=false" in doc
    assert JSON_REPORT_NAME in doc
    assert MARKDOWN_REPORT_NAME in doc


def test_br17_validation_rejects_unsafe_packet_mutations() -> None:
    packet = build_manual_report_review_packet()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(packet, safety={**packet.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(packet, safety={**packet.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(packet, safety={**packet.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set trade_instruction_created"):
        replace(packet, safety={**packet.safety, "trade_instruction_created": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(packet, safety={**packet.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(packet, label=MONITOR_ONLY).validate()


def test_br17_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
        "alpaca",
        "ib_insync",
        "tradeStation",
    ]

    for label in disallowed:
        assert label not in source


def _hash_evidence_files(evidence_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in EVIDENCE_ARTIFACTS.values():
        path = evidence_dir / relative_path
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
        json.loads(path.read_text(encoding="utf-8"))
    return hashes
