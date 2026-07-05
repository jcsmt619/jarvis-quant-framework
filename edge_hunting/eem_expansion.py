"""
edge_hunting/eem_expansion.py
================================
Implementation of docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md (approved).

Tests whether the EEM rsi_revert(14,30/70) mean-reversion signal
generalizes across related emerging-market ETFs, nearby RSI thresholds,
and other mean-reversion families, or is likely a one-asset artifact.

Rules followed (per task instructions)
---------------------------------------
- No paper trading, no live trading -- this module only produces research
  report files under reports/eem_expansion/.
- No parameter tuning after seeing results: the RSI center grid (Section
  3.1 of the spec) and the standard grids for the other six families
  (Section 3.2) are fixed BEFORE this script runs and are reused verbatim
  from edge_hunting/parameter_grid.py where applicable.
- Does not change the original EEM rsi_revert(14,30/70) primary candidate
  or its classification anywhere.
- Does not change any strategy_library.py logic.
- Reuses existing edge_hunting infrastructure (data_loader, walk_forward,
  funnel, robustness, strategy_library) wherever possible; only the
  minimum new glue code needed to run the expansion and reuse the
  benchmark/regime/duplicate methodology already implemented elsewhere in
  edge_hunting/ is added here.
- Does not touch broker/, execution/, or any live-trading code.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from edge_hunting import data_loader
from edge_hunting.backtest_engine import TRADING_DAYS, _max_drawdown, _sharpe
from edge_hunting.benchmark_comparison import (
    _beta_warning,
    _buy_hold_metrics,
    _equal_weight_universe_returns,
)
from edge_hunting.benchmark_comparison import _classify as _benchmark_classify
from edge_hunting.duplicate_signal_detection import _pair_classification, _trade_days
from edge_hunting.funnel import evaluate_funnel
from edge_hunting.parameter_grid import FAMILY_GRIDS, _grid_combinations
from edge_hunting.regime_decomposition import REGIMES, label_regimes
from edge_hunting.regime_decomposition import _classify as _regime_classify
from edge_hunting.regime_decomposition import _regime_metrics
from edge_hunting.robustness import bootstrap_stress_test, parameter_sensitivity
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/eem_expansion")

# ---------------------------------------------------------------------------
# Section 1: exact asset universe (spec Section 1)
# ---------------------------------------------------------------------------
EM_ASSET_UNIVERSE = [
    "EEM", "VWO", "IEMG", "EWZ", "FXI", "INDA", "EWT", "EWY", "EWW",
    "EZA", "EIDO", "TUR", "ILF",
]
RSX_TICKER = "RSX"
RSX_HALT_CUTOFF = pd.Timestamp("2022-03-31")

# ---------------------------------------------------------------------------
# Section 2/3: exact strategy families + parameter grids (spec Sections 2-3)
# ---------------------------------------------------------------------------
RSI_CENTER_GRID_SPEC = {
    "window": [7, 10, 14, 18, 21],
    "oversold": [20, 25, 30, 35],
    "overbought": [65, 70, 75, 80],
}

OTHER_MEAN_REVERSION_FAMILIES = [
    "percent_b_revert", "bollinger_revert", "keltner_revert",
    "zscore_revert", "cci_revert", "williams_r_revert",
]

ORIGINAL_EEM_PARAMS = {"window": 14, "oversold": 30, "overbought": 70}


def build_center_grid() -> list[dict]:
    """The 80-config RSI parameter-neighborhood grid (spec Section 3.1)."""
    return _grid_combinations(RSI_CENTER_GRID_SPEC)


def build_configs() -> list[tuple[str, dict]]:
    """All (family, params) tuples tested in this expansion (spec Section 2-3)."""
    configs: list[tuple[str, dict]] = [("rsi_revert", p) for p in build_center_grid()]
    for family in OTHER_MEAN_REVERSION_FAMILIES:
        grid = FAMILY_GRIDS.get(family, {})
        for params in _grid_combinations(grid):
            configs.append((family, params))
    return configs


# ---------------------------------------------------------------------------
# Section 1.1 / 1.2: data audit (RSX handling + MIN_VALID_BARS enforcement)
# ---------------------------------------------------------------------------
def load_em_universe_with_status(
    assets: list[str] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Fetch every asset independently; report per-asset inclusion status
    rather than silently dropping any asset (spec Sections 1.2, 4.3)."""
    assets = assets or EM_ASSET_UNIVERSE
    universe: dict[str, pd.DataFrame] = {}
    status: dict[str, str] = {}
    cache_dir = Path("data/raw/edge_hunting_cache")
    for sym in assets:
        try:
            df = data_loader.fetch_symbol(sym, cache_dir=cache_dir)
        except Exception:
            df = None
        if df is None:
            status[sym] = "EXCLUDED_NO_DATA_OR_SHORT_HISTORY"
        else:
            universe[sym] = df
            status[sym] = "INCLUDED"
    return universe, status


