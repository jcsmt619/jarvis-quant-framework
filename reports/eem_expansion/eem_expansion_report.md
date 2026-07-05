# EEM Mean-Reversion Expansion Report

**Status: RESEARCH ONLY. No paper trading or live trading is enabled by
this report. No parameter was tuned after seeing results. The original
EEM `rsi_revert(14,30/70)` primary candidate's classification in
`docs/JARVIS_PAPER_TRADING_CANDIDATES.md` is unchanged.**

Generated: 2026-07-05T01:50:45.644240Z

## Data audit

| Asset | Status |
|---|---|
| EEM | INCLUDED |
| VWO | INCLUDED |
| IEMG | INCLUDED |
| EWZ | INCLUDED |
| FXI | INCLUDED |
| INDA | INCLUDED |
| EWT | INCLUDED |
| EWY | INCLUDED |
| EWW | INCLUDED |
| EZA | INCLUDED |
| EIDO | INCLUDED |
| TUR | INCLUDED |
| ILF | INCLUDED |
| RSX | INCLUDED_PREHALT_ONLY_EXCLUDED_FROM_AGGREGATE |

Configs tested: 91  |  Assets available: 13  |  Total backtests run: 1183

## 1. Does EEM RSI mean reversion generalize across related EM ETFs?

`rsi_revert` family classification: **GENERALIZES** (9 independent survivor asset(s), parameter-sensitivity flag: ROBUST).

## 2. Does it generalize across nearby RSI thresholds?

See the 80-config parameter-neighborhood grid (window in {7,10,14,18,21}, oversold in {20,25,30,35}, overbought in {65,70,75,80}) results in `eem_expansion_results.csv`, filtered to `family == rsi_revert`. The per-asset mean OOS Sharpe across this grid is reported in the EEM-outlier check below.

## 3. Does it generalize across other mean-reversion families?

| Family | Classification | Independent survivor assets | Sensitivity flag |
|---|---|---|---|
| rsi_revert | GENERALIZES | 9 | ROBUST |
| percent_b_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |
| bollinger_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |
| keltner_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |
| zscore_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |
| cci_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |
| williams_r_revert | DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT | 0 | ROBUST |

## 4. Is EEM an outlier propping up the results?

```
{
  "is_outlier": false,
  "eem_mean_sharpe": 0.3597607580242067,
  "other_assets_mean_sharpe": 0.3442527723465152,
  "other_assets_std_sharpe": 0.15712315353613462,
  "threshold": 0.5013759258826498,
  "flag": "NO_OUTLIER_DETECTED"
}
```

## 5. Which candidate, if any, deserves paper testing?

30 candidate(s) cleared every gate in this expansion. Per the anti-overfitting rules in the approved spec, any NEW candidate (i.e., not the original EEM setting) found here requires its own independent future validation before being treated as paper-test-ready -- it is not auto-promoted by this report:
- EEM rsi_revert({"overbought": 75, "oversold": 25, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EEM rsi_revert({"overbought": 70, "oversold": 20, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EEM rsi_revert({"overbought": 70, "oversold": 25, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EEM rsi_revert({"overbought": 70, "oversold": 30, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE (ORIGINAL EEM PRIMARY SETTING)
- EEM rsi_revert({"overbought": 70, "oversold": 35, "window": 18}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EEM rsi_revert({"overbought": 65, "oversold": 35, "window": 21}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- VWO rsi_revert({"overbought": 80, "oversold": 25, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- VWO rsi_revert({"overbought": 70, "oversold": 30, "window": 18}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- IEMG rsi_revert({"overbought": 75, "oversold": 35, "window": 18}) -> DEFENSIVE_CANDIDATE, NEAR_DUPLICATE
- IEMG rsi_revert({"overbought": 65, "oversold": 35, "window": 21}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- IEMG rsi_revert({"overbought": 70, "oversold": 35, "window": 21}) -> DEFENSIVE_CANDIDATE, NEAR_DUPLICATE
- EWZ rsi_revert({"overbought": 65, "oversold": 30, "window": 21}) -> ROBUST_CANDIDATE, UNIQUE_SIGNAL
- EWT rsi_revert({"overbought": 80, "oversold": 30, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWT rsi_revert({"overbought": 80, "oversold": 35, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWT rsi_revert({"overbought": 75, "oversold": 30, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWT rsi_revert({"overbought": 80, "oversold": 30, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWT rsi_revert({"overbought": 70, "oversold": 35, "window": 18}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWY rsi_revert({"overbought": 70, "oversold": 30, "window": 18}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EWW rsi_revert({"overbought": 70, "oversold": 20, "window": 10}) -> ROBUST_CANDIDATE, UNIQUE_SIGNAL
- EZA rsi_revert({"overbought": 70, "oversold": 20, "window": 7}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 75, "oversold": 20, "window": 7}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 80, "oversold": 20, "window": 7}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 65, "oversold": 25, "window": 7}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 70, "oversold": 30, "window": 7}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 65, "oversold": 30, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 70, "oversold": 35, "window": 10}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 65, "oversold": 30, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 65, "oversold": 35, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- EZA rsi_revert({"overbought": 75, "oversold": 35, "window": 14}) -> ROBUST_CANDIDATE, NEAR_DUPLICATE
- TUR rsi_revert({"overbought": 80, "oversold": 30, "window": 10}) -> ROBUST_CANDIDATE, UNIQUE_SIGNAL

## 6. Which candidates are rejected?

1144 configs were rejected (funnel failure, FRAGILE bootstrap, BETA_DISGUISED/REJECT benchmark classification, or DUPLICATE_SIGNAL). Full list in `eem_expansion_results.csv`.

## 7. Is this a real emerging-market mean-reversion effect, or likely a one-asset artifact?

**Headline verdict: EDGE_LIKELY_REAL_AND_EM_STRUCTURAL**

This verdict is derived mechanically from the `rsi_revert` family generalization classification (Question 1) cross-checked against the EEM-outlier check (Question 4), per Section 6.4/10 of the approved spec. See `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` for the full decision procedure.

## Explicit scope boundary

- No paper trading or live trading was enabled or performed to produce this report.
- No parameter was tuned after seeing results; all grids were fixed in the approved spec before this script ran.
- The original EEM `rsi_revert(14,30/70)` primary candidate is unchanged.
- No strategy rule was changed to improve results.
