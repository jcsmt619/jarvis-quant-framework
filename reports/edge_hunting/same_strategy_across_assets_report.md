# Same-Strategy-Across-Assets Survival Report

**Status: reporting/aggregation only.** No strategy logic was
changed, no threshold was tuned, and no new sweep or backtest was
run. This report is a groupby/aggregate over the already-existing
`reports/edge_hunting/top_survivors.csv` (35 survivors from the original
2,697-backtest sweep documented in `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`).

## Purpose

Determine whether a given surviving strategy configuration is a
broad, generalizable pattern that shows up across many independent
assets, or a narrow / single-asset artifact -- directly answering,
with Jarvis's own already-computed data, the same style of question
raised in `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` and
`private_research/youtube_ai_pathways/BRENDAN_9000_STRATEGIES_NOTES.md`
(Brendan Li's claim that RSI mean reversion survived on 20 distinct
tickers and Keltner reversion on 18, in that separate, unverified,
secondhand source).

Breadth classification rule (reporting label only, not a funnel
filter): `BROAD` if a strategy survives on >= 3
distinct assets, `NARROW` if on 2 assets, `ONE_ASSET_SPECIFIC` if on
exactly 1 asset.

## Per-exact-strategy-configuration breadth (family + parameters)

| Strategy name | Family | Category | # Assets | Assets | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Breadth |
|---|---|---|---|---|---|---|---|---|
| dual_momentum__window60_rel_window126 | dual_momentum | TREND | 8 | AAPL, AMZN, HYG, MSFT, NVDA, SPY, XLF, XLY | 0.7256 | 0.6457 | -0.1898 | BROAD |
| dual_momentum__window126_rel_window126 | dual_momentum | TREND | 4 | AAPL, HYG, MSFT, XLF | 0.6696 | 0.6839 | -0.2235 | BROAD |
| rsi_revert__window7_oversold30_overbought75 | rsi_revert | MEAN_REVERSION | 3 | GOOGL, SPY, XLK | 0.5613 | 0.5390 | -0.1371 | BROAD |
| percent_b_revert__window20_lower0.05_upper0.95 | percent_b_revert | MEAN_REVERSION | 2 | MSFT, XLK | 0.7332 | 0.7332 | -0.1365 | NARROW |
| rsi_revert__window7_oversold25_overbought70 | rsi_revert | MEAN_REVERSION | 2 | EFA, TLT | 0.6947 | 0.6947 | -0.0751 | NARROW |
| keltner_revert__window20_atr_mult2.0 | keltner_revert | MEAN_REVERSION | 2 | AMZN, MSFT | 0.6879 | 0.6879 | -0.1230 | NARROW |
| rsi_revert__window14_oversold25_overbought70 | rsi_revert | MEAN_REVERSION | 2 | EEM, XLP | 0.5416 | 0.5416 | -0.0562 | NARROW |
| atr_breakout__window14_mult1.5 | atr_breakout | VOLATILITY | 1 | BTC-USD | 0.8797 | 0.8797 | -0.3107 | ONE_ASSET_SPECIFIC |
| cci_revert__window20_threshold150 | cci_revert | MEAN_REVERSION | 1 | QQQ | 0.7251 | 0.7251 | -0.0841 | ONE_ASSET_SPECIFIC |
| rsi_revert__window14_oversold30_overbought70 | rsi_revert | MEAN_REVERSION | 1 | EEM | 0.6515 | 0.6515 | -0.0991 | ONE_ASSET_SPECIFIC |
| pivot_bounce__window5_tolerance0.01 | pivot_bounce | PATTERN | 1 | TLT | 0.6388 | 0.6388 | -0.1178 | ONE_ASSET_SPECIFIC |
| rsi_revert__window7_oversold30_overbought70 | rsi_revert | MEAN_REVERSION | 1 | EFA | 0.6348 | 0.6348 | -0.0862 | ONE_ASSET_SPECIFIC |
| donchian_breakout__window55 | donchian_breakout | TREND | 1 | ETH-USD | 0.6317 | 0.6317 | -0.1758 | ONE_ASSET_SPECIFIC |
| ultimate_oscillator_revert__w17_w214_w328 | ultimate_oscillator_revert | MEAN_REVERSION | 1 | EEM | 0.6204 | 0.6204 | -0.0577 | ONE_ASSET_SPECIFIC |
| bollinger_revert__window20_num_std2.0 | bollinger_revert | MEAN_REVERSION | 1 | XLK | 0.6003 | 0.6003 | -0.0873 | ONE_ASSET_SPECIFIC |
| zscore_revert__window20_threshold2.0 | zscore_revert | MEAN_REVERSION | 1 | XLK | 0.6003 | 0.6003 | -0.0873 | ONE_ASSET_SPECIFIC |
| rsi_revert__window14_oversold30_overbought75 | rsi_revert | MEAN_REVERSION | 1 | QQQ | 0.5649 | 0.5649 | -0.0423 | ONE_ASSET_SPECIFIC |
| rsi_revert__window7_oversold25_overbought75 | rsi_revert | MEAN_REVERSION | 1 | EFA | 0.5322 | 0.5322 | -0.0828 | ONE_ASSET_SPECIFIC |
| macd_rsi_confirm__fast12_slow26_signal9_rsi_window14 | macd_rsi_confirm | COMPOSITE | 1 | AAPL | 0.5007 | 0.5007 | -0.2791 | ONE_ASSET_SPECIFIC |

