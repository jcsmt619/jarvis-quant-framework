from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
)
from engines.moonshot.deterministic.options_chain_quality_scanner import load_options_chain_quality_report
from engines.moonshot.deterministic.options_contract_scorer import load_contract_scoring_report
from engines.moonshot.deterministic.trade_score_risk_gate import (
    CandidateRiskContext,
    TradeScoreRiskGateConfig,
    build_trade_score_risk_gate_report,
    load_candidate_risk_contexts,
    load_trade_score_risk_gate_report,
    render_markdown_trade_score_risk_gate,
    safety_manifest,
    trade_score_risk_gate_payload,
    write_trade_score_risk_gate_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _config(**overrides: object) -> TradeScoreRiskGateConfig:
    values = {
        "min_chain_quality_score": 75,
        "min_contract_score": 75,
        "min_thesis_quality_score": 70,
        "min_monitor_score": 65,
        "min_human_review_score": 80,
        "min_paper_score": 90,
        "max_proposed_position_pct": 0.03,
        "max_symbol_concentration_pct": 0.06,
        "max_portfolio_drawdown_pct": 0.08,
        "max_candidate_drawdown_pct": 0.20,
        "min_days_to_catalyst": 14,
        "max_days_to_catalyst": 540,
    }
    values.update(overrides)
    return TradeScoreRiskGateConfig(**values)


def _reports() -> tuple[object, object, object]:
    contract_report = load_contract_scoring_report()
    analyst_report = build_analyst_thesis_report(response_text_by_prompt_id=load_fixture_analyst_responses())
    return load_options_chain_quality_report(), contract_report, analyst_report


def test_br06_safety_manifest_is_disabled_and_research_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-06"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["blocked_by_safety_gate"] is True
    assert manifest["deterministic_gate_only"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br06_loads_fixture_and_combines_required_risk_dimensions() -> None:
    report = load_trade_score_risk_gate_report(config=_config())
    payload = trade_score_risk_gate_payload(report)

    assert payload["phase"] == "BR-06"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["metrics"] == {
        "candidate_count": 6,
        "paper_only_count": 2,
        "human_review_required_count": 1,
        "monitor_only_count": 0,
        "research_only_count": 0,
        "blocked_count": 3,
    }
    top = payload["decisions"][0]
    assert top["contract_id"] == "NVDA-20271217-C-140"
    assert top["score"] == 97
    assert top["label"] == PAPER_ONLY
    assert top["human_review_required"] is True
    assert top["research_only"] is True
    assert top["live_trading_enabled"] is False
    assert top["broker_order_call_performed"] is False
    assert {component["name"] for component in top["component_scores"]} == {
        "chain_quality",
        "contract_score",
        "greeks",
        "liquidity",
        "thesis_quality",
        "concentration",
        "drawdown",
        "catalyst_timing",
    }


def test_br06_requires_human_review_for_near_catalyst_timing() -> None:
    payload = trade_score_risk_gate_payload(load_trade_score_risk_gate_report(config=_config()))
    decisions = {item["contract_id"]: item for item in payload["decisions"]}
    near_catalyst = decisions["NVDA-20271217-C-220"]

    assert near_catalyst["score"] == 87
    assert near_catalyst["label"] == HUMAN_REVIEW_REQUIRED
    assert near_catalyst["hard_block_reasons"] == ()
    assert near_catalyst["review_reasons"] == ("catalyst_too_near_for_new_risk",)


def test_br06_blocks_concentration_drawdown_chain_quality_and_contract_score_breaches() -> None:
    payload = trade_score_risk_gate_payload(load_trade_score_risk_gate_report(config=_config()))
    decisions = {item["contract_id"]: item for item in payload["decisions"]}

    concentrated = decisions["NVDA-20271217-C-260"]
    assert concentrated["label"] == BLOCKED_BY_SAFETY_GATE
    assert concentrated["hard_block_reasons"] == (
        "proposed_position_pct_above_maximum",
        "symbol_concentration_above_maximum",
    )

    weak_chain = decisions["ABCD-20260821-C-45"]
    assert weak_chain["label"] == BLOCKED_BY_SAFETY_GATE
    assert set(weak_chain["hard_block_reasons"]) == {
        "chain_quality_failed",
        "contract_score_failed",
        "portfolio_drawdown_above_maximum",
        "candidate_drawdown_above_maximum",
    }
    assert "thesis_quality_below_minimum" in weak_chain["review_reasons"]


def test_br06_payload_markdown_and_report_files_are_disabled_gate_outputs() -> None:
    report = load_trade_score_risk_gate_report(config=_config())
    markdown = render_markdown_trade_score_risk_gate(report)

    assert "BR-06 Deterministic Trade Score Risk Gate" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Deterministic trade score risk gate only; no broker routing or order submission." in markdown
    assert "Report-level state remains blocked by safety gate." in markdown

    out_dir = Path(".codex_pytest_tmp/br06_trade_score_risk_gate_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_trade_score_risk_gate_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-06"
    assert "Component Scores" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br06_validation_rejects_invalid_config_labels_and_empty_input() -> None:
    chain_report, contract_report, analyst_report = _reports()
    contexts = load_candidate_risk_contexts()

    with pytest.raises(ValueError, match="score thresholds must be ordered"):
        build_trade_score_risk_gate_report(
            chain_report,
            contract_report,
            analyst_report,
            contexts,
            config=_config(min_monitor_score=85, min_human_review_score=80),
        )

    with pytest.raises(ValueError, match="requires at least one candidate risk context"):
        build_trade_score_risk_gate_report(chain_report, contract_report, analyst_report, [], config=_config())

    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(contexts[0], symbol="nvda").validate()

    with pytest.raises(ValueError, match="safe research"):
        replace(contexts[0], label="UNSAFE_LABEL").validate()

    with pytest.raises(ValueError, match="cannot enable live trading"):
        replace(load_trade_score_risk_gate_report(config=_config()), safety={"live_trading_enabled": True}).validate()


def test_br06_can_emit_research_only_for_low_scoring_non_blocked_candidates() -> None:
    chain_report, contract_report, analyst_report = _reports()
    context = CandidateRiskContext(
        contract_id="NVDA-20271217-C-220",
        symbol="NVDA",
        proposed_position_pct=0.01,
        existing_symbol_exposure_pct=0.01,
        portfolio_drawdown_pct=0.01,
        candidate_drawdown_pct=0.01,
        days_to_next_catalyst=90,
    )

    report = build_trade_score_risk_gate_report(
        chain_report,
        contract_report,
        analyst_report,
        (context,),
        config=_config(min_monitor_score=92, min_human_review_score=95, min_paper_score=100),
    )
    payload = trade_score_risk_gate_payload(report)

    assert payload["decisions"][0]["hard_block_reasons"] == ()
    assert payload["decisions"][0]["label"] == RESEARCH_ONLY
