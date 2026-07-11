from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br29_offline_snapshot_research_replay_evidence_pack import (
    DEFAULT_BR28_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    build_offline_snapshot_research_replay_evidence_pack,
    offline_snapshot_research_replay_evidence_pack_payload,
    render_markdown_offline_snapshot_research_replay_evidence_pack,
    run_offline_snapshot_research_replay_evidence_pack,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br29_offline_snapshot_research_replay_evidence_pack.py")
SCRIPT_PATH = Path("scripts/run_br29_offline_snapshot_research_replay_evidence_pack.py")
DOC_PATH = Path("docs/brendan_strategy/br29_offline_snapshot_research_replay_evidence_pack.md")


def test_br29_safety_manifest_is_offline_research_only_and_disabled() -> None:
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
    assert manifest["br28_snapshot_candidates_only"] is True
    assert manifest["frozen_deterministic_boundaries_used"] is True
    assert manifest["opportunity_driven_selection"] is True
    assert manifest["fixed_daily_trade_quota_imposed"] is False
    assert manifest["alpha_claim_created"] is False
    assert manifest["evaluation_period_tuning_performed"] is False
    assert manifest["parameter_optimization_performed"] is False
    assert manifest["broker_write_operations_authorized"] is False
    assert manifest["external_routing_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br29_replays_br28_candidates_without_fixed_trade_quota_or_alpha_claim() -> None:
    pack = build_offline_snapshot_research_replay_evidence_pack(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )
    payload = offline_snapshot_research_replay_evidence_pack_payload(pack)

    assert DEFAULT_BR28_REPORT_PATH.exists()
    assert payload["phase"] == "BR-29"
    assert payload["module"] == "Offline Snapshot Research Replay Evidence Pack"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["replay_checks"]["br28_report_accepted"] is True
    assert payload["replay_checks"]["opportunity_driven_selection"] is True
    assert payload["replay_checks"]["no_fixed_daily_trade_quota"] is True
    assert payload["replay_checks"]["post_decision_outcomes_available"] is False
    assert payload["metrics"]["candidate_count"] == 2
    assert payload["metrics"]["advanced_candidate_count"] == 2
    assert payload["metrics"]["trade_count"] == 2
    assert payload["metrics"]["turnover"] == 1.0
    assert payload["metrics"]["gross_exposure"] == 1.0
    assert payload["metrics"]["max_symbol_weight"] == 0.5
    assert payload["metrics"]["alpha_claimed"] is False
    assert payload["metrics"]["gross_research_return"] is None
    assert payload["metrics"]["sharpe"] is None
    assert payload["unsupported_metrics"]["gross_research_return"].startswith("unsupported")
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["alpha_claim_allowed"] is False
    assert all(item["label"] == PAPER_ONLY for item in payload["candidate_replay_decisions"])
    assert {item["symbol"] for item in payload["candidate_replay_decisions"]} == {"QQQ", "SPY"}


def test_br29_blocks_missing_br28_report_and_advances_zero_candidates() -> None:
    missing = Path(".codex_pytest_tmp/br29_missing/missing_br28.json")
    if missing.parent.exists():
        shutil.rmtree(missing.parent)
    missing.parent.mkdir(parents=True)

    pack = build_offline_snapshot_research_replay_evidence_pack(
        br28_report_path=missing,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = offline_snapshot_research_replay_evidence_pack_payload(pack)
    reasons = {reason for item in payload["unresolved_blockers"] for reason in item["reasons"]}

    assert payload["metrics"]["candidate_count"] == 0
    assert payload["metrics"]["advanced_candidate_count"] == 0
    assert payload["metrics"]["trade_count"] == 0
    assert payload["metrics"]["gross_exposure"] == 0.0
    assert "br28_report_missing" in reasons
    assert payload["replay_checks"]["br28_report_loaded"] is False
    assert payload["replay_checks"]["br28_report_accepted"] is False

    shutil.rmtree(missing.parent)


def test_br29_blocks_candidate_that_fails_liquidity_gate_without_blocking_independent_passers() -> None:
    tmp_path = Path(".codex_pytest_tmp/br29_bad_liquidity")
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    report_path = tmp_path / "br28_variant.json"
    payload = json.loads(DEFAULT_BR28_REPORT_PATH.read_text(encoding="utf-8"))
    payload["candidates"][0]["feature_inputs"]["volume"] = 10
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    pack = build_offline_snapshot_research_replay_evidence_pack(
        br28_report_path=report_path,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    report = offline_snapshot_research_replay_evidence_pack_payload(pack)
    blocked = [item for item in report["candidate_replay_decisions"] if item["label"] == BLOCKED_BY_SAFETY_GATE]
    advanced = [item for item in report["candidate_replay_decisions"] if item["label"] == PAPER_ONLY]

    assert report["metrics"]["candidate_count"] == 2
    assert report["metrics"]["advanced_candidate_count"] == 1
    assert report["metrics"]["blocked_candidate_count"] == 1
    assert report["metrics"]["trade_count"] == 1
    assert report["metrics"]["gross_exposure"] == 0.5
    assert blocked[0]["blocked_reasons"] == ("insufficient_liquidity",)
    assert advanced[0]["symbol"] == "SPY"

    shutil.rmtree(tmp_path)


def test_br29_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br29_replay_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    pack = run_offline_snapshot_research_replay_evidence_pack(
        out_dir=out_dir,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = offline_snapshot_research_replay_evidence_pack_payload(pack)

    assert payload["metrics"]["candidate_count"] == 2
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br29_markdown_script_and_doc_record_required_sections() -> None:
    pack = build_offline_snapshot_research_replay_evidence_pack(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )
    markdown = render_markdown_offline_snapshot_research_replay_evidence_pack(pack)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-29 Offline Snapshot Research Replay Evidence Pack" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Replay Checks" in markdown
    assert "## Supported Metrics" in markdown
    assert "## Unsupported Metrics" in markdown
    assert "## Cost Sensitivity" in markdown
    assert "## Symbol Contribution" in markdown
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not perform broker write operations" in doc_text
    assert "does not create external routing paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "does not mutate live state" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "fixed_daily_trade_quota_imposed=false" in doc_text
    assert "alpha_claim_created=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br29_validation_rejects_unsafe_mutations() -> None:
    pack = build_offline_snapshot_research_replay_evidence_pack(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(pack, safety={**pack.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(pack, safety={**pack.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(pack, safety={**pack.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(pack, safety={**pack.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow external_routing_paths_authorized"):
        replace(pack, safety={**pack.safety, "external_routing_paths_authorized": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(pack, safety={**pack.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(pack, label=MONITOR_ONLY).validate()


def test_br29_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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
