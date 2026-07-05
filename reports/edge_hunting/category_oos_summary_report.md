# Category-Level OOS Sharpe Summary Report

**Status: reporting/aggregation only.** No strategy logic was
changed, no threshold was tuned, and no new sweep or backtest was
run. This report is a groupby/aggregate over the already-existing
`reports/edge_hunting/sweep_results.csv` (2697 total backtests,
35 survivors, from the original sweep documented in
`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`).

## Purpose

Summarize out-of-sample performance and funnel survival at the
strategy-CATEGORY level (TREND, MEAN_REVERSION, VOLATILITY,
PATTERN, VOLUME, COMPOSITE) so that category-level conclusions
already stated qualitatively elsewhere in
`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` (Sections 1 and 6) are
backed by a single, explicit, reproducible table -- and so that
any category whose apparent survival is really just one asset's
result, repeated across parameter variants, is flagged rather than
silently counted as broad category-level evidence.

Concentration warning rule (reporting label only, not a funnel
filter): a category is flagged if one single asset accounts for
>= 50% of that category's survivors,
and the category has at least 2
survivors (categories with 0-1 survivors are not flagged, since
concentration is not a meaningful concept for such a small set).

## Category summary

| Category | # Configs tested | # Survivors | Survival rate | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Concentration warning |
|---|---|---|---|---|---|---|---|
| MEAN_REVERSION | 754 | 19 | 2.5% | 0.1371 | 0.1728 | -0.2029 | - |
| COMPOSITE | 87 | 1 | 1.1% | -0.1639 | 0.0000 | -0.2968 | - |
| TREND | 1247 | 13 | 1.0% | -0.0531 | -0.0542 | -0.3965 | - |
| PATTERN | 174 | 1 | 0.6% | -0.0779 | -0.0437 | -0.2724 | - |
| VOLATILITY | 174 | 1 | 0.6% | -0.2090 | -0.2472 | -0.2393 | - |
| VOLUME | 261 | 0 | 0.0% | -0.1468 | -0.1515 | -0.3477 | - |

## Concentration findings

No category triggered the single-asset concentration warning: every category with 2+ survivors has its survivors spread across more than one asset.

## Caveats

- Mean/median OOS Sharpe here are computed over ALL configs tested
  in a category, including the large majority that failed the
  funnel -- these are descriptive statistics of category-level
  performance, not evidence that any given failing config was
  close to viable. See per-survivor detail in
  `reports/edge_hunting/top_survivors.csv` and
  `reports/edge_hunting/same_strategy_across_assets_report.md` for
  survivor-only breadth analysis.
- No multiple-comparisons correction is applied here (see
  `docs/BRENDAN_VIDEO_VS_JARVIS_AUDIT.md` Item 11); a category's
  survival rate reflects how many of its own configs passed the
  funnel out of how many were tried, not a probability that its
  survivors are genuine skill rather than chance.
- The concentration-warning threshold
  (`CONCENTRATION_WARN_FRACTION = 50%`)
  is an unopinionated reporting label chosen for this report only --
  it is not, and must not be treated as, a funnel/threshold change
  to `edge_hunting/funnel.py`.
