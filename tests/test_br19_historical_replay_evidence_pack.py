from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br19_historical_replay_evidence_pack import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REPLAY_SECTIONS,
    build_historical_replay_evidence_pack,
    historical_replay_evidence_pack_payload,
    render_markdown_historical_replay_evidence_pack,
    run_historical_replay_evidence_pack,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br19_historical_replay_evidence_pack.py")
SCRIPT_PATH = Path("scripts/run_br19_historical_replay_evidence_pack.py")
DOC_PATH = Path("docs/brendan_strategy/br19_historical_replay_evidence_pack.md")


def test_br19_safety_manifest_is_offline_replay_only_and_disabled() -> None:
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
    assert manifest["offline_replay_only"] is True
    assert manifest["fixture_only"] is True
    assert manifest["deterministic_replay_records_only"] is True
    assert manifest["paper_portfolio_updates_simulated"] is True
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br19_builds_evidence_pack_from_committed_fixture() -> None:
    pack = build_historical_replay_evidence_pack()
    payload = historical_replay_evidence_pack_payload(pack)

    assert DEFAULT_FIXTURE_PATH.exists()
    assert payload["phase"] == "BR-19"
    assert payload["module"] == "Historical Replay Evidence Pack"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["replay_sections"] == REPLAY_SECTIONS
    assert payload["metrics"]["replay_window_count"] == 3
    assert payload["metrics"]["replay_record_count"] == 4
    assert payload["metrics"]["paper_only_change_count"] == 2
    assert payload["metrics"]["blocked_risk_gate_count"] == 1
    assert payload["metrics"]["human_review_risk_gate_count"] == 1
    assert payload["metrics"]["paper_only_risk_gate_count"] == 2
    assert payload["metrics"]["unresolved_review_item_count"] == 5
    assert payload["metrics"]["human_review_action_count"] == 6
    assert all(payload["acceptance_criteria"].values())
    assert {item["scenario_type"] for item in payload["scenario_provenance"]} == {
        "bullish",
        "poor-liquidity",
        "neutral",
        "paper-hold",
    }


def test_br19_payload_summarizes_required_replay_sections() -> None:
    pack = build_historical_replay_evidence_pack()
    payload = historical_replay_evidence_pack_payload(pack)
    first_record = payload["records"][0]

    for section_name in REPLAY_SECTIONS:
        assert section_name in first_record
    assert first_record["candidate_decision"]["label"] == RESEARCH_ONLY
    assert first_record["option_chain_state"]["label"] == MONITOR_ONLY
    assert first_record["contract_scoring"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["thesis_context"]["label"] == HUMAN_REVIEW_REQUIRED
    assert first_record["risk_gate_outcome"]["label"] == PAPER_ONLY
    assert first_record["paper_portfolio_change"]["label"] == PAPER_ONLY
    assert first_record["monitor_observation"]["label"] == MONITOR_ONLY
    assert first_record["dashboard_reference"]["label"] == MONITOR_ONLY
    assert payload["risk_gate_outcomes"][1]["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["paper_only_portfolio_changes"][0]["change"] == "simulated_entry"
    assert payload["dashboard_references"][3]["reference"] == "BR19-DASH-NVDA-HOLD"


def test_br19_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br19_replay_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    pack = run_historical_replay_evidence_pack(out_dir=out_dir)
    payload = historical_replay_evidence_pack_payload(pack)

    assert payload["acceptance_criteria"]["offline_replay_only"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br19_markdown_script_and_doc_record_required_sections() -> None:
    pack = build_historical_replay_evidence_pack()
    markdown = render_markdown_historical_replay_evidence_pack(pack)
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-19 Historical Replay Evidence Pack" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Replay Windows" in markdown
    assert "## Replay Records" in markdown
    assert "## Unresolved Review Items" in markdown
    assert "BR19-REPLAY-001" in markdown
    assert "paper_hold" in markdown
    assert "replay windows, scenario provenance, candidate decisions" in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "live_state_mutation_attempted=false" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert SCRIPT_PATH.read_text(encoding="utf-8").count("LIVE TRADING: DISABLED") == 1


def test_br19_validation_rejects_unsafe_replay_mutations() -> None:
    pack = build_historical_replay_evidence_pack()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(pack, safety={**pack.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(pack, safety={**pack.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(pack, safety={**pack.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(pack, safety={**pack.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(pack, safety={**pack.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(pack, safety={**pack.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(pack, label=MONITOR_ONLY).validate()


def test_br19_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
