from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from engines.wealth.deterministic.mean_reversion_lab import (
    REQUIRED_LABELS,
    MeanReversionConfig,
    build_mean_reversion_signals,
    build_report_payload,
    render_markdown_report,
    run_research_backtest,
    safety_manifest,
    signal_definitions,
    write_research_report,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


def _prices() -> pd.Series:
    return pd.Series(
        [100, 100, 100, 100, 100, 92, 94, 97, 100, 108, 105, 101],
        index=pd.date_range("2024-01-01", periods=12, freq="D"),
        name="close",
        dtype=float,
    )


def test_12a_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_12a_signal_definitions_and_mean_reversion_signals() -> None:
    cfg = MeanReversionConfig(lookback=5, entry_z=1.0, exit_z=0.2, cost_bps=0.0)
    signals = build_mean_reversion_signals(_prices(), cfg)
    definitions = signal_definitions()

    assert {"rolling_mean", "rolling_std", "zscore", "raw_signal", "target_weight"} <= set(definitions)
    assert signals.loc["2024-01-06", "target_weight"] == pytest.approx(1.0)
    assert signals.loc["2024-01-10", "target_weight"] == pytest.approx(-1.0)
    assert signals["target_weight"].abs().max() <= cfg.max_weight


def test_12a_research_backtest_uses_shifted_positions_and_reports_metrics() -> None:
    cfg = MeanReversionConfig(lookback=5, entry_z=1.0, exit_z=0.2, cost_bps=0.0)
    result = run_research_backtest(_prices(), cfg)

    close_returns = result.signals["close"].pct_change().fillna(0.0)
    shifted = result.signals["target_weight"].shift(1).fillna(0.0)
    expected_returns = shifted * close_returns

    pd.testing.assert_series_equal(result.strategy_returns, expected_returns, check_names=False)
    assert result.metrics["observations"] == len(_prices())
    assert result.metrics["signal_flips"] >= 2
    assert result.safety["broker_order_call_performed"] is False


def test_12a_report_payload_and_markdown_are_research_outputs() -> None:
    result = run_research_backtest(
        _prices(),
        MeanReversionConfig(lookback=5, entry_z=1.0, exit_z=0.2, cost_bps=0.0),
    )
    payload = build_report_payload(result)
    markdown = render_markdown_report(result)

    assert payload["phase"] == "12A"
    assert payload["safety"]["labels"] == REQUIRED_LABELS
    assert "LIVE TRADING: DISABLED" in markdown
    assert "research-only" in markdown


def test_12a_write_research_report_outputs_json_and_markdown() -> None:
    result = run_research_backtest(
        pd.DataFrame({"Close": _prices()}),
        MeanReversionConfig(lookback=5, entry_z=1.0, exit_z=0.2, cost_bps=1.0),
    )
    out_dir = Path("reports/wealth_mean_reversion_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_research_report(result, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["lab"] == "Wealth Mean Reversion Lab"
    assert "Signal Definitions" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)
