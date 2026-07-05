"""
edge_hunting/category_oos_summary.py
==============================================
Category-level OOS Sharpe summary report.

For each strategy CATEGORY (TREND, MEAN_REVERSION, VOLATILITY, PATTERN,
VOLUME, COMPOSITE), summarize the already-computed sweep results:

- mean / median OOS Sharpe (across ALL configs tested in that category, not
  just survivors)
- number of configs tested
- number of survivors (funnel-passing configs)
- survival rate (survivors / configs tested)
- mean OOS max drawdown (across all configs tested)
- a concentration warning if a category's survivors are dominated by a
  single asset (i.e. the category's apparent "survival" is really just one
  asset's result repeated across parameter variants)

Rules followed
--------------
- Does not change any strategy logic, does not tune any threshold, does not
  re-run the sweep. This module is a pure aggregation/reporting layer over
  the already-existing reports/edge_hunting/sweep_results.csv (the full,
  pre-filter set of every backtest in the original 2,697-backtest sweep).
  This is the correct source for this report (unlike
  same_strategy_across_assets.py, which only needed survivors) because
  "number of configs tested" and "mean OOS Sharpe across all configs" both
  require the full, non-survivor-filtered dataset.
- No new backtest is executed anywhere in this module.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPORTS_DIR = Path("reports/edge_hunting")
SWEEP_RESULTS_CSV = REPORTS_DIR / "sweep_results.csv"

OUT_CSV = REPORTS_DIR / "category_oos_summary.csv"
OUT_MD = REPORTS_DIR / "category_oos_summary_report.md"

# Concentration-warning threshold: if a single asset accounts for >= this
# fraction of a category's survivors, flag it. Reporting-only label, not a
# funnel filter, not used to reject/accept anything, not a threshold change
# to edge_hunting/funnel.py.
CONCENTRATION_WARN_FRACTION = 0.5
# Minimum survivor count before a concentration warning is even considered
# meaningful (a category with only 1 survivor is trivially "concentrated").
CONCENTRATION_MIN_SURVIVORS = 2


def _load_sweep_results() -> pd.DataFrame:
    if not SWEEP_RESULTS_CSV.exists():
        raise FileNotFoundError(
            f"{SWEEP_RESULTS_CSV} not found. This report requires the "
            "existing full sweep output; it does not run a new sweep."
        )
    df = pd.read_csv(SWEEP_RESULTS_CSV)
    # survived column is written as literal "True"/"False" strings by pandas
    # to_csv/read_csv round-trip of a bool column; be defensive either way.
    if df["survived"].dtype != bool:
        df["survived"] = df["survived"].astype(str).str.strip().str.lower() == "true"
    return df


def _concentration_warning(survivors: pd.DataFrame) -> str:
    """Return a warning string if survivors are dominated by one asset,
    else an empty string. Pure descriptive label over already-existing
    survivor rows -- no new computation of returns/Sharpe/drawdown."""
    n_survivors = len(survivors)
    if n_survivors < CONCENTRATION_MIN_SURVIVORS:
        return ""
    asset_counts = survivors["asset"].value_counts()
    top_asset = asset_counts.index[0]
    top_count = int(asset_counts.iloc[0])
    top_fraction = top_count / n_survivors
    if top_fraction >= CONCENTRATION_WARN_FRACTION:
        return (
            f"WARNING: {top_count} of {n_survivors} survivors "
            f"({top_fraction:.0%}) are on a single asset ({top_asset})"
        )
    return ""


def build_category_oos_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Group the full (pre-filter) sweep results by category and compute
    the summary stats. No strategy logic, no thresholds, no
    re-backtesting -- pure groupby/aggregate over existing columns."""
    rows = []
    for category, g in df.groupby("category"):
        n_tested = len(g)
        survivors = g[g["survived"]]
        n_survivors = len(survivors)
        survival_rate = n_survivors / n_tested if n_tested else 0.0

        mean_oos_sharpe = float(g["oos_sharpe"].mean())
        median_oos_sharpe = float(g["oos_sharpe"].median())
        mean_oos_max_drawdown = float(g["oos_max_drawdown"].mean())

        warning = _concentration_warning(survivors)

        rows.append({
            "category": category,
            "n_configs_tested": n_tested,
            "n_survivors": n_survivors,
            "survival_rate": survival_rate,
            "mean_oos_sharpe": mean_oos_sharpe,
            "median_oos_sharpe": median_oos_sharpe,
            "mean_oos_max_drawdown": mean_oos_max_drawdown,
            "concentration_warning": warning,
        })

    out = pd.DataFrame(rows).sort_values(
        by="survival_rate", ascending=False
    ).reset_index(drop=True)
    return out