def handle_rsx() -> tuple[pd.DataFrame | None, str]:
    """RSX delisting-safe handling per spec Section 1.1. Returns
    (dataframe_or_None, status_string). The returned dataframe (if any) is
    pre-halt-only and must never be used in the main aggregate scoring."""
    try:
        df = data_loader.fetch_symbol(RSX_TICKER)
    except Exception:
        df = None
    if df is None:
        return None, "EXCLUDED_DELISTED_INSUFFICIENT_DATA"

    pre_halt = df[df.index <= RSX_HALT_CUTOFF]
    if len(pre_halt) >= data_loader.MIN_VALID_BARS:
        return pre_halt, "INCLUDED_PREHALT_ONLY_EXCLUDED_FROM_AGGREGATE"
    return None, "EXCLUDED_DELISTED_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Section 5: validation gates (all reuse existing, unmodified functions)
# ---------------------------------------------------------------------------
SLIPPAGE_COST_LEVELS_BPS = [1.0, 5.0, 10.0, 25.0, 50.0]


def _slippage_classify(sharpes: dict[float, float]) -> str:
    """Same classification rule as edge_hunting/slippage_stress.py::_classify,
    reimplemented against a {cost_bps: sharpe} mapping to avoid importing a
    module-level global list keyed by position."""
    s1 = sharpes.get(1.0, 0.0)
    s5 = sharpes.get(5.0)
    s10 = sharpes.get(10.0)
    s25 = sharpes.get(25.0)
    if s1 <= 0:
        return "DOES_NOT_WORK_EVEN_AT_1BP"
    if (s5 is not None and s5 <= 0) or (s10 is not None and s10 <= 0):
        return "FRAGILE"
    if s25 is not None and s25 > 0:
        return "STRONGER"
    return "MARGINAL_NO_PAPER_TEST"


def run_slippage_stress(df: pd.DataFrame, fn, params: dict) -> dict:
    sharpes = {}
    for cost_bps in SLIPPAGE_COST_LEVELS_BPS:
        wf = run_walk_forward(df, fn, params, cost_bps=cost_bps)
        sharpes[cost_bps] = wf.oos_sharpe
    return {
        "sharpes_by_cost": sharpes,
        "classification": _slippage_classify(sharpes),
    }


def run_benchmark_comparison(
    wf_returns: pd.Series, wf_total_return: float, wf_sharpe: float,
    wf_max_drawdown: float, asset_close: pd.Series, em_universe: dict,
    full_universe: dict,
) -> dict:
    oos_idx = wf_returns.index
    asset_bh = _buy_hold_metrics(asset_close, oos_idx)

    em_ret = _equal_weight_universe_returns(em_universe, oos_idx)
    em_equity = (1.0 + em_ret).cumprod()
    em_sharpe = _sharpe(em_ret.to_numpy())

    common = wf_returns.index.intersection(asset_bh["returns"].index)
    if len(common) >= 10 and wf_returns.reindex(common).std() > 0 and asset_bh["returns"].reindex(common).std() > 0:
        corr = float(np.corrcoef(wf_returns.reindex(common), asset_bh["returns"].reindex(common))[0, 1])
    else:
        corr = 0.0

    excess_return = wf_total_return - asset_bh["total_return"]
    excess_sharpe = wf_sharpe - asset_bh["sharpe"]
    beta_warn = _beta_warning(wf_returns, asset_bh["returns"], corr, excess_sharpe)
    classification = _benchmark_classify(
        wf_sharpe, asset_bh["sharpe"], wf_max_drawdown, asset_bh["max_drawdown"],
        wf_total_return, asset_bh["total_return"], excess_sharpe, excess_return, corr,
    )
    return {
        "asset_bh_sharpe": asset_bh["sharpe"],
        "asset_bh_total_return": asset_bh["total_return"],
        "asset_bh_max_drawdown": asset_bh["max_drawdown"],
        "em_equal_weight_sharpe": em_sharpe,
        "correlation_to_asset": corr,
        "excess_return": excess_return,
        "excess_sharpe": excess_sharpe,
        "beta_warning": beta_warn,
        "classification": classification,
    }


