"""
tests/test_eem_expansion.py
=============================
Tests for edge_hunting/eem_expansion.py (implementation of
docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md). No network access -- uses
synthetic OHLCV fixtures throughout.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edge_hunting import eem_expansion as eemx
from edge_hunting.backtest_engine import compute_position, compute_returns
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward


def _synthetic_ohlcv(n=600, seed=0, start="2015-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0003, 0.01, n)
    close = 100 * np.cumprod(1 + ret)
    idx = pd.date_range(start, periods=n, freq="B")
    df = pd.DataFrame({
        "Open": close, "High": close * 1.001, "Low": close * 0.999,
        "Close": close, "Volume": rng.integers(1_000_000, 5_000_000, n),
    }, index=idx)
    return df


# ---------------------------------------------------------------------------
# 1. No look-ahead
# ---------------------------------------------------------------------------
def test_no_lookahead_for_all_new_configs():
    """Signal at time t must be unchanged if future rows are truncated."""
    df = _synthetic_ohlcv(n=300)
    configs = [("rsi_revert", p) for p in eemx.build_center_grid()[:5]]
    for family in eemx.OTHER_MEAN_REVERSION_FAMILIES:
        from edge_hunting.parameter_grid import FAMILY_GRIDS, _grid_combinations
        grid = FAMILY_GRIDS.get(family, {})
        combos = _grid_combinations(grid)
        if combos:
            configs.append((family, combos[0]))

    cutoff = 250
    for family, params in configs:
        fn, _, _ = STRATEGY_REGISTRY[family]
        full_signal = fn(df, params)
        truncated_signal = fn(df.iloc[:cutoff], params)
        pd.testing.assert_series_equal(
            full_signal.iloc[:cutoff].astype(float),
            truncated_signal.astype(float),
            check_names=False,
        )


# ---------------------------------------------------------------------------
# 2. Correct cost application
# ---------------------------------------------------------------------------
def test_slippage_cost_scales_with_bps():
    """Higher cost_bps must produce lower (or equal) OOS returns for any
    active (turnover > 0) strategy, via the unmodified compute_returns."""
    df = _synthetic_ohlcv(n=400)
    fn, _, _ = STRATEGY_REGISTRY["rsi_revert"]
    params = eemx.ORIGINAL_EEM_PARAMS
    signal = fn(df, params)
    position = compute_position(signal)

    low_cost = compute_returns(df["Close"], position, cost_bps=1.0)
    high_cost = compute_returns(df["Close"], position, cost_bps=50.0)

    turnover = position.diff().abs().fillna(position.abs())
    traded_days = turnover > 0
    if traded_days.any():
        assert (low_cost[traded_days] >= high_cost[traded_days]).all()


def test_slippage_classify_matches_expected_buckets():
    assert eemx._slippage_classify({1.0: -0.1}) == "DOES_NOT_WORK_EVEN_AT_1BP"
    assert eemx._slippage_classify({1.0: 1.0, 5.0: -0.1, 10.0: 0.5, 25.0: 0.5}) == "FRAGILE"
    assert eemx._slippage_classify({1.0: 1.0, 5.0: 0.5, 10.0: 0.5, 25.0: 0.5}) == "STRONGER"
    assert eemx._slippage_classify({1.0: 1.0, 5.0: 0.5, 10.0: 0.5, 25.0: -0.1}) == "MARGINAL_NO_PAPER_TEST"


# ---------------------------------------------------------------------------
# 3. Correct benchmark comparison
# ---------------------------------------------------------------------------
def test_benchmark_comparison_runs_and_returns_expected_keys():
    df = _synthetic_ohlcv(n=400, seed=1)
    fn, _, _ = STRATEGY_REGISTRY["rsi_revert"]
    wf = run_walk_forward(df, fn, eemx.ORIGINAL_EEM_PARAMS, cost_bps=1.0)
    em_universe = {"EEM": df}
    result = eemx.run_benchmark_comparison(
        wf.oos_returns, wf.oos_total_return, wf.oos_sharpe, wf.oos_max_drawdown,
        df["Close"], em_universe, em_universe,
    )
    expected_keys = {
        "asset_bh_sharpe", "asset_bh_total_return", "asset_bh_max_drawdown",
        "em_equal_weight_sharpe", "correlation_to_asset", "excess_return",
        "excess_sharpe", "beta_warning", "classification",
    }
    assert expected_keys.issubset(result.keys())
    assert result["classification"] in {
        "BETA_DISGUISED", "ROBUST_CANDIDATE", "DEFENSIVE_CANDIDATE", "REJECT",
    }


# ---------------------------------------------------------------------------
# 4. Correct bootstrap output
# ---------------------------------------------------------------------------
def test_bootstrap_output_is_deterministic_and_well_formed():
    df = _synthetic_ohlcv(n=400, seed=2)
    fn, _, _ = STRATEGY_REGISTRY["rsi_revert"]
    wf = run_walk_forward(df, fn, eemx.ORIGINAL_EEM_PARAMS, cost_bps=1.0)
    from edge_hunting.robustness import bootstrap_stress_test

    r1 = bootstrap_stress_test(wf.oos_returns, "rsi_revert", "EEM")
    r2 = bootstrap_stress_test(wf.oos_returns, "rsi_revert", "EEM")
    assert r1.p5_sharpe == r2.p5_sharpe
    assert r1.p50_sharpe == r2.p50_sharpe
    assert r1.p95_sharpe == r2.p95_sharpe
    assert r1.flag in {"SOLID", "FRAGILE"}


# ---------------------------------------------------------------------------
# 5. Correct duplicate-signal grouping
# ---------------------------------------------------------------------------
def test_duplicate_check_applied_pairwise_to_all_survivors():
    """Identical return/position series must classify as DUPLICATE_SIGNAL."""
    idx = pd.date_range("2020-01-01", periods=100, freq="B")
    rng = np.random.default_rng(3)
    returns = pd.Series(rng.normal(0, 0.01, 100), index=idx)
    position = pd.Series(rng.choice([-1, 0, 1], 100), index=idx)

    from edge_hunting.duplicate_signal_detection import _pair_classification

    ret_corr = float(np.corrcoef(returns, returns)[0, 1])
    pos_corr = float(np.corrcoef(position, position)[0, 1])
    assert eemx._pair_classification(ret_corr, pos_corr) == "DUPLICATE_SIGNAL"
    assert _pair_classification(ret_corr, pos_corr) == "DUPLICATE_SIGNAL"

    independent = pd.Series(rng.normal(0, 0.01, 100), index=idx)
    ret_corr_ind = float(np.corrcoef(returns, independent)[0, 1])
    # Not asserting a specific bucket for random independent series (may
    # vary by chance), just that the function runs and returns a valid label.
    assert eemx._pair_classification(ret_corr_ind, 0.0) in {
        "DUPLICATE_SIGNAL", "NEAR_DUPLICATE", "INDEPENDENT",
    }


# ---------------------------------------------------------------------------
# 6. EEM-outlier check
# ---------------------------------------------------------------------------
def test_eem_outlier_check_detects_outlier():
    per_asset = {"EEM": 3.0, "VWO": 0.1, "EWZ": 0.0, "FXI": -0.1, "EWT": 0.2}
    result = eemx.check_eem_outlier(per_asset)
    assert result["is_outlier"] is True
    assert result["flag"] == "POOLED_RESULT_DRIVEN_BY_EEM_OUTLIER"


def test_eem_outlier_check_no_outlier_when_consistent():
    per_asset = {"EEM": 0.5, "VWO": 0.45, "EWZ": 0.55, "FXI": 0.5, "EWT": 0.48}
    result = eemx.check_eem_outlier(per_asset)
    assert result["is_outlier"] is False
    assert result["flag"] == "NO_OUTLIER_DETECTED"


def test_eem_outlier_check_missing_eem():
    result = eemx.check_eem_outlier({"VWO": 0.1, "EWZ": 0.2})
    assert result["is_outlier"] is False
    assert result["reason"] == "EEM_NOT_IN_RESULTS"


# ---------------------------------------------------------------------------
# Center grid / spec-fidelity checks
# ---------------------------------------------------------------------------
def test_center_grid_matches_original_setting():
    grid = eemx.build_center_grid()
    assert len(grid) == 80
    assert eemx.ORIGINAL_EEM_PARAMS in grid


def test_center_grid_dimensions_match_spec():
    grid = eemx.build_center_grid()
    windows = {p["window"] for p in grid}
    oversolds = {p["oversold"] for p in grid}
    overboughts = {p["overbought"] for p in grid}
    assert windows == {7, 10, 14, 18, 21}
    assert oversolds == {20, 25, 30, 35}
    assert overboughts == {65, 70, 75, 80}


def test_build_configs_includes_all_seven_families():
    configs = eemx.build_configs()
    families = {f for f, _ in configs}
    assert families == {
        "rsi_revert", "percent_b_revert", "bollinger_revert",
        "keltner_revert", "zscore_revert", "cci_revert", "williams_r_revert",
    }


# ---------------------------------------------------------------------------
# Family generalization classification logic
# ---------------------------------------------------------------------------
def test_family_generalization_classification_thresholds():
    assert eemx.classify_family_generalization(4, "ROBUST") == "GENERALIZES"
    assert eemx.classify_family_generalization(2, "ROBUST") == "PARTIALLY_GENERALIZES"
    assert eemx.classify_family_generalization(0, "LIKELY_CURVE_FIT") == \
        "DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT"
    assert eemx.classify_family_generalization(1, "MIXED") == "PARTIALLY_GENERALIZES"


# ---------------------------------------------------------------------------
# RSX handling never silently included as continuously tradeable
# ---------------------------------------------------------------------------
def test_rsx_never_in_main_em_universe_list():
    assert eemx.RSX_TICKER not in eemx.EM_ASSET_UNIVERSE


def test_original_eem_setting_flagged_correctly():
    assert eemx.ORIGINAL_EEM_PARAMS == {"window": 14, "oversold": 30, "overbought": 70}