## Per-family breadth (all parameter variants pooled)

| Family | Category | # Surviving configs | # Assets | Assets | Mean OOS Sharpe | Median OOS Sharpe | Mean OOS Max DD | Breadth |
|---|---|---|---|---|---|---|---|---|
| dual_momentum | TREND | 12 | 8 | AAPL, AMZN, HYG, MSFT, NVDA, SPY, XLF, XLY | 0.7069 | 0.6554 | -0.2010 | BROAD |
| rsi_revert | MEAN_REVERSION | 11 | 8 | EEM, EFA, GOOGL, QQQ, SPY, TLT, XLK, XLP | 0.5945 | 0.5649 | -0.0895 | BROAD |
| percent_b_revert | MEAN_REVERSION | 2 | 2 | MSFT, XLK | 0.7332 | 0.7332 | -0.1365 | NARROW |
| keltner_revert | MEAN_REVERSION | 2 | 2 | AMZN, MSFT | 0.6879 | 0.6879 | -0.1230 | NARROW |
| atr_breakout | VOLATILITY | 1 | 1 | BTC-USD | 0.8797 | 0.8797 | -0.3107 | ONE_ASSET_SPECIFIC |
| cci_revert | MEAN_REVERSION | 1 | 1 | QQQ | 0.7251 | 0.7251 | -0.0841 | ONE_ASSET_SPECIFIC |
| pivot_bounce | PATTERN | 1 | 1 | TLT | 0.6388 | 0.6388 | -0.1178 | ONE_ASSET_SPECIFIC |
| donchian_breakout | TREND | 1 | 1 | ETH-USD | 0.6317 | 0.6317 | -0.1758 | ONE_ASSET_SPECIFIC |
| ultimate_oscillator_revert | MEAN_REVERSION | 1 | 1 | EEM | 0.6204 | 0.6204 | -0.0577 | ONE_ASSET_SPECIFIC |
| bollinger_revert | MEAN_REVERSION | 1 | 1 | XLK | 0.6003 | 0.6003 | -0.0873 | ONE_ASSET_SPECIFIC |
| zscore_revert | MEAN_REVERSION | 1 | 1 | XLK | 0.6003 | 0.6003 | -0.0873 | ONE_ASSET_SPECIFIC |
| macd_rsi_confirm | COMPOSITE | 1 | 1 | AAPL | 0.5007 | 0.5007 | -0.2791 | ONE_ASSET_SPECIFIC |

## EEM rsi_revert finding

At the family level, `rsi_revert` (across all its surviving parameter variants) survived on **8** distinct assets in the original 29-asset sweep universe: EEM, EFA, GOOGL, QQQ, SPY, TLT, XLK, XLP. Family-level breadth classification: **BROAD**.

This means EEM's rsi_revert survivors are **not isolated single-asset artifacts within this sweep** -- the same rsi_revert family also survives independently on other assets in the universe (see per-family table above for the exact asset list). This is consistent with, and independently corroborates using Jarvis's own already-computed sweep data, the separate, more targeted generalization test already performed in `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` / `edge_hunting/eem_expansion.py` (which found RSI reversion generalized across 9 of 13 emerging-market ETFs tested).

## Caveats

- This report only sees the 35 already-filtered survivors in `top_survivors.csv`. It cannot distinguish "strategy X failed on asset Y" from "strategy X was never tested on asset Y" -- both look identical (absent) from this survivor-only view. A future, separately-scoped task could join against the full, pre-filter `reports/edge_hunting/sweep_results.csv` to report, for every surviving strategy_name, how many of the 29 universe assets it was actually tested against vs. how many it survived on, giving a true survival rate per asset rather than just a survivor count.
- No multiple-comparisons correction is applied here (see `docs/BRENDAN_VIDEO_VS_JARVIS_AUDIT.md` Item 11); a strategy surviving on 2-3 assets out of 29 tested could still be partly attributable to chance given the total number of trials in the original sweep.
- Breadth classification thresholds (`BROAD_MIN_ASSETS = 3`) are an unopinionated reporting label chosen for this report only -- they are not, and must not be treated as, a funnel/threshold change to `edge_hunting/funnel.py`.
