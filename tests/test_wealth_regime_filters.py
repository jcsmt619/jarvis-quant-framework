from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from engines.wealth.deterministic.wealth_regime_filters import (
    FILTER_NAME,
    REQUIRED_LABELS,
    WealthRegimeFilterConfig,
    build_report_payload,
    build_wealth_regime_filters,
    evaluate_wealth_regime_filters,
    regime_filter_definitions,
    render_markdown_report,
    safety_manifest,
    write_research_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _market_data() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "volume": [250_000] * 10,
        },
        index=idx,
        dtype=float,
    )


def _config() -> WealthRegimeFilterConfig:
    return WealthRegimeFilterConfig(
        volatility_window=3,
        max_annualized_volatility=0.50,
        trend_short_window=2,
        trend_long_window=4,
        liquidity_window=3,
        min_avg_dollar_volume=1_000_000.0,
        min_avg_volume=100_000.0,
        risk_off_drawdown=-0.08,
    )


def test_12d_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "12D"
    assert manifest["filter"] == FILTER_NAME
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_12d_builds_volatility_trend_liquidity_and_risk_off_filters() -> None:
    filters = build_wealth_regime_filters(_market_data(), _config())
    latest = filters.iloc[-1]
    definitions = regime_filter_definitions()

    assert {
        "volatility_filter_pass",
        "trend_filter_pass",
        "liquidity_filter_pass",
        "risk_off_filter_pass",
        "research_weight_multiplier",
        "filter_label",
    } <= set(definitions)
    assert bool(latest["volatility_filter_pass"]) is True
    assert bool(latest["trend_filter_pass"]) is True
    assert bool(latest["liquidity_filter_pass"]) is True
    assert bool(latest["risk_off_filter_pass"]) is True
    assert bool(latest["all_filters_pass"]) is True
    assert latest["research_weight_multiplier"] == pytest.approx(1.0)
    assert latest["filter_label"] == RESEARCH_ONLY


def test_12d_volatility_spike_blocks_research_multiplier() -> None:
    data = _market_data()
    data.loc[data.index[-1], "close"] = 150.0
    cfg = _config()
    filters = build_wealth_regime_filters(data, cfg)
    latest = filters.iloc[-1]

    assert latest["realized_annualized_volatility"] > cfg.max_annualized_volatility
    assert bool(latest["volatility_filter_pass"]) is False
    assert bool(latest["all_filters_pass"]) is False
    assert latest["research_weight_multiplier"] == pytest.approx(0.0)
    assert latest["filter_label"] == BLOCKED_BY_SAFETY_GATE


def test_12d_liquidity_and_external_risk_off_block_state() -> None:
    data = _market_data()
    data["volume"] = 10_000
    risk_off_signal = pd.Series(False, index=data.index)
    risk_off_signal.iloc[-1] = True

    filters = build_wealth_regime_filters(data, _config(), risk_off_signal=risk_off_signal)
    latest = filters.iloc[-1]

    assert bool(latest["liquidity_filter_pass"]) is False
    assert bool(latest["external_risk_off"]) is True
    assert bool(latest["risk_off_filter_pass"]) is False
    assert bool(latest["all_filters_pass"]) is False
    assert latest["filter_label"] == BLOCKED_BY_SAFETY_GATE


def test_12d_config_validation_rejects_unsafe_thresholds() -> None:
    with pytest.raises(ValueError, match="trend_short_window"):
        WealthRegimeFilterConfig(trend_short_window=5, trend_long_window=5).validate()
    with pytest.raises(ValueError, match="risk_off_drawdown"):
        WealthRegimeFilterConfig(risk_off_drawdown=0.01).validate()
    with pytest.raises(ValueError, match="liquidity thresholds"):
        WealthRegimeFilterConfig(min_avg_dollar_volume=-1.0).validate()


def test_12d_report_payload_and_markdown_are_research_outputs() -> None:
    result = evaluate_wealth_regime_filters(_market_data(), _config())
    payload = build_report_payload(result)
    markdown = render_markdown_report(result)

    assert payload["phase"] == "12D"
    assert payload["safety"]["labels"] == REQUIRED_LABELS
    assert payload["latest"]["filter_label"] == RESEARCH_ONLY
    assert payload["pass_count"] >= 1
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Filter Definitions" in markdown
    assert "human review" in markdown


def test_12d_write_research_report_outputs_json_and_markdown() -> None:
    result = evaluate_wealth_regime_filters(_market_data(), _config())
    out_dir = Path("reports/wealth_regime_filters_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_research_report(result, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["filter"] == "Wealth Regime Filters"
    assert "Latest State" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)