def run_regime_decomposition(df: pd.DataFrame, wf) -> dict:
    regime_labels = label_regimes(df).reindex(wf.oos_returns.index)
    regime_rows = []
    for regime in REGIMES:
        mask = regime_labels == regime
        m = _regime_metrics(wf.oos_returns[mask], wf.oos_position[mask])
        m["regime"] = regime
        regime_rows.append(m)
    classification, best_regime, worst_regime, concentrated = _regime_classify(regime_rows)
    return {
        "classification": classification,
        "best_regime": best_regime,
        "worst_regime": worst_regime,
        "concentrated_in_one_regime": concentrated,
    }


# ---------------------------------------------------------------------------
# Section 6.3: EEM-outlier check
# ---------------------------------------------------------------------------
def check_eem_outlier(per_asset_mean_sharpe: dict[str, float], eem_key: str = "EEM") -> dict:
    """Flags POOLED_RESULT_DRIVEN_BY_EEM_OUTLIER if EEM's own mean OOS Sharpe
    (across the rsi_revert center grid) is more than 1 std above the mean of
    the OTHER assets' per-asset means (spec Section 6.3)."""
    if eem_key not in per_asset_mean_sharpe:
        return {"is_outlier": False, "reason": "EEM_NOT_IN_RESULTS"}
    others = [v for k, v in per_asset_mean_sharpe.items() if k != eem_key]
    if len(others) < 2:
        return {"is_outlier": False, "reason": "INSUFFICIENT_OTHER_ASSETS"}
    eem_mean = per_asset_mean_sharpe[eem_key]
    other_mean = float(np.mean(others))
    other_std = float(np.std(others, ddof=1))
    threshold = other_mean + other_std
    is_outlier = eem_mean > threshold
    return {
        "is_outlier": is_outlier,
        "eem_mean_sharpe": eem_mean,
        "other_assets_mean_sharpe": other_mean,
        "other_assets_std_sharpe": other_std,
        "threshold": threshold,
        "flag": "POOLED_RESULT_DRIVEN_BY_EEM_OUTLIER" if is_outlier else "NO_OUTLIER_DETECTED",
    }


# ---------------------------------------------------------------------------
# Section 6.2: family-level generalization classification
# ---------------------------------------------------------------------------
def classify_family_generalization(
    n_independent_survivor_assets: int, sensitivity_flag: str,
) -> str:
    if n_independent_survivor_assets >= 4 and sensitivity_flag == "ROBUST":
        return "GENERALIZES"
    if n_independent_survivor_assets >= 2 or sensitivity_flag == "MIXED":
        return "PARTIALLY_GENERALIZES"
    return "DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT"