def write_report(summary_df: pd.DataFrame, full_df: pd.DataFrame) -> str:
    total_tested = len(full_df)
    total_survivors = int(full_df["survived"].sum())

    lines = [
        "# Category-Level OOS Sharpe Summary Report",
        "",
        "**Status: reporting/aggregation only.** No strategy logic was",
        "changed, no threshold was tuned, and no new sweep or backtest was",
        "run. This report is a groupby/aggregate over the already-existing",
        f"`{SWEEP_RESULTS_CSV.as_posix()}` ({total_tested} total backtests,",
        f"{total_survivors} survivors, from the original sweep documented in",
        "`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`).",
        "",
        "## Purpose",
        "",
        "Summarize out-of-sample performance and funnel survival at the",
        "strategy-CATEGORY level (TREND, MEAN_REVERSION, VOLATILITY,",
        "PATTERN, VOLUME, COMPOSITE) so that category-level conclusions",
        "already stated qualitatively elsewhere in",
        "`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` (Sections 1 and 6) are",
        "backed by a single, explicit, reproducible table -- and so that",
        "any category whose apparent survival is really just one asset's",
        "result, repeated across parameter variants, is flagged rather than",
        "silently counted as broad category-level evidence.",
        "",
        f"Concentration warning rule (reporting label only, not a funnel",
        f"filter): a category is flagged if one single asset accounts for",
        f">= {CONCENTRATION_WARN_FRACTION:.0%} of that category's survivors,",
        f"and the category has at least {CONCENTRATION_MIN_SURVIVORS}",
        "survivors (categories with 0-1 survivors are not flagged, since",
        "concentration is not a meaningful concept for such a small set).",
        "",
        "## Category summary",
        "",
        "| Category | # Configs tested | # Survivors | Survival rate | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Concentration warning |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, r in summary_df.iterrows():
        warning_cell = r["concentration_warning"] if r["concentration_warning"] else "-"
        lines.append(
            f"| {r['category']} | {r['n_configs_tested']} | {r['n_survivors']} | "
            f"{r['survival_rate']:.1%} | {r['mean_oos_sharpe']:.4f} | "
            f"{r['median_oos_sharpe']:.4f} | {r['mean_oos_max_drawdown']:.4f} | "
            f"{warning_cell} |"
        )

    warned = summary_df[summary_df["concentration_warning"] != ""]
    lines += [
        "",
        "## Concentration findings",
        "",
    ]
    if warned.empty:
        lines.append(
            "No category triggered the single-asset concentration warning: "
            "every category with 2+ survivors has its survivors spread "
            "across more than one asset."
        )
    else:
        for _, r in warned.iterrows():
            lines.append(f"- **{r['category']}**: {r['concentration_warning']}")

    lines += [
        "",
        "## Caveats",
        "",
        "- Mean/median OOS Sharpe here are computed over ALL configs tested",
        "  in a category, including the large majority that failed the",
        "  funnel -- these are descriptive statistics of category-level",
        "  performance, not evidence that any given failing config was",
        "  close to viable. See per-survivor detail in",
        "  `reports/edge_hunting/top_survivors.csv` and",
        "  `reports/edge_hunting/same_strategy_across_assets_report.md` for",
        "  survivor-only breadth analysis.",
        "- No multiple-comparisons correction is applied here (see",
        "  `docs/BRENDAN_VIDEO_VS_JARVIS_AUDIT.md` Item 11); a category's",
        "  survival rate reflects how many of its own configs passed the",
        "  funnel out of how many were tried, not a probability that its",
        "  survivors are genuine skill rather than chance.",
        "- The concentration-warning threshold",
        f"  (`CONCENTRATION_WARN_FRACTION = {CONCENTRATION_WARN_FRACTION:.0%}`)",
        "  is an unopinionated reporting label chosen for this report only --",
        "  it is not, and must not be treated as, a funnel/threshold change",
        "  to `edge_hunting/funnel.py`.",
        "",
    ]

    return "\n".join(lines)


def main():
    df = _load_sweep_results()
    summary_df = build_category_oos_summary(df)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} ({len(summary_df)} categories)")

    report_text = write_report(summary_df, df)
    OUT_MD.write_text(report_text, encoding="utf-8")
    print(f"Wrote {OUT_MD}")

    return summary_df


if __name__ == "__main__":
    main()
