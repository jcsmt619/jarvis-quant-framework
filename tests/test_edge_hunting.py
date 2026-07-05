"""
tests/test_edge_hunting.py
==========================
Tests for the edge-hunting pipeline: config validation, gate evaluation,
and a synthetic end-to-end experiment run (no network, no real data).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from edge_hunting.config_loader import ExperimentConfig, ConfigError
from edge_hunting.gate import GateVerdict, evaluate as evaluate_gate
from edge_hunting.reporter import write_reports
from strategies.base import EdgeStrategy, Signal


# ---------------------------------------------------------------------------
# Config loader tests
# ---------------------------------------------------------------------------
def _valid_config() -> dict:
    return {
        "strategy_name": "test_strategy",
        "strategy_module": "strategies.hmm_adapter",
        "strategy_class": "HMMAllocationAdapter",
        "asset_class": "stocks_etfs",
        "symbols": ["SPY"],
        "timeframe": "1Day",
        "start_date": "2010-01-01",
        "end_date": "2025-12-31",
        "features_used": ["logret_1", "rsi_z_14"],
        "entry_rules": {"min_confidence": 0.55},
        "exit_rules": {"stop_type": "atr", "atr_multiplier": 2.0},
        "position_sizing": {"method": "allocation", "max_leverage": 1.0,
                            "initial_capital": 100000.0},
        "fees": {"commission_per_trade": 0.0, "slippage_bps": 5.0},
        "train_test_split": {"method": "walk_forward", "train_window": 252,
                             "test_window": 126, "step_size": 126, "fill_delay": 1},
        "walk_forward": {"n_candidates": [3, 4, 5], "n_init": 4, "random_state": 42},
        "benchmark": {"buy_hold": True, "sma200": True,
                      "random": {"enabled": True, "seeds": 50}},
        "robustness": {
            "cpcv": {"enabled": True, "n_groups": 6, "n_test_groups": 2, "embargo_pct": 0.01},
            "deflated_sharpe": {"enabled": True, "n_trials": 1},
            "stress_tests": {
                "crash_injection": {"enabled": True, "n_sims": 10, "n_gaps": 5},
                "gap_risk": {"enabled": True, "n_sims": 10, "n_gaps": 5},
                "regime_misclassification": {"enabled": True, "n_sims": 5},
            },
            "parameter_sensitivity": {"enabled": True, "perturbation_pct": 0.20,
                                      "params_to_perturb": ["min_confidence"]},
        },
        "validation_gate": {
            "min_oos_sharpe": 0.5, "min_dsr": 0.80, "max_max_drawdown": 0.25,
            "min_cpcv_pct_positive": 0.60, "must_beat_random": True,
            "must_beat_buy_hold": False,
        },
    }


def test_config_valid():
    """A valid config parses without error."""
    cfg = ExperimentConfig.from_dict(_valid_config())
    assert cfg.strategy_name == "test_strategy"
    assert cfg.asset_class == "stocks_etfs"
    assert cfg.symbols == ["SPY"]


def test_config_rejects_crypto():
    """Crypto symbols are rejected."""
    c = _valid_config()
    c["symbols"] = ["BTCUSD"]
    with pytest.raises(ConfigError, match="crypto/forex"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_wrong_asset_class():
    """Non-stocks_etfs asset classes are rejected."""
    c = _valid_config()
    c["asset_class"] = "crypto"
    with pytest.raises(ConfigError, match="stocks_etfs"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_missing_fields():
    """Missing required fields are rejected."""
    c = _valid_config()
    del c["strategy_name"]
    with pytest.raises(ConfigError, match="missing required"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_bad_dates():
    """start_date >= end_date is rejected."""
    c = _valid_config()
    c["start_date"] = "2025-01-01"
    c["end_date"] = "2020-01-01"
    with pytest.raises(ConfigError, match="before"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_bad_features():
    """Unknown features are rejected."""
    c = _valid_config()
    c["features_used"] = ["nonexistent_feature"]
    with pytest.raises(ConfigError, match="unknown features"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_zero_fill_delay():
    """fill_delay < 1 (same-bar execution) is rejected."""
    c = _valid_config()
    c["train_test_split"]["fill_delay"] = 0
    with pytest.raises(ConfigError, match="fill_delay"):
        ExperimentConfig.from_dict(c)


def test_config_rejects_negative_slippage():
    """Negative slippage is rejected."""
    c = _valid_config()
    c["fees"]["slippage_bps"] = -1.0
    with pytest.raises(ConfigError, match="slippage"):
        ExperimentConfig.from_dict(c)


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------
def test_gate_pass_all_clear():
    """A strategy that meets all hard gates passes."""
    metrics = {"sharpe": 1.2, "max_drawdown": 0.15, "profit_factor": 1.8,
               "win_rate": 0.55, "avg_holding_bars": 10}
    robustness = {"dsr": 0.92, "cpcv_pct_positive": 0.75, "crash_worst_dd": -0.20,
                  "param_sensitivity_stable": True, "cpcv_sharpe_std": 0.8,
                  "regime_misclass_contained": True}
    verdict = evaluate_gate(metrics, robustness, True, True, True, _valid_config()["validation_gate"])
    assert verdict.passed
    assert len(verdict.hard_failures) == 0


def test_gate_fail_low_sharpe():
    """H1: low Sharpe fails."""
    metrics = {"sharpe": 0.3, "max_drawdown": 0.10, "profit_factor": 1.5,
               "win_rate": 0.50, "avg_holding_bars": 5}
    robustness = {"dsr": 0.90, "cpcv_pct_positive": 0.70, "crash_worst_dd": -0.15,
                  "param_sensitivity_stable": True, "cpcv_sharpe_std": 0.5,
                  "regime_misclass_contained": True}
    verdict = evaluate_gate(metrics, robustness, True, True, True, _valid_config()["validation_gate"])
    assert not verdict.passed
    assert any("H1" in f for f in verdict.hard_failures)


def test_gate_fail_look_ahead():
    """H6: look-ahead failure is non-negotiable."""
    metrics = {"sharpe": 2.0, "max_drawdown": 0.05, "profit_factor": 3.0,
               "win_rate": 0.70, "avg_holding_bars": 20}
    robustness = {"dsr": 0.95, "cpcv_pct_positive": 0.90, "crash_worst_dd": -0.10,
                  "param_sensitivity_stable": True, "cpcv_sharpe_std": 0.3,
                  "regime_misclass_contained": True}
    verdict = evaluate_gate(metrics, robustness, False, True, True, _valid_config()["validation_gate"])
    assert not verdict.passed
    assert any("H6" in f for f in verdict.hard_failures)


def test_gate_fail_high_drawdown():
    """H2: max DD > 25% fails."""
    metrics = {"sharpe": 1.5, "max_drawdown": 0.35, "profit_factor": 2.0,
               "win_rate": 0.55, "avg_holding_bars": 8}
    robustness = {"dsr": 0.90, "cpcv_pct_positive": 0.70, "crash_worst_dd": -0.30,
                  "param_sensitivity_stable": True, "cpcv_sharpe_std": 0.6,
                  "regime_misclass_contained": True}
    verdict = evaluate_gate(metrics, robustness, True, True, True, _valid_config()["validation_gate"])
    assert not verdict.passed
    assert any("H2" in f for f in verdict.hard_failures)


def test_gate_soft_warnings_dont_block():
    """Soft gate warnings don't block a pass."""
    metrics = {"sharpe": 1.0, "max_drawdown": 0.15, "profit_factor": 1.1,
               "win_rate": 0.30, "avg_holding_bars": 1}
    robustness = {"dsr": 0.85, "cpcv_pct_positive": 0.65, "crash_worst_dd": -0.20,
                  "param_sensitivity_stable": True, "cpcv_sharpe_std": 1.8,
                  "regime_misclass_contained": False}
    verdict = evaluate_gate(metrics, robustness, True, True, False, _valid_config()["validation_gate"])
    assert verdict.passed
    assert len(verdict.soft_warnings) > 0


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------
def test_reporter_writes_all_files(tmp_path):
    """Reporter writes all required output files."""
    config = _valid_config()
    n = 100
    index = pd.date_range("2024-01-01", periods=n, freq="D")
    equity = np.linspace(100000, 110000, n)
    target = np.full(n, 0.6)
    close = np.linspace(100, 110, n)
    trades = [{"entry_idx": 0, "exit_idx": 50, "hold_bars": 50, "pnl": 1000.0,
               "return_pct": 0.01}]
    metrics = {"sharpe": 1.0, "max_drawdown": 0.05, "total_return": 0.10,
               "cagr": 0.10, "sortino": 1.2, "calmar": 2.0, "win_rate": 0.55,
               "profit_factor": 1.8, "total_trades": 1, "avg_holding_bars": 50,
               "underwater_bars": 5}
    benchmarks = {"buy_hold": {"total_return": 0.08, "sharpe": 0.7, "max_dd": 0.10}}
    robustness = {"dsr": 0.90, "cpcv_sharpes": [0.8, 1.2, 0.5], "cpcv_pct_positive": 1.0,
                  "cpcv_sharpe_std": 0.3, "crash_worst_dd": -0.15,
                  "stress_crash_worst_dd": -0.15, "param_sensitivity_stable": True,
                  "regime_misclass_contained": True}
    verdict = GateVerdict(verdict="PASS", hard_failures=[], soft_warnings=[])

    write_reports(
        out_dir=tmp_path, config=config, metrics=metrics, trades=trades,
        equity=equity, index=index, target=target, close=close,
        benchmarks=benchmarks, robustness=robustness,
        gate_verdict=verdict, look_ahead_passed=True,
    )

    # Check all required files exist
    required = ["metrics.json", "trades.csv", "equity_curve.csv", "drawdown.csv",
                "assumptions.md", "failure_reasons.md", "config_snapshot.yaml",
                "cpcv_sharpe_distribution.csv", "stress_test_summary.json"]
    for fname in required:
        assert (tmp_path / fname).exists(), f"Missing: {fname}"

    # Check metrics.json content
    with open(tmp_path / "metrics.json") as f:
        m = json.load(f)
    assert m["gate_verdict"] == "PASS"
    assert m["look_ahead_passed"] is True

    # Check failure_reasons.md content
    with open(tmp_path / "failure_reasons.md") as f:
        content = f.read()
    assert "PASS" in content


# ---------------------------------------------------------------------------
# Strategy interface test
# ---------------------------------------------------------------------------
def test_signal_dataclass():
    """Signal dataclass works correctly."""
    sig = Signal(target_exposure=0.8, stop_price=95.0, meta={"regime": "calm"})
    assert sig.target_exposure == 0.8
    assert sig.stop_price == 95.0
    assert sig.meta == {"regime": "calm"}


def test_edge_strategy_is_abstract():
    """EdgeStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        EdgeStrategy()