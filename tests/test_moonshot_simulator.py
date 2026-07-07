from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engines.moonshot.deterministic.simulator import (
    REQUIRED_LABELS,
    MoonshotScenario,
    MoonshotSimulatorConfig,
    build_report_payload,
    failure_mode_definitions,
    render_markdown_report,
    safety_manifest,
    simulate_moonshot_scenarios,
    write_research_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _clean_scenario(symbol: str = "MSFT") -> MoonshotScenario:
    return MoonshotScenario(
        symbol=symbol,
        thesis="Asymmetric LEAPS research setup with capped downside.",
        proposed_position_pct=0.02,
        upside_pct=1.50,
        downside_pct=0.35,
        probability_upside=0.35,
        dte=420,
        iv_rank=0.50,
        theta_decay_pct=0.10,
        option_chain_age_minutes=5,
        has_exit_plan=True,
    )


def test_13a_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13A"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13a_clean_scenario_is_included_with_expected_paper_accounting() -> None:
    scenario = _clean_scenario()
    result = simulate_moonshot_scenarios([scenario])
    item = result.scenario_results[0]

    expected_return = 0.35 * 1.50 - 0.65 * 0.35

    assert item.label == RESEARCH_ONLY
    assert item.included_in_research_simulation is True
    assert item.expected_return_pct == pytest.approx(expected_return)
    assert item.expected_account_return_pct == pytest.approx(0.02 * expected_return)
    assert item.best_case_account_return_pct == pytest.approx(0.02 * 1.50)
    assert item.stress_loss_account_pct == pytest.approx(0.02 * 0.35)
    assert item.failure_modes == ()
    assert result.metrics["included_count"] == 1
    assert result.metrics["blocked_count"] == 0


def test_13a_risk_caps_block_size_loss_and_portfolio_exposure() -> None:
    scenarios = [
        MoonshotScenario(
            symbol="RISKY",
            thesis="High-risk research scenario.",
            proposed_position_pct=0.04,
            upside_pct=2.0,
            downside_pct=0.50,
            probability_upside=0.30,
            dte=365,
            iv_rank=0.40,
            theta_decay_pct=0.10,
            option_chain_age_minutes=5,
        ),
        MoonshotScenario(
            symbol="OVER",
            thesis="Second high-risk scenario that breaches total exposure.",
            proposed_position_pct=0.03,
            upside_pct=1.0,
            downside_pct=0.20,
            probability_upside=0.50,
            dte=365,
            iv_rank=0.40,
            theta_decay_pct=0.10,
            option_chain_age_minutes=5,
        ),
    ]

    result = simulate_moonshot_scenarios(
        scenarios,
        MoonshotSimulatorConfig(max_total_exposure_pct=0.05),
    )

    assert result.scenario_results[0].label == BLOCKED_BY_SAFETY_GATE
    assert "position_size_breach" in result.scenario_results[0].failure_modes
    assert "position_loss_breach" in result.scenario_results[0].failure_modes
    assert result.scenario_results[1].label == BLOCKED_BY_SAFETY_GATE
    assert "portfolio_exposure_breach" in result.scenario_results[1].failure_modes
    assert result.metrics["blocked_count"] == 2
    assert result.metrics["blocked_stress_loss_account_pct"] > 0.0


def test_13a_failure_modes_cover_option_quality_decay_iv_dte_and_exit_plan() -> None:
    scenario = MoonshotScenario(
        symbol="FAIL",
        thesis="Failure-mode coverage scenario.",
        proposed_position_pct=0.01,
        upside_pct=1.0,
        downside_pct=0.20,
        probability_upside=0.50,
        dte=90,
        iv_rank=0.95,
        theta_decay_pct=0.40,
        option_chain_age_minutes=120,
        has_exit_plan=False,
    )

    item = simulate_moonshot_scenarios([scenario]).scenario_results[0]

    assert item.label == BLOCKED_BY_SAFETY_GATE
    assert set(item.failure_modes) >= {
        "missing_stop",
        "option_chain_stale",
        "theta_decay_breach",
        "iv_spike_review",
        "dte_below_minimum",
    }
    assert set(failure_mode_definitions()) >= set(item.failure_modes)


def test_13a_report_payload_and_markdown_are_research_outputs() -> None:
    result = simulate_moonshot_scenarios([_clean_scenario()])
    payload = build_report_payload(result)
    markdown = render_markdown_report(result)

    assert payload["phase"] == "13A"
    assert payload["safety"]["labels"] == REQUIRED_LABELS
    assert payload["risk_caps"]["max_position_pct"] == pytest.approx(0.03)
    assert payload["scenarios"][0]["safety"]["broker_order_submitted"] is False
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Risk Caps" in markdown
    assert "high-risk research scenarios" in markdown


def test_13a_write_research_report_outputs_json_and_markdown() -> None:
    result = simulate_moonshot_scenarios([_clean_scenario("META")])
    out_dir = Path("reports/moonshot_simulator_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_research_report(result, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["simulator"] == "Moonshot Simulator"
    assert "Scenario Results" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_13a_scenario_validation_rejects_invalid_probabilities() -> None:
    scenario = _clean_scenario()
    invalid = MoonshotScenario(
        symbol=scenario.symbol,
        thesis=scenario.thesis,
        proposed_position_pct=scenario.proposed_position_pct,
        upside_pct=scenario.upside_pct,
        downside_pct=scenario.downside_pct,
        probability_upside=1.2,
        dte=scenario.dte,
        iv_rank=scenario.iv_rank,
        theta_decay_pct=scenario.theta_decay_pct,
        option_chain_age_minutes=scenario.option_chain_age_minutes,
        has_exit_plan=scenario.has_exit_plan,
    )

    with pytest.raises(ValueError, match="probability_upside"):
        simulate_moonshot_scenarios([invalid])