# ---------------------------------------------------------------------------
# Main pipeline (Phases 0-5 of the spec)
# ---------------------------------------------------------------------------
def main() -> tuple[pd.DataFrame, dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 0: data audit
    universe, status = load_em_universe_with_status()
    rsx_df, rsx_status = handle_rsx()
    status[RSX_TICKER] = rsx_status
    print("Data audit:")
    for sym, st in status.items():
        n = len(universe[sym]) if sym in universe else (len(rsx_df) if sym == RSX_TICKER and rsx_df is not None else 0)
        print(f"  {sym:6s} {st:45s} bars={n}")

    if not universe:
        print("WARNING: no EM assets available (no network/cache). Writing empty-result report.")

    try:
        full_universe = data_loader.load_universe()
    except Exception:
        full_universe = universe

    configs = build_configs()
    print(f"\nRunning {len(configs)} configs x {len(universe)} assets = {len(configs) * len(universe)} backtests")

    all_rows = []
    survivors: dict[str, dict] = {}  # candidate_id -> {returns, position, meta}

    for asset, df in universe.items():
        for family, params in configs:
            fn, category, _ = STRATEGY_REGISTRY[family]
            wf = run_walk_forward(df, fn, params, cost_bps=1.0)
            verdict = evaluate_funnel(wf.in_sample_sharpe, wf.oos_sharpe, wf.oos_max_drawdown, wf.oos_trade_count)

            row = {
                "asset": asset,
                "family": family,
                "params": json.dumps(params, sort_keys=True),
                "in_sample_sharpe": wf.in_sample_sharpe,
                "oos_sharpe": wf.oos_sharpe,
                "oos_max_drawdown": wf.oos_max_drawdown,
                "oos_total_return": wf.oos_total_return,
                "trade_count": wf.oos_trade_count,
                "funnel_survived": verdict.survived,
                "funnel_failure_reason": verdict.failure_reason,
                "bootstrap_flag": "",
                "bootstrap_worst_dd": np.nan,
                "slippage_classification": "",
                "benchmark_classification": "",
                "correlation_to_asset": np.nan,
                "excess_sharpe_over_asset_bh": np.nan,
                "regime_classification": "",
                "is_original_eem_setting": (asset == "EEM" and family == "rsi_revert" and params == ORIGINAL_EEM_PARAMS),
            }

            if verdict.survived:
                stress = bootstrap_stress_test(wf.oos_returns, strategy_name=f"{family}", asset=asset)
                row["bootstrap_flag"] = stress.flag
                row["bootstrap_worst_dd"] = stress.worst_case_drawdown

                if stress.flag == "SOLID":
                    slip = run_slippage_stress(df, fn, params)
                    row["slippage_classification"] = slip["classification"]

                    if slip["classification"] == "STRONGER":
                        bench = run_benchmark_comparison(
                            wf.oos_returns, wf.oos_total_return, wf.oos_sharpe,
                            wf.oos_max_drawdown, df["Close"], universe, full_universe,
                        )
                        row["benchmark_classification"] = bench["classification"]
                        row["correlation_to_asset"] = bench["correlation_to_asset"]
                        row["excess_sharpe_over_asset_bh"] = bench["excess_sharpe"]

                        regime = run_regime_decomposition(df, wf)
                        row["regime_classification"] = regime["classification"]

                        cid = f"{asset}__{family}__{row['params']}"
                        survivors[cid] = {
                            "asset": asset, "family": family, "params": params,
                            "returns": wf.oos_returns, "position": wf.oos_position,
                        }

            all_rows.append(row)

    results_df = pd.DataFrame(all_rows)

    # Duplicate-signal check across all final survivors (spec Section 5.7)
    dup_rollup: dict[str, str] = {}
    dup_pairs = []
    ids = list(survivors.keys())
    for id_a, id_b in itertools.combinations(ids, 2):
        a, b = survivors[id_a], survivors[id_b]
        common_idx = a["returns"].index.intersection(b["returns"].index)
        if len(common_idx) >= 10:
            ra, rb = a["returns"].reindex(common_idx), b["returns"].reindex(common_idx)
            pa, pb = a["position"].reindex(common_idx), b["position"].reindex(common_idx)
            ret_corr = float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else 0.0
            pos_corr = float(np.corrcoef(pa, pb)[0, 1]) if pa.std() > 0 and pb.std() > 0 else 0.0
            pair_class = _pair_classification(ret_corr, pos_corr)
        else:
            ret_corr, pos_corr, pair_class = 0.0, 0.0, "INSUFFICIENT_OVERLAP"
        dup_pairs.append({"a": id_a, "b": id_b, "ret_corr": ret_corr, "pos_corr": pos_corr, "classification": pair_class})

    for cid in ids:
        involved = [p for p in dup_pairs if p["a"] == cid or p["b"] == cid]
        if any(p["classification"] == "DUPLICATE_SIGNAL" for p in involved):
            dup_rollup[cid] = "DUPLICATE_SIGNAL"
        elif any(p["classification"] == "NEAR_DUPLICATE" for p in involved):
            dup_rollup[cid] = "NEAR_DUPLICATE"
        else:
            dup_rollup[cid] = "UNIQUE_SIGNAL"

    if not results_df.empty:
        results_df["duplicate_rollup"] = results_df.apply(
            lambda r: dup_rollup.get(f"{r['asset']}__{r['family']}__{r['params']}", ""), axis=1,
        )
    else:
        results_df["duplicate_rollup"] = pd.Series(dtype=str)

    # Parameter-neighborhood / sensitivity analysis (Section 5.8)
    sensitivity_by_family = {}
    per_asset_rsi_mean: dict[str, float] = {}
    if not results_df.empty:
        sens_input = results_df[["family", "oos_sharpe"]].dropna()
        if not sens_input.empty:
            sens_df = parameter_sensitivity(sens_input)
            sensitivity_by_family = {
                row["family"]: row["flag"] for _, row in sens_df.iterrows()
            }
        rsi_rows = results_df[results_df["family"] == "rsi_revert"]
        for asset, grp in rsi_rows.groupby("asset"):
            per_asset_rsi_mean[asset] = float(grp["oos_sharpe"].mean())

    outlier_check = check_eem_outlier(per_asset_rsi_mean)

    # Family-level generalization (Section 6.2) -- independent survivor
    # count = distinct assets with >=1 UNIQUE_SIGNAL or NEAR_DUPLICATE (but
    # not DUPLICATE_SIGNAL) survivor in that family.
    family_generalization = {}
    if not results_df.empty:
        for family in results_df["family"].unique():
            fam_survivors = results_df[
                (results_df["family"] == family)
                & (results_df["duplicate_rollup"].isin(["UNIQUE_SIGNAL", "NEAR_DUPLICATE"]))
            ]
            n_assets = fam_survivors["asset"].nunique()
            flag = sensitivity_by_family.get(family, "INSUFFICIENT_CONFIGS")
            classification = classify_family_generalization(n_assets, flag)
            if family == "rsi_revert" and outlier_check.get("is_outlier"):
                if classification == "GENERALIZES":
                    classification = "PARTIALLY_GENERALIZES"
            family_generalization[family] = {
                "n_independent_survivor_assets": int(n_assets),
                "sensitivity_flag": flag,
                "classification": classification,
            }

    rsi_gen = family_generalization.get("rsi_revert", {}).get("classification", "DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT")
    if rsi_gen == "GENERALIZES":
        headline_verdict = "EDGE_LIKELY_REAL_AND_EM_STRUCTURAL"
    elif rsi_gen == "PARTIALLY_GENERALIZES":
        headline_verdict = "EDGE_PARTIALLY_GENERALIZES_EM_SUBSET_SPECIFIC"
    else:
        headline_verdict = "EDGE_LIKELY_A_ONE_ASSET_EEM_ARTIFACT"

    # Paper-test recommendation: only candidates that (a) are the original
    # EEM setting, or (b) survived every gate AND are UNIQUE_SIGNAL/NEAR_
    # DUPLICATE (not DUPLICATE_SIGNAL) are even discussed here. This module
    # does not enable paper trading -- it only records a recommendation.
    paper_test_candidates = []
    reject_candidates = []
    if not results_df.empty:
        full_survivors = results_df[
            (results_df["benchmark_classification"].isin(["ROBUST_CANDIDATE", "DEFENSIVE_CANDIDATE"]))
            & (results_df["duplicate_rollup"] != "DUPLICATE_SIGNAL")
        ]
        for _, r in full_survivors.iterrows():
            paper_test_candidates.append({
                "asset": r["asset"], "family": r["family"], "params": r["params"],
                "benchmark_classification": r["benchmark_classification"],
                "duplicate_rollup": r["duplicate_rollup"],
                "is_original_eem_setting": bool(r["is_original_eem_setting"]),
            })
        reject_mask = (
            (results_df["funnel_survived"] == False)
            | (results_df["bootstrap_flag"] == "FRAGILE")
            | (results_df["benchmark_classification"] == "BETA_DISGUISED")
            | (results_df["benchmark_classification"] == "REJECT")
            | (results_df["duplicate_rollup"] == "DUPLICATE_SIGNAL")
        )
        reject_candidates = results_df[reject_mask][["asset", "family", "params"]].to_dict("records")

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_audit": status,
        "n_configs_tested": len(configs),
        "n_assets_tested": len(universe),
        "n_total_backtests": len(results_df),
        "family_generalization": family_generalization,
        "eem_outlier_check": outlier_check,
        "headline_verdict": headline_verdict,
        "n_paper_test_candidates": len(paper_test_candidates),
        "paper_test_candidates": paper_test_candidates,
        "n_reject_candidates": len(reject_candidates),
        "original_eem_primary_candidate_unchanged": True,
        "note": "This module does not enable paper trading or live trading; it only records a research recommendation.",
    }

    out_csv = OUT_DIR / "eem_expansion_results.csv"
    results_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(results_df)} rows)")

    out_json = OUT_DIR / "eem_expansion_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {out_json}")

    write_report(results_df, summary)

    return results_df, summary


