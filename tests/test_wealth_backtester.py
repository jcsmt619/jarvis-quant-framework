from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from engines.wealth.deterministic.wealth_backtester import (
    BACKTESTER_NAME,
    REQUIRED_LABELS,
    CostBreakdown,
    WealthBacktestConfig,
    build_benchmark_returns,
    build_report_payload,
    default_linear_cost_hook,
    render_markdown_report,
    run_wealth_backtest,
    safety_manifest,
    write_research_report,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


def _prices() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    return pd.DataFrame(
        {
            "CORE": [100, 101, 102, 103, 104, 106, 105, 108],
            "SAT": [50, 49, 50, 52, 51, 53, 54, 55],
        },
        index=idx,
        dtype=float,
    )


def _weights() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    return pd.DataFrame(
        {
            "CORE": [99.0, 99.0, 99.0, 0.60, 0.60, 0.20, 0.20, 0.0],
            "SAT": [-99.0, -99.0, -99.0, 0.00, 0.20, 0.20, 0.00, 0.0],
        },
        index=idx,
        dtype=float,
    )


def test_12b_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "12B"
    assert manifest["backtester"] == BACKTESTER_NAME
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_12b_train_test_split_ignores_in_sample_weights_and_shifts_execution() -> None:
    cfg = WealthBacktestConfig(train_size=3, test_size=5, cost_bps=0.0)
    result = run_wealth_backtest(_prices(), _weights(), cfg)

    assert result.train_prices.index[0] == pd.Timestamp("2024-01-01")
    assert result.test_prices.index[0] == pd.Timestamp("2024-01-04")
    assert result.metrics["train_observations"] == 3
    assert result.metrics["test_observations"] == 5
    assert result.execution_weights.iloc[0].sum() == pytest.approx(0.0)

    expected = (result.target_weights.shift(1).fillna(0.0) * result.asset_returns).sum(axis=1)
    pd.testing.assert_series_equal(result.gross_returns, expected.rename("gross_return"))
    pd.testing.assert_series_equal(result.strategy_returns, expected.rename("strategy_return"))


def test_12b_linear_cost_hook_is_deterministic_and_auditable() -> None:
    cfg = WealthBacktestConfig(train_size=3, cost_bps=10.0)
    result_a = run_wealth_backtest(_prices(), _weights(), cfg)
    result_b = run_wealth_backtest(_prices(), _weights(), cfg)

    expected_costs = default_linear_cost_hook(result_a.execution_weights, result_a.target_weights, cfg)
    pd.testing.assert_series_equal(result_a.cost_returns, expected_costs.total_cost.rename("cost_return"))
    pd.testing.assert_frame_equal(result_a.cost_components, expected_costs.components)
    pd.testing.assert_series_equal(result_a.strategy_returns, result_b.strategy_returns)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    assert result_a.metrics["total_cost"] > 0.0


def test_12b_custom_cost_hook_can_add_components() -> None:
    def fixed_fee_hook(
        execution_weights: pd.DataFrame,
        target_weights: pd.DataFrame,
        config: WealthBacktestConfig,
    ) -> CostBreakdown:
        fixed = pd.Series(0.001, index=execution_weights.index, name="total_cost")
        return CostBreakdown(
            total_cost=fixed,
            components=pd.DataFrame({"fixed_fee": fixed}, index=execution_weights.index),
        )

    result = run_wealth_backtest(
        _prices(),
        _weights(),
        WealthBacktestConfig(train_size=3, cost_bps=0.0),
        cost_hook=fixed_fee_hook,
    )

    assert result.cost_returns.iloc[0] == pytest.approx(0.001)
    assert result.cost_components["fixed_fee"].sum() == pytest.approx(0.005)
    pd.testing.assert_series_equal(
        result.strategy_returns,
        (result.gross_returns - result.cost_returns).rename("strategy_return"),
    )


def test_12b_benchmark_comparison_uses_same_test_period() -> None:
    cfg = WealthBacktestConfig(train_size=3, test_size=5, cost_bps=0.0)
    result = run_wealth_backtest(_prices(), _weights(), cfg)
    benchmarks = build_benchmark_returns(result.test_prices)

    assert set(result.benchmark_returns) == {"equal_weight_buy_hold", "CORE_buy_hold", "SAT_buy_hold"}
    pd.testing.assert_series_equal(result.benchmark_returns["CORE_buy_hold"], benchmarks["CORE_buy_hold"])
    assert result.benchmark_metrics["equal_weight_buy_hold"]["observations"] == 5
    assert result.metrics["benchmark_count"] == 3


def test_12b_report_payload_and_markdown_are_research_outputs() -> None:
    result = run_wealth_backtest(
        _prices(),
        _weights(),
        WealthBacktestConfig(train_size=3, test_size=5, cost_bps=1.0),
    )
    payload = build_report_payload(result)
    markdown = render_markdown_report(result)

    assert payload["phase"] == "12B"
    assert payload["safety"]["labels"] == REQUIRED_LABELS
    assert payload["train_period"]["observations"] == 3
    assert payload["test_period"]["observations"] == 5
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Benchmarks" in markdown
    assert "research" in markdown


def test_12b_write_research_report_outputs_json_and_markdown() -> None:
    result = run_wealth_backtest(
        _prices()["CORE"],
        _weights()["CORE"],
        WealthBacktestConfig(train_size=3, cost_bps=1.0),
    )
    out_dir = Path("reports/wealth_backtester_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_research_report(result, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["backtester"] == "Wealth Backtester"
    assert "Train/Test Separation" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)
