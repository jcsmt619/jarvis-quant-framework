from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.options_contract_scorer import (
    ContractScoringConfig,
    build_contract_scoring_report,
    contract_scoring_payload,
    load_contract_scoring_inputs,
    load_contract_scoring_report,
    render_markdown_contract_scoring,
    safety_manifest,
    write_contract_scoring_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _config(**overrides: object) -> ContractScoringConfig:
    values = {
        "target_delta_min": 0.35,
        "target_delta_max": 0.65,
        "acceptable_delta_min": 0.25,
        "acceptable_delta_max": 0.75,
        "ideal_theta_abs_max": 0.030,
        "acceptable_theta_abs_max": 0.060,
        "ideal_vega_min": 0.30,
        "acceptable_vega_min": 0.15,
        "ideal_iv_min": 0.20,
        "ideal_iv_max": 0.65,
        "acceptable_iv_min": 0.05,
        "acceptable_iv_max": 1.20,
        "ideal_spread_pct_max": 0.03,
        "acceptable_spread_pct_max": 0.08,
        "ideal_dte_min": 360,
        "ideal_dte_max": 760,
        "acceptable_dte_min": 180,
        "acceptable_dte_max": 900,
        "min_volume": 25,
        "min_open_interest": 250,
        "ideal_volume": 100,
        "ideal_open_interest": 1000,
        "ideal_strike_to_underlying_min": 0.85,
        "ideal_strike_to_underlying_max": 1.50,
        "acceptable_strike_to_underlying_min": 0.70,
        "acceptable_strike_to_underlying_max": 1.80,
        "min_component_score": 50,
        "min_total_score": 75,
    }
    values.update(overrides)
    return ContractScoringConfig(**values)


def test_br04_safety_manifest_is_disabled_research_and_paper_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-04"
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
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br04_loads_fixture_and_scores_contracts_deterministically() -> None:
    report = load_contract_scoring_report(config=_config())
    payload = contract_scoring_payload(report)

    assert payload["phase"] == "BR-04"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["metrics"] == {
        "contract_count": 6,
        "suitable_contract_count": 4,
        "blocked_contract_count": 2,
        "human_review_required_count": 6,
    }
    assert payload["suitable_contracts"][0]["contract_id"] == "NVDA-20271217-C-140"
    assert payload["suitable_contracts"][0]["total_score"] == 100
    assert payload["suitable_contracts"][0]["label"] == MONITOR_ONLY
    assert payload["suitable_contracts"][0]["human_review_required"] is True
    assert {item["name"] for item in payload["suitable_contracts"][0]["component_scores"]} == {
        "delta",
        "theta",
        "vega",
        "implied_volatility",
        "spread",
        "dte",
        "liquidity",
        "contract_suitability",
    }
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br04_component_scores_explain_acceptable_but_suitable_contracts() -> None:
    report = load_contract_scoring_report(config=_config())
    payload = contract_scoring_payload(report)
    decisions = {item["contract_id"]: item for item in payload["suitable_contracts"]}
    contract = decisions["NVDA-20271217-C-260"]
    components = {item["name"]: item for item in contract["component_scores"]}

    assert contract["total_score"] == 82
    assert contract["suitable"] is True
    assert contract["reasons"] == ()
    assert components["delta"]["score"] == 70
    assert components["delta"]["reason"] == "delta_inside_acceptable_band"
    assert components["vega"]["score"] == 70
    assert components["spread"]["score"] == 70
    assert components["liquidity"]["score"] == 70


def test_br04_blocks_contracts_with_missing_greeks_iv_short_dte_and_illiquidity() -> None:
    report = load_contract_scoring_report(config=_config())
    payload = contract_scoring_payload(report)
    blocked = {item["contract_id"]: item for item in payload["blocked_contracts"]}
    first = blocked["ABCD-20260821-C-45"]
    second = blocked["ABCD-20260821-C-55"]
    first_components = {item["name"]: item for item in first["component_scores"]}
    second_components = {item["name"]: item for item in second["component_scores"]}

    assert first["label"] == BLOCKED_BY_SAFETY_GATE
    assert set(first["reasons"]) >= {
        "vega_below_minimum",
        "implied_volatility_below_minimum",
        "spread_below_minimum",
        "dte_below_minimum",
        "liquidity_below_minimum",
        "total_score_below_minimum",
    }
    assert first_components["vega"]["reason"] == "missing_vega"
    assert first_components["implied_volatility"]["reason"] == "implied_volatility_outside_acceptable_band"
    assert second_components["delta"]["reason"] == "missing_delta"
    assert second_components["theta"]["reason"] == "missing_theta"
    assert second_components["implied_volatility"]["reason"] == "missing_implied_volatility"


def test_br04_config_changes_can_block_otherwise_suitable_contracts() -> None:
    report = load_contract_scoring_report(config=_config(min_total_score=95))
    payload = contract_scoring_payload(report)
    blocked = {item["contract_id"]: item for item in payload["blocked_contracts"]}

    assert "NVDA-20271217-C-220" in blocked
    assert blocked["NVDA-20271217-C-220"]["total_score"] == 92
    assert blocked["NVDA-20271217-C-220"]["reasons"] == ("total_score_below_minimum",)


def test_br04_payload_markdown_and_report_files_are_human_review_outputs() -> None:
    report = load_contract_scoring_report(config=_config())
    markdown = render_markdown_contract_scoring(report)

    assert "BR-04 Greeks IV Spread DTE Scoring" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Deterministic options scoring report only; no broker routing or order submission." in markdown
    assert "Report-level state remains blocked by safety gate." in markdown

    out_dir = Path(".codex_pytest_tmp/br04_options_contract_scoring_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_contract_scoring_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-04"
    assert "Component Scores" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br04_validation_rejects_invalid_config_labels_and_empty_input() -> None:
    with pytest.raises(ValueError, match="acceptable_delta_min cannot be above target_delta_min"):
        build_contract_scoring_report(load_contract_scoring_inputs(), config=_config(acceptable_delta_min=0.40))

    with pytest.raises(ValueError, match="requires at least one chain"):
        build_contract_scoring_report([], config=_config())

    chain = load_contract_scoring_inputs()[0]
    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(chain, underlying_symbol="nvda").validate()

    with pytest.raises(ValueError, match="safe research"):
        replace(chain.contracts[0], label="UNSAFE_LABEL").validate()

    with pytest.raises(ValueError, match="contract scoring report must remain blocked"):
        replace(load_contract_scoring_report(config=_config()), label=MONITOR_ONLY).validate()