def write_report(results_df: pd.DataFrame, summary: dict) -> None:
    lines = [
        "# EEM Mean-Reversion Expansion Report",
        "",
        "**Status: RESEARCH ONLY. No paper trading or live trading is enabled by",
        "this report. No parameter was tuned after seeing results. The original",
        "EEM `rsi_revert(14,30/70)` primary candidate's classification in",
        "`docs/JARVIS_PAPER_TRADING_CANDIDATES.md` is unchanged.**",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Data audit",
        "",
        "| Asset | Status |",
        "|---|---|",
    ]
    for sym, st in summary["data_audit"].items():
        lines.append(f"| {sym} | {st} |")

    lines += [
        "",
        f"Configs tested: {summary['n_configs_tested']}  |  "
        f"Assets available: {summary['n_assets_tested']}  |  "
        f"Total backtests run: {summary['n_total_backtests']}",
        "",
        "## 1. Does EEM RSI mean reversion generalize across related EM ETFs?",
        "",
    ]
    rsi_gen = summary["family_generalization"].get("rsi_revert", {})
    lines.append(
        f"`rsi_revert` family classification: **{rsi_gen.get('classification', 'N/A')}** "
        f"({rsi_gen.get('n_independent_survivor_assets', 0)} independent survivor "
        f"asset(s), parameter-sensitivity flag: {rsi_gen.get('sensitivity_flag', 'N/A')})."
    )

    lines += [
        "",
        "## 2. Does it generalize across nearby RSI thresholds?",
        "",
        "See the 80-config parameter-neighborhood grid (window in "
        "{7,10,14,18,21}, oversold in {20,25,30,35}, overbought in "
        "{65,70,75,80}) results in `eem_expansion_results.csv`, filtered to "
        "`family == rsi_revert`. The per-asset mean OOS Sharpe across this "
        "grid is reported in the EEM-outlier check below.",
        "",
        "## 3. Does it generalize across other mean-reversion families?",
        "",
        "| Family | Classification | Independent survivor assets | Sensitivity flag |",
        "|---|---|---|---|",
    ]
    for family, info in summary["family_generalization"].items():
        lines.append(
            f"| {family} | {info['classification']} | "
            f"{info['n_independent_survivor_assets']} | {info['sensitivity_flag']} |"
        )

    lines += [
        "",
        "## 4. Is EEM an outlier propping up the results?",
        "",
        f"```\n{json.dumps(summary['eem_outlier_check'], indent=2, default=str)}\n```",
        "",
        "## 5. Which candidate, if any, deserves paper testing?",
        "",
    ]
    if summary["n_paper_test_candidates"] == 0:
        lines.append("No new candidate from this expansion is recommended for paper "
                      "testing. The original EEM `rsi_revert(14,30/70)` primary "
                      "candidate remains the only approved candidate, unchanged by "
                      "this report.")
    else:
        lines.append(f"{summary['n_paper_test_candidates']} candidate(s) cleared every "
                      "gate in this expansion. Per the anti-overfitting rules in the "
                      "approved spec, any NEW candidate (i.e., not the original EEM "
                      "setting) found here requires its own independent future "
                      "validation before being treated as paper-test-ready -- it is "
                      "not auto-promoted by this report:")
        for c in summary["paper_test_candidates"]:
            tag = " (ORIGINAL EEM PRIMARY SETTING)" if c["is_original_eem_setting"] else ""
            lines.append(f"- {c['asset']} {c['family']}({c['params']}) -> "
                          f"{c['benchmark_classification']}, {c['duplicate_rollup']}{tag}")

    lines += [
        "",
        "## 6. Which candidates are rejected?",
        "",
        f"{summary['n_reject_candidates']} configs were rejected (funnel failure, "
        "FRAGILE bootstrap, BETA_DISGUISED/REJECT benchmark classification, or "
        "DUPLICATE_SIGNAL). Full list in `eem_expansion_results.csv`.",
        "",
        "## 7. Is this a real emerging-market mean-reversion effect, or likely a one-asset artifact?",
        "",
        f"**Headline verdict: {summary['headline_verdict']}**",
        "",
        "This verdict is derived mechanically from the `rsi_revert` family "
        "generalization classification (Question 1) cross-checked against the "
        "EEM-outlier check (Question 4), per Section 6.4/10 of the approved "
        "spec. See `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` for the full "
        "decision procedure.",
        "",
        "## Explicit scope boundary",
        "",
        "- No paper trading or live trading was enabled or performed to "
        "produce this report.",
        "- No parameter was tuned after seeing results; all grids were fixed "
        "in the approved spec before this script ran.",
        "- The original EEM `rsi_revert(14,30/70)` primary candidate is "
        "unchanged.",
        "- No strategy rule was changed to improve results.",
    ]

    out_md = OUT_DIR / "eem_expansion_report.md"
    with open(out_md, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
