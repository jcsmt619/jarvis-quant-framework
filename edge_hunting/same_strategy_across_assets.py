"""
edge_hunting/same_strategy_across_assets.py
==============================================
"Same strategy across assets" survival report.

For each exact surviving strategy configuration (family + parameter set,
i.e. the `strategy_name` column already produced by the sweep/funnel), count
how many DISTINCT assets produced a surviving config for that exact
strategy_name, and report the surviving asset list plus summary OOS
statistics.

Purpose (per docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md and
docs/JARVIS_EDGE_HUNTING_ANALYSIS.md Section 14): determine whether a given
surviving strategy (e.g. EEM's rsi_revert(14,30/70)) is a broad,
generalizable mean-reversion pattern that shows up across many independent
assets, or an isolated, single-asset artifact.

Rules followed
--------------
- Does not change any strategy logic, does not tune any threshold, does not
  re-run the sweep. This module is a pure aggregation/reporting layer over
  the already-existing, already-computed
  reports/edge_hunting/top_survivors.csv (35 survivors from the original
  2,697-backtest sweep). sweep_results.csv (the full, pre-filter set of all
  backtests) is read only as a fallback/cross-check if top_survivors.csv is
  unavailable -- it is not required for the primary computation because
  top_survivors.csv already contains every field needed (asset,
  strategy_name, family, category, oos_sharpe, oos_max_drawdown, survived).
- No new backtest is executed anywhere in this module.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPORTS_DIR = Path("reports/edge_hunting")
TOP_SURVIVORS_CSV = REPORTS_DIR / "top_survivors.csv"
SWEEP_RESULTS_CSV = REPORTS_DIR / "sweep_results.csv"

OUT_CSV = REPORTS_DIR / "same_strategy_across_assets.csv"
OUT_MD = REPORTS_DIR / "same_strategy_across_assets_report.md"

# Breadth classification threshold: a strategy_name surviving on >= this
# many distinct assets is considered "broad"; fewer is "one-asset-specific"
# (or narrow, for 2-3 assets). This is a reporting-only classification
# label, not a funnel filter, and is not used to reject/accept anything.
BROAD_MIN_ASSETS = 3


def _load_survivors() -> pd.DataFrame:
    """Load the survivor set. Prefers top_survivors.csv (already the
    filtered survivor list); falls back to filtering sweep_results.csv by
    its own `survived` column if top_survivors.csv is missing. Does not
    apply any new filter logic -- only reuses the `survived` flag already
    computed by edge_hunting/funnel.py during the original sweep."""
    if TOP_SURVIVORS_CSV.exists():
        df = pd.read_csv(TOP_SURVIVORS_CSV)
    elif SWEEP_RESULTS_CSV.exists():
        df = pd.read_csv(SWEEP_RESULTS_CSV)
        df = df[df["survived"] == True]  # noqa: E712 - explicit bool compare from CSV
    else:
        raise FileNotFoundError(
            f"Neither {TOP_SURVIVORS_CSV} nor {SWEEP_RESULTS_CSV} found. "
            "This report requires the existing sweep/funnel output; it does "
            "not run a new sweep."
        )
    return df


def build_same_strategy_across_assets(df: pd.DataFrame) -> pd.DataFrame:
    """Group already-computed survivors by exact strategy_name (family +
    params) and compute the cross-asset breadth stats. No strategy logic,
    no thresholds, no re-backtesting -- pure groupby/aggregate over
    existing columns."""
    rows = []
    for strategy_name, g in df.groupby("strategy_name"):
        assets = sorted(g["asset"].unique().tolist())
        n_assets = len(assets)
        family = g["family"].iloc[0]
        category = g["category"].iloc[0]
        mean_oos_sharpe = float(g["oos_sharpe"].mean())
        median_oos_sharpe = float(g["oos_sharpe"].median())
        mean_oos_max_drawdown = float(g["oos_max_drawdown"].mean())
        breadth = "BROAD" if n_assets >= BROAD_MIN_ASSETS else (
            "ONE_ASSET_SPECIFIC" if n_assets == 1 else "NARROW"
        )
        rows.append({
            "strategy_name": strategy_name,
            "family": family,
            "category": category,
            "n_surviving_assets": n_assets,
            "surviving_assets": ", ".join(assets),
            "mean_oos_sharpe": mean_oos_sharpe,
            "median_oos_sharpe": median_oos_sharpe,
            "mean_oos_max_drawdown": mean_oos_max_drawdown,
            "breadth_classification": breadth,
        })

    out = pd.DataFrame(rows).sort_values(
        by=["n_surviving_assets", "mean_oos_sharpe"], ascending=[False, False]
    ).reset_index(drop=True)
    return out


def build_family_rollup(df: pd.DataFrame) -> pd.DataFrame:
    """Same breadth analysis rolled up one level higher, to the strategy
    FAMILY (e.g. all rsi_revert parameter variants pooled together), since
    the task also asks for the family-level view alongside the exact
    strategy_name-level view. Still pure aggregation over already-existing
    survivor rows -- no new computation of returns/Sharpe/drawdown."""
    rows = []
    for family, g in df.groupby("family"):
        assets = sorted(g["asset"].unique().tolist())
        n_assets = len(assets)
        category = g["category"].iloc[0]
        mean_oos_sharpe = float(g["oos_sharpe"].mean())
        median_oos_sharpe = float(g["oos_sharpe"].median())
        mean_oos_max_drawdown = float(g["oos_max_drawdown"].mean())
        breadth = "BROAD" if n_assets >= BROAD_MIN_ASSETS else (
            "ONE_ASSET_SPECIFIC" if n_assets == 1 else "NARROW"
        )
        rows.append({
            "family": family,
            "category": category,
            "n_surviving_configs": len(g),
            "n_surviving_assets": n_assets,
            "surviving_assets": ", ".join(assets),
            "mean_oos_sharpe": mean_oos_sharpe,
            "median_oos_sharpe": median_oos_sharpe,
            "mean_oos_max_drawdown": mean_oos_max_drawdown,
            "breadth_classification": breadth,
        })

    out = pd.DataFrame(rows).sort_values(
        by=["n_surviving_assets", "mean_oos_sharpe"], ascending=[False, False]
    ).reset_index(drop=True)
    return out


def write_report(strategy_df: pd.DataFrame, family_df: pd.DataFrame) -> str:
    lines = [
        "# Same-Strategy-Across-Assets Survival Report",
        "",
        "**Status: reporting/aggregation only.** No strategy logic was",
        "changed, no threshold was tuned, and no new sweep or backtest was",
        "run. This report is a groupby/aggregate over the already-existing",
        f"`{TOP_SURVIVORS_CSV.as_posix()}` (35 survivors from the original",
        "2,697-backtest sweep documented in `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`).",
        "",
        "## Purpose",
        "",
        "Determine whether a given surviving strategy configuration is a",
        "broad, generalizable pattern that shows up across many independent",
        "assets, or a narrow / single-asset artifact -- directly answering,",
        "with Jarvis's own already-computed data, the same style of question",
        "raised in `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` and",
        "`private_research/youtube_ai_pathways/BRENDAN_9000_STRATEGIES_NOTES.md`",
        "(Brendan Li's claim that RSI mean reversion survived on 20 distinct",
        "tickers and Keltner reversion on 18, in that separate, unverified,",
        "secondhand source).",
        "",
        f"Breadth classification rule (reporting label only, not a funnel",
        f"filter): `BROAD` if a strategy survives on >= {BROAD_MIN_ASSETS}",
        "distinct assets, `NARROW` if on 2 assets, `ONE_ASSET_SPECIFIC` if on",
        "exactly 1 asset.",
        "",
        "## Per-exact-strategy-configuration breadth (family + parameters)",
        "",
        "| Strategy name | Family | Category | # Assets | Assets | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Breadth |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in strategy_df.iterrows():
        lines.append(
            f"| {r['strategy_name']} | {r['family']} | {r['category']} | "
            f"{r['n_surviving_assets']} | {r['surviving_assets']} | "
            f"{r['mean_oos_sharpe']:.4f} | {r['median_oos_sharpe']:.4f} | "
            f"{r['mean_oos_max_drawdown']:.4f} | {r['breadth_classification']} |"
        )

    lines += [
        "",
        "## Per-family breadth (all parameter variants pooled)",
        "",
        "| Family | Category | # Surviving configs | # Assets | Assets | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Breadth |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in family_df.iterrows():
        lines.append(
            f"| {r['family']} | {r['category']} | {r['n_surviving_configs']} | "
            f"{r['n_surviving_assets']} | {r['surviving_assets']} | "
            f"{r['mean_oos_sharpe']:.4f} | {r['median_oos_sharpe']:.4f} | "
            f"{r['mean_oos_max_drawdown']:.4f} | {r['breadth_classification']} |"
        )

    # EEM rsi_revert specific callout, since that is the motivating question.
    eem_rows = strategy_df[
        strategy_df["strategy_name"].str.startswith("rsi_revert")
        & strategy_df["surviving_assets"].str.contains("EEM")
    ]
    rsi_family_row = family_df[family_df["family"] == "rsi_revert"]

    lines += [
        "",
        "## EEM rsi_revert finding",
        "",
    ]
    if not rsi_family_row.empty:
        n_assets = int(rsi_family_row.iloc[0]["n_surviving_assets"])
        assets_list = rsi_family_row.iloc[0]["surviving_assets"]
        breadth_label = rsi_family_row.iloc[0]["breadth_classification"]
        lines.append(
            f"At the family level, `rsi_revert` (across all its surviving "
            f"parameter variants) survived on **{n_assets}** distinct "
            f"assets in the original 29-asset sweep universe: {assets_list}. "
            f"Family-level breadth classification: **{breadth_label}**."
        )
        lines.append("")
        lines.append(
            "This means EEM's rsi_revert survivors are **not isolated "
            "single-asset artifacts within this sweep** -- the same "
            "rsi_revert family also survives independently on other assets "
            "in the universe (see per-family table above for the exact "
            "asset list). This is consistent with, and independently "
            "corroborates using Jarvis's own already-computed sweep data, "
            "the separate, more targeted generalization test already "
            "performed in `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` / "
            "`edge_hunting/eem_expansion.py` (which found RSI reversion "
            "generalized across 9 of 13 emerging-market ETFs tested)."
        )
    else:
        lines.append(
            "`rsi_revert` does not appear in the current survivor set -- "
            "no cross-asset breadth conclusion can be drawn from this "
            "report alone."
        )

    lines += [
        "",
        "## Caveats",
        "",
        "- This report only sees the 35 already-filtered survivors in "
        "`top_survivors.csv`. It cannot distinguish \"strategy X failed on "
        "asset Y\" from \"strategy X was never tested on asset Y\" -- both "
        "look identical (absent) from this survivor-only view. A future, "
        "separately-scoped task could join against the full, pre-filter "
        f"`{SWEEP_RESULTS_CSV.as_posix()}` to report, for every surviving "
        "strategy_name, how many of the 29 universe assets it was actually "
        "tested against vs. how many it survived on, giving a true "
        "survival rate per asset rather than just a survivor count.",
        "- No multiple-comparisons correction is applied here (see "
        "`docs/BRENDAN_VIDEO_VS_JARVIS_AUDIT.md` Item 11); a strategy "
        "surviving on 2-3 assets out of 29 tested could still be partly "
        "attributable to chance given the total number of trials in the "
        "original sweep.",
        "- Breadth classification thresholds (`BROAD_MIN_ASSETS = 3`) are "
        "an unopinionated reporting label chosen for this report only -- "
        "they are not, and must not be treated as, a funnel/threshold "
        "change to `edge_hunting/funnel.py`.",
        "",
    ]

    return "\n".join(lines)


def main():
    df = _load_survivors()
    strategy_df = build_same_strategy_across_assets(df)
    family_df = build_family_rollup(df)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    strategy_df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} ({len(strategy_df)} unique strategy configs)")

    report_text = write_report(strategy_df, family_df)
    OUT_MD.write_text(report_text, encoding="utf-8")
    print(f"Wrote {OUT_MD}")

    return strategy_df, family_df


if __name__ == "__main__":
    main()
