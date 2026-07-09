from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.options_chain_quality_scanner import (
    OptionsChainQualityConfig,
    build_options_chain_quality_report,
    load_options_chain_quality_inputs,
    load_options_chain_quality_report,
    options_chain_quality_payload,
    render_markdown_options_chain_quality,
    safety_manifest,
    write_options_chain_quality_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _config(**overrides: object) -> OptionsChainQualityConfig:
    values = {
        "max_spread_pct": 0.08,
        "min_volume": 25,
        "min_open_interest": 250,
        "min_dte": 180,
        "max_dte": 900,
        "min_strike_count": 4,
        "max_quote_age_minutes": 30,
        "min_implied_volatility": 0.05,
        "max_implied_volatility": 1.50,
        "min_quality_score": 75,
    }
    values.update(overrides)
    return OptionsChainQualityConfig(**values)


def test_br03_safety_manifest_is_disabled_and_research_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-03"
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


def test_br03_loads_fixture_and_scores_chain_quality_deterministically() -> None:
    report = load_options_chain_quality_report(config=_config())
    payload = options_chain_quality_payload(report)

    assert payload["phase"] == "BR-03"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["metrics"] == {
        "chain_count": 2,
        "passed_chain_count": 1,
        "blocked_chain_count": 1,
        "contract_count": 6,
        "passed_contract_count": 4,
        "blocked_contract_count": 2,
        "human_review_required_count": 8,
    }
    assert payload["passed_chains"][0]["underlying_symbol"] == "NVDA"
    assert payload["passed_chains"][0]["score"] == 100
    assert payload["passed_chains"][0]["strike_count"] == 4
    assert payload["passed_chains"][0]["label"] == MONITOR_ONLY
    assert payload["passed_chains"][0]["human_review_required"] is True
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br03_blocks_low_quality_contracts_for_required_reasons() -> None:
    report = load_options_chain_quality_report(config=_config())
    payload = options_chain_quality_payload(report)
    blocked_chain = payload["blocked_chains"][0]
    contracts = {item["contract_id"]: item for item in blocked_chain["contracts"]}

    assert blocked_chain["underlying_symbol"] == "ABCD"
    assert blocked_chain["label"] == BLOCKED_BY_SAFETY_GATE
    assert blocked_chain["reasons"] == (
        "strike_availability_below_minimum",
        "one_or_more_contracts_failed_quality_gate",
        "chain_score_below_minimum",
    )
    assert set(contracts["ABCD-20260821-C-45"]["reasons"]) >= {
        "spread_pct_above_maximum",
        "volume_below_minimum",
        "open_interest_below_minimum",
        "dte_below_minimum",
        "stale_quote_data",
        "missing_greeks",
        "implied_volatility_out_of_range",
        "contract_score_below_minimum",
    }
    assert contracts["ABCD-20260821-C-55"]["greeks_missing_fields"] == (
        "delta",
        "gamma",
        "theta",
        "vega",
    )
    assert "missing_implied_volatility" in contracts["ABCD-20260821-C-55"]["reasons"]


def test_br03_config_changes_can_make_strike_availability_pass_deterministically() -> None:
    report = load_options_chain_quality_report(config=_config(min_strike_count=2, min_quality_score=0))
    payload = options_chain_quality_payload(report)
    blocked_chain = payload["blocked_chains"][0]

    assert blocked_chain["underlying_symbol"] == "ABCD"
    assert "strike_availability_below_minimum" not in blocked_chain["reasons"]
    assert blocked_chain["reasons"] == ("one_or_more_contracts_failed_quality_gate",)


def test_br03_payload_markdown_and_report_files_are_human_review_outputs() -> None:
    report = load_options_chain_quality_report(config=_config())
    markdown = render_markdown_options_chain_quality(report)

    assert "BR-03 Options Chain Quality Scanner" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Deterministic option-chain quality report only; no broker routing or order submission." in markdown
    assert "Report-level state remains blocked by safety gate." in markdown

    out_dir = Path(".codex_pytest_tmp/br03_options_chain_quality_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_options_chain_quality_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-03"
    assert "Contract Quality Flags" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br03_validation_rejects_invalid_config_labels_and_empty_input() -> None:
    with pytest.raises(ValueError, match="max_dte cannot be below min_dte"):
        build_options_chain_quality_report(
            load_options_chain_quality_inputs(),
            config=_config(min_dte=500, max_dte=400),
        )

    with pytest.raises(ValueError, match="requires at least one chain"):
        build_options_chain_quality_report([], config=_config())

    chain = load_options_chain_quality_inputs()[0]
    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(chain, underlying_symbol="nvda").validate()

    with pytest.raises(ValueError, match="safe research"):
        replace(chain.contracts[0], label="UNSAFE_LABEL").validate()

    with pytest.raises(ValueError, match="ask cannot be below bid"):
        replace(chain.contracts[0], bid=10.0, ask=9.0).validate()
