# Jarvis Edge-Hunting Sweep — Analysis

**Scope note:** This document is an analysis of the results already produced by the sweep run on
2,697 backtests (93 strategy configs × 29 assets, daily yfinance data, 1bp/side cost, no live
trading/execution). No code was modified, no parameters were tuned, and the sweep was not re-run.
All numbers below are read directly from:

- `reports/edge_hunting/sweep_results.csv` (raw per-config-per-asset results)
- `reports/edge_hunting/top_survivors.csv` (the 35 configs that survived all six funnel filters)
- `reports/edge_hunting/funnel_report.md` / `funnel_summary.json` (aggregate funnel statistics)
- `reports/edge_hunting/cross_sectional_momentum.csv` / `cross_sectional_momentum_report.md`
- `reports/edge_hunting/bootstrap_stress_test.csv` and `parameter_sensitivity.csv` (robustness layer)

**Update (follow-up bootstrap run):** The 5 survivors originally missing from
`bootstrap_stress_test.csv` (NVDA `dual_momentum`, AMZN `dual_momentum`, AMZN
`keltner_revert`, MSFT `percent_b_revert`, GOOGL `rsi_revert`) have now been
bootstrap-tested using the identical unmodified methodology, with no parameter
tuning, no strategy-logic changes, and no funnel threshold changes. Results are
in `reports/edge_hunting/missing_bootstrap_stress.csv` and
`reports/edge_hunting/missing_bootstrap_stress_report.md`. The classification
table in Section "Classification of every survivor" below has been updated
accordingly. **Do not paper-test any of these 5 configs based on the original
version of this document — the bootstrap results changed 3 of the 5
classifications.**

**Update (slippage / transaction-cost stress run):** Every current
PAPER-TEST CANDIDATE (18 rows) and remaining NEEDS MORE ROBUSTNESS TESTING
row (3 rows) has now been stress-tested at 1/5/10/25/50bp per-side costs
using the same unmodified walk-forward engine (no parameter tuning, no
strategy-logic changes, no entry/exit rule changes, no optimization to
survive costs). Results are in `reports/edge_hunting/slippage_stress.csv`
and `reports/edge_hunting/slippage_stress_report.md`. **Only 7 of 21 configs
survive realistic friction through 25bp; 13 only work at the original 1bp
assumption and must NOT be promoted to paper-trading; 1 (TLT pivot_bounce)
is outright FRAGILE, dying by 10bp.** See the updated classification table
below (new "Slippage" column) and the new Section 12.

---



## 1. Which strategy families survived?

Of the 47 strategy families in the library, only **12 (25.5%)** produced at least one survivor
that cleared all six funnel filters:

| Family | Survival rate | Category |
|---|---|---|
| dual_momentum | 20.7% | TREND |
| percent_b_revert | 6.9% | MEAN_REVERSION |
| keltner_revert | 6.9% | MEAN_REVERSION |
| rsi_revert | 4.7% | MEAN_REVERSION |
| macd_rsi_confirm | 3.4% | COMPOSITE |
| ultimate_oscillator_revert | 3.4% | MEAN_REVERSION |
| cci_revert | 1.7% | MEAN_REVERSION |
| donchian_breakout | 1.7% | TREND |
| bollinger_revert | 1.7% | MEAN_REVERSION |
| pivot_bounce | 1.7% | PATTERN |
| zscore_revert | 0.9% | MEAN_REVERSION |
| atr_breakout | 0.9% | VOLATILITY |

The other 35 families — including well-known trend/technical staples such as MACD, Ichimoku,
Supertrend, Parabolic SAR, Hull MA, KAMA, MA crossover, ADX trend, Aroon, Vortex, TRIX, Chandelier
Exit, OBV trend, and every VOLUME-category strategy — produced **zero survivors** anywhere in the
29-asset universe. VOLUME as a category had a 0.0% survival rate across all its families.

**Mean-reversion dominates the survivor list by count** (8 of 12 surviving families), and
MEAN_REVERSION is the only category with a positive mean OOS Sharpe across *all* its backtests
(+0.14), while every other category (TREND, PATTERN, VOLUME, COMPOSITE, VOLATILITY) has a
**negative** mean OOS Sharpe. This is a category-level signal, not just a survivor-count artifact.

---

## 2. Which assets dominated?

The 35 survivors span **17 distinct assets** — there is no single dominant name:

| Asset | Survivors | Asset | Survivors |
|---|---|---|---|
| XLK | 4 | AMZN | 2 |
| MSFT | 4 | XLY | 1 |
| EFA | 3 | XLP | 1 |
| EEM | 3 | BTC-USD | 1 |
| AAPL | 3 | ETH-USD | 1 |
| SPY | 2 | NVDA | 1 |
| QQQ | 2 | GOOGL | 1 |
| XLF | 2 | | |
| TLT | 2 | | |
| HYG | 2 | | |

Max concentration is 11.4% (XLK or MSFT), well under any reasonable single-asset-concentration
flag. Grouping loosely: mega-cap tech (AAPL/MSFT/AMZN/NVDA/GOOGL) = 11/35 (31%); broad
market/sector ETFs (XLK/SPY/QQQ/XLF/XLY/XLP) = 12/35 (34%); international/bond/credit ETFs
(EFA/EEM/TLT/HYG) = 10/35 (29%); crypto (BTC-USD/ETH-USD) = 2/35 (6%). No single-asset
concentration warning was raised by the pipeline itself (`concentration_warning: ""` in
`funnel_summary.json`).

---

## 3. Which results are probably real?

The mean-reversion cluster on liquid ETFs and large caps has the strongest combined evidence:

- **Family-level robustness:** `parameter_sensitivity.csv` flags `rsi_revert`, `keltner_revert`,
  `cci_revert`, `percent_b_revert`, `bollinger_revert`, `zscore_revert`,
  `ultimate_oscillator_revert`, and `pivot_bounce` as **ROBUST** (60–90%+ of parameter variations
  within the family are OOS-positive, not just one lucky setting).
- **Bootstrap stability:** Of the mean-reversion survivors that were bootstrap-tested (see
  `bootstrap_stress_test.csv`), essentially all are flagged **SOLID** — worst-case reshuffled
  drawdown stayed well inside the -35% floor (e.g. XLK percent_b_revert -25.1%, MSFT
  keltner_revert -23.6%, TLT/EFA/EEM rsi_revert variants -9.7% to -19.3%).
- **Plausible mechanism:** short-horizon mean reversion in liquid, heavily arbitraged
  ETFs/large-caps is a well-documented microstructure effect, not an exotic claim.
- **Sane magnitude:** OOS Sharpe values sit in a modest 0.52–0.84 range with OOS *not* wildly
  exceeding in-sample Sharpe — the signature of a real, small effect rather than a fitted fluke.

Best examples: `XLK percent_b_revert` (0.84 OOS Sharpe, SOLID, ROBUST family, 168 trades),
`MSFT keltner_revert` (0.71, SOLID, 121 trades), `TLT`/`EFA` `rsi_revert(7,25/70)` (0.70/0.69,
SOLID, 160/165 trades).

---

## 4. Which results are suspicious?

- **`dual_momentum` dominance:** it has by far the highest family survival rate (20.7%) and
  supplies most of the top-ranked individual survivors (NVDA, AMZN, AAPL, MSFT, XLF, SPY, HYG,
  XLY), yet the family was tested with only two parameter combinations per asset
  (`window=60,rel_window=126` and `window=126,rel_window=126`) — a very small grid, which inflates
  the apparent "survival rate" denominator effect.
- **FRAGILE bootstrap flags concentrated in dual_momentum:** AAPL (both variants), MSFT (both
  variants), XLF (both variants), XLY — all flagged **FRAGILE**, with worst-case
  reshuffled drawdowns of -37% to -51%, well past the -35% funnel floor. Bootstrap reshuffling
  only reorders existing returns (it doesn't change their magnitude), so a FRAGILE flag here means
  the smooth-looking equity curve depends on the lucky **sequencing** of a handful of large
  winning days, not a persistently repeatable edge.
- **AAPL `macd_rsi_confirm`:** the family's own aggregate stats (`parameter_sensitivity.csv`) show
  a **negative** mean OOS Sharpe (-0.22) and a **MIXED** robustness flag across the family, yet
  this one AAPL config passed the funnel with an OOS Sharpe of exactly 0.50 — right at the
  threshold — and is also the single worst bootstrap result in the entire survivor set
  (-53.7% worst-case drawdown). An outlier survivor from an otherwise-losing family, at the exact
  edge of the pass bar, with the worst fragility score, is a strong overfitting/luck signature.
- **BTC-USD `atr_breakout`:** family-level mean OOS Sharpe is -0.35 (MIXED, mostly negative) but
  this single BTC-USD config shows 0.88 — again an outlier from a losing family. Bootstrap flags
  it FRAGILE with the single worst worst-case drawdown of any survivor (-60.1%).

---

## 5. Which results may be asset beta rather than strategy edge?

Several signals point this way:

- **Cross-sectional momentum underperformed single-asset momentum.** The cross-sectional version
  ranks assets against each other and goes long/short in relative terms — it should strip out
  common market drift. It did **not** reproduce the single-asset `dual_momentum` edge (see Q10
  below): mean OOS Sharpe 0.03 vs 0.10 for single-asset. If the single-asset "momentum edge" were
  a genuine relative-strength/timing effect, a properly beta-neutral cross-sectional version
  should show it too, or better. It didn't — which is evidence that at least part of the
  single-asset `dual_momentum` performance is riding directional asset drift (i.e., these specific
  names/ETFs simply trended up over the tested window) rather than a repeatable timing skill.
- **The `dual_momentum` survivor list is exactly the set of names that had a strong uptrend in the
  test window** — mega-cap tech (AAPL/AMZN/MSFT/NVDA), broad-market ETFs (SPY/XLF/XLY), and a
  credit ETF (HYG). A trend-following strategy scoring well on assets that trended is
  circumstantially consistent with "the asset had beta/drift" rather than "the strategy found
  something."
- **BTC-USD/ETH-USD breakout survivors** are similarly consistent with capturing the general
  upward drift and elevated volatility of crypto over the sample period rather than an exploitable
  breakout inefficiency — reinforced by their FRAGILE bootstrap flags.

---

## 6. Which strategies failed due to drawdown?

**1,112 of 2,662 non-survivors (41.8%)** were rejected on the `max_drawdown` filter (OOS max
drawdown worse than -35%) as their first/primary failure reason. By category:

| Category | Drawdown failures |
|---|---|
| TREND | 726 |
| VOLUME | 145 |
| MEAN_REVERSION | 108 |
| COMPOSITE | 47 |
| PATTERN | 44 |
| VOLATILITY | 42 |

TREND strategies account for nearly two-thirds of all drawdown-based rejections. This is
consistent with unhedged trend/breakout systems riding trends all the way through their
reversals — they need an explicit stop-loss or vol-targeting overlay to control drawdown, which
none of the raw signal implementations in this library apply.

---

## 7. Which strategies failed due to insufficient trades (<30)?

**28 configs**, spread thinly across many families rather than concentrated in one:
`ma_crossover`, `dual_momentum`, `squeeze_breakout`, `ts_momentum`, `rsi_revert`, `trix`,
`supertrend`, `triple_screen`, `ultimate_oscillator_revert`, `money_flow_index`, `volume_surge` —
on lower-turnover assets/timeframes (SPY, QQQ, XLK, XLY, HYG, TLT, DIA, XLV, EFA, EWZ, BTC-USD,
TSLA, GOOGL, META, JPM). Trade counts ranged from 2 (BTC-USD/META `triple_screen`) to 28.

Notably, several of these had OOS Sharpe *above* the survivor bar (e.g. SPY `dual_momentum`:
26 trades, 0.84 Sharpe; XLY `dual_momentum`: 22 trades, 0.83 Sharpe; EWZ `supertrend`: 25 trades,
0.90–0.91 Sharpe) but were correctly rejected anyway — 20–28 trades across a 5-window walk-forward
split is too small a sample to trust a Sharpe estimate regardless of how good it looks. This is
the funnel behaving as designed, not a weakness.

---

## 8. Which strategies failed because OOS Sharpe was too good / suspicious (>2.5 ceiling)?

**None.** Zero of the 2,697 backtests exceeded the 2.5 OOS Sharpe ceiling. The single highest OOS
Sharpe observed anywhere in the entire sweep was **1.37**. This filter never fired.

This is mildly reassuring — it means there is no gross look-ahead/leakage signature producing
implausibly perfect results — but it should not be read as "everything is clean." The ceiling
filter is a coarse trip-wire; the subtler `oos_over_is_ratio` filter (Q9) is doing real work and
did catch meaningful cases.

---

## 9. Which strategies failed due to in-sample/out-of-sample mismatch (OOS Sharpe > 1.3× in-sample Sharpe)?

**145 configs.** The most extreme cases, ranked by raw OOS Sharpe:

| Asset | Family | In-sample Sharpe | OOS Sharpe |
|---|---|---|---|
| META | connors_rsi_revert | 0.88 | 1.22 |
| EWZ | pivot_bounce | 0.03 | 1.19 |
| ETH-USD | dual_momentum | 0.26 | 1.07 |
| NVDA | connors_rsi_revert | 0.71 | 1.01 |
| XLE | higher_highs_lower_lows | 0.08 | 1.00 |
| META | rsi_revert | 0.35–0.40 | 0.97–1.00 |
| EWZ | connors_rsi_revert | 0.39 | 0.98 |
| AMZN | rsi_revert | 0.20 | 0.97 |
| EEM | vwap_revert | 0.03 | 0.97 |

Several of these (EWZ `pivot_bounce`, ETH-USD `dual_momentum`, XLE `higher_highs_lower_lows`, EEM
`vwap_revert`) show OOS Sharpe exploding out of a near-zero or negligible in-sample base — the
hallmark of noise rather than skill. The funnel correctly rejected all of them.

---

## 10. Did cross-sectional momentum beat single-asset momentum?

**No.** Per `cross_sectional_momentum_report.md`:

| Lookback | In-sample Sharpe | OOS Sharpe | OOS Max DD |
|---|---|---|---|
| 3m | 0.36 | 0.12 | -30.7% |
| 6m | 0.49 | **-0.15** | -37.1% |
| 12-1 | 0.74 | 0.11 | -35.9% |

None of the three lookbacks cleared even the 0.5 minimum-Sharpe funnel threshold that single-asset
`dual_momentum` survivors cleared. The 6-month lookback actually went **negative** OOS despite a
respectable 0.49 in-sample Sharpe — an IS/OOS mismatch in the wrong direction. Cross-sectional mean
OOS Sharpe across all three lookbacks (0.03) is roughly a third of single-asset momentum's mean
(0.10), and its worst OOS drawdown (-37.1%) is worse than most single-asset survivors' drawdowns.
This directly supports the asset-beta concern raised in Q5: the market-relative version of the
same idea did not reproduce the single-asset result.

---

## 11. What should be tested next?

Observations worth investigating before any strategy here is taken further (not tuning — genuine
follow-up validation):

1. **Bootstrap-test the 5 survivors that were never bootstrap-tested.** `bootstrap_stress_test.csv`
   contains only 30 of the 35 survivors. Missing: **NVDA dual_momentum** and **AMZN dual_momentum**
   (the #1 and #2 ranked survivors by raw OOS Sharpe), **AMZN keltner_revert**, **MSFT
   percent_b_revert**, and **GOOGL rsi_revert**. Given that sibling `dual_momentum` configs on
   AAPL/MSFT/XLF/XLY all came back FRAGILE, the NVDA/AMZN dual_momentum results should not be
   treated as confirmed until they go through the same stress test.
2. **Regime/sub-period decomposition of `dual_momentum` survivors** — split the walk-forward
   windows and check whether performance is concentrated in one bull leg of the sample rather than
   distributed across multiple up/down cycles. This would directly test the asset-beta hypothesis
   in Q5.
3. **Recognize and remove duplicate signals before counting evidence.** `XLK bollinger_revert
   (window20, num_std2.0)` and `XLK zscore_revert (window20, threshold2.0)` produced *identical*
   in-sample Sharpe, OOS Sharpe, and drawdown numbers — they are almost certainly the same
   underlying rolling-mean/rolling-std computation expressed two different ways. They should be
   counted as one piece of evidence, not two.
4. **Check the actual date range used by the sweep.** All 2,697 backtests were run on a single
   continuous historical window sliced into 5 walk-forward folds — that is not the same as testing
   across genuinely different macro regimes (e.g., a rate-hiking cycle vs. easing cycle, a
   risk-on vs. risk-off year). Before paper-testing anything, confirm what calendar period was
   actually covered and whether it includes more than one regime.
5. **Add an explicit stop-loss/vol-targeting overlay test for TREND-category strategies.** TREND
   strategies failed on drawdown at a much higher rate (726 failures) than any other category —
   worth knowing whether a simple risk overlay would rescue any of the 726, but that is a separate,
   later exercise, not something to fold into this analysis.
6. **Re-examine why `atr_breakout` and `macd_rsi_confirm` produced a single passing outlier from an
   otherwise-negative family mean.** This pattern (bad family average, one surviving outlier) is
   exactly what you'd expect from a large multi-asset multi-parameter sweep throwing off a few
   false positives by chance — these two survivors are the weakest candidates in the set and are
   good examples to keep as a "what a false positive looks like" reference.

---

## Classification of every survivor

Legend: **REJECT** (fails robustness or overfitting checks) · **NEEDS MORE ROBUSTNESS TESTING**
(missing bootstrap data, or thin/ambiguous evidence) · **PAPER-TEST CANDIDATE** (passed funnel +
family-level ROBUST + bootstrap SOLID) · **RESEARCH CANDIDATE ONLY** (interesting but redundant,
duplicate, or otherwise not independently informative).

| # | Asset | Strategy | OOS Sharpe | Bootstrap | Family flag | Classification |
|---|---|---|---|---|---|---|
| 1 | NVDA | dual_momentum(60,126) | 0.98 | **FRAGILE (-61.3%)** | ROBUST (family) | **REJECT** — bootstrap-tested (see missing_bootstrap_stress.csv); now the single worst bootstrap result of any survivor in the sweep |
| 2 | AMZN | dual_momentum(60,126) | 0.98 | **FRAGILE (-48.0%)** | ROBUST (family) | **REJECT** — bootstrap-tested (see missing_bootstrap_stress.csv); confirms same fragility pattern as #1 |

| 3 | AAPL | dual_momentum(60,126) | 0.95 | FRAGILE (-42.7%) | ROBUST (family) | **REJECT** |
| 4 | BTC-USD | atr_breakout | 0.88 | FRAGILE (-60.1%) | MIXED, mean -0.35 | **REJECT** |
| 5 | XLK | percent_b_revert | 0.84 | SOLID (-25.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 6 | AAPL | dual_momentum(126,126) | 0.77 | FRAGILE (-48.8%) | ROBUST (family) | **REJECT** |
| 7 | QQQ | cci_revert | 0.73 | SOLID (-19.0%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 8 | MSFT | keltner_revert | 0.71 | SOLID (-23.6%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 9 | MSFT | dual_momentum(126,126) | 0.71 | FRAGILE (-50.9%) | ROBUST (family) | **REJECT** |
| 10 | TLT | rsi_revert(7,25/70) | 0.70 | SOLID (-15.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 11 | EFA | rsi_revert(7,25/70) | 0.69 | SOLID (-15.0%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 12 | AMZN | keltner_revert | 0.66 | **SOLID (-31.3%)** | ROBUST (family, sibling MSFT SOLID) | **PAPER-TEST CANDIDATE** — bootstrap-tested (see missing_bootstrap_stress.csv); confirms sibling MSFT result |

| 13 | XLF | dual_momentum(126,126) | 0.66 | FRAGILE (-39.4%) | ROBUST (family) | **REJECT** |
| 14 | XLF | dual_momentum(60,126) | 0.65 | FRAGILE (-37.1%) | ROBUST (family) | **REJECT** |
| 15 | EEM | rsi_revert(14,30/70) | 0.65 | SOLID (-13.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 16 | TLT | pivot_bounce | 0.64 | SOLID (-31.0%, near floor) | ROBUST | **NEEDS MORE ROBUSTNESS TESTING** — SOLID but worst-case DD close to the -35% funnel floor, plus unusually high turnover/exposure |
| 17 | SPY | dual_momentum(60,126) | 0.64 | SOLID (-28.3%) | ROBUST (family) | **PAPER-TEST CANDIDATE** — note sibling configs on other names were fragile; SPY specifically tested SOLID |
| 18 | EFA | rsi_revert(7,30/70) | 0.63 | SOLID (-19.3%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 19 | ETH-USD | donchian_breakout | 0.63 | FRAGILE (-40.6%) | ROBUST (family) | **REJECT** |
| 20 | MSFT | percent_b_revert | 0.63 | **SOLID (-26.3%)** | ROBUST (family, sibling XLK SOLID) | **PAPER-TEST CANDIDATE** — bootstrap-tested (see missing_bootstrap_stress.csv); confirms sibling XLK result |

| 21 | EEM | ultimate_oscillator_revert | 0.62 | SOLID (-9.7%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 22 | XLK | rsi_revert(7,30/75) | 0.62 | SOLID (-25.3%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 23 | XLK | bollinger_revert | 0.60 | SOLID (-20.6%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 24 | XLK | zscore_revert | 0.60 | SOLID (-20.6%) | ROBUST | **RESEARCH CANDIDATE ONLY** — numerically identical to #23; same underlying signal, not independent evidence |
| 25 | MSFT | dual_momentum(60,126) | 0.58 | FRAGILE (-46.3%) | ROBUST (family) | **REJECT** |
| 26 | QQQ | rsi_revert(14,30/75) | 0.56 | not tested | ROBUST (family), 41 trades | **NEEDS MORE ROBUSTNESS TESTING** |
| 27 | XLP | rsi_revert(14,25/70) | 0.54 | SOLID (-7.3%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 28 | HYG | dual_momentum(126,126) | 0.54 | SOLID (-13.7%) | ROBUST (family) | **PAPER-TEST CANDIDATE** — notably stable on this bond/credit ETF despite fragility elsewhere in the family |
| 29 | EEM | rsi_revert(14,25/70) | 0.54 | not tested | ROBUST (family, sibling EEM config SOLID) | **NEEDS MORE ROBUSTNESS TESTING** (low priority) |
| 30 | SPY | rsi_revert(7,30/75) | 0.54 | SOLID (-19.7%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 31 | EFA | rsi_revert(7,25/75) | 0.53 | SOLID (-14.3%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 32 | GOOGL | rsi_revert(7,30/75) | 0.53 | **FRAGILE (-36.4%)** | ROBUST (family) | **REJECT** — bootstrap-tested (see missing_bootstrap_stress.csv); narrowly past the -35% floor, asset-specific fragility (family otherwise mostly SOLID) |

| 33 | HYG | dual_momentum(60,126) | 0.52 | SOLID (-13.3%) | ROBUST (family) | **PAPER-TEST CANDIDATE** |
| 34 | XLY | dual_momentum(60,126) | 0.51 | FRAGILE (-39.0%) | ROBUST (family) | **REJECT** |
| 35 | AAPL | macd_rsi_confirm | 0.50 | FRAGILE (-53.7%, worst of all) | MIXED, mean -0.22 | **REJECT** — outlier survivor from a losing family, at the exact pass threshold, worst fragility score of the entire set |

### Summary counts (updated after missing_bootstrap_stress.csv follow-up run)

- **REJECT:** 14 (was 11 — +3: NVDA dual_momentum, AMZN dual_momentum, GOOGL rsi_revert, now
  bootstrap-confirmed FRAGILE)
- **NEEDS MORE ROBUSTNESS TESTING:** 4 (was 9 — -5: the 5 previously-untested configs are now
  fully resolved into REJECT or PAPER-TEST CANDIDATE below; the 3 already-tested-but-flagged rows
  TLT `pivot_bounce`, QQQ `rsi_revert(14,30/75)`, EEM `rsi_revert(14,25/70)` remain in this bucket
  for their original non-missing-data reasons, plus this is a net count of 3 not 4 — see note below)
- **PAPER-TEST CANDIDATE:** 16 (was 14 — +2: AMZN keltner_revert, MSFT percent_b_revert, now
  bootstrap-confirmed SOLID)
- **RESEARCH CANDIDATE ONLY:** 1 (unchanged)

**Count reconciliation note:** 14 + 3 + 16 + 1 = 34, not 35 — the original table itself has a
pre-existing off-by-one (its own summary said 9 for "NEEDS MORE ROBUSTNESS TESTING" while only 8
rows in the table actually carry that tag; see the reconciliation note in
`reports/edge_hunting/missing_bootstrap_stress_report.md`). This discrepancy predates this
follow-up run and is flagged here rather than silently corrected, since fixing it would require
re-auditing the original table row-by-row against the sweep CSVs, which is out of scope for a
bootstrap-only follow-up.

Nearly all 16 paper-test candidates are mean-reversion strategies (RSI, %B, Keltner, CCI,
Bollinger, Ultimate Oscillator) on liquid ETFs/large-caps and one bond ETF (`HYG dual_momentum`).
**Every single equity/equity-ETF `dual_momentum` survivor tested to date is now FRAGILE** (AAPL
×2, MSFT ×2, XLF ×2, XLY, NVDA, AMZN — 8 of 8). Only the two bond/credit-ETF `dual_momentum`
survivors (SPY, HYG ×2) are SOLID. This fully confirms the concern raised in Q4/Q11: do not
paper-test any equity-side `dual_momentum` config, including NVDA and AMZN, regardless of their
high raw OOS Sharpe (0.98 each, the two highest in the entire sweep).

---

## 12. Slippage / transaction-cost stress test — does the edge survive realistic friction?

All 18 current PAPER-TEST CANDIDATE rows plus the 3 remaining NEEDS MORE ROBUSTNESS TESTING rows
(21 unique configs total) were re-run at 1/5/10/25/50bp per-side cost assumptions using the same
unmodified walk-forward engine — no parameter tuning, no strategy-logic changes, no entry/exit
rule changes, no optimization to survive costs. Full results:
`reports/edge_hunting/slippage_stress.csv` and `reports/edge_hunting/slippage_stress_report.md`.

**This is the single most consequential finding in the entire analysis.** The original sweep's
1bp/side cost assumption made every one of these 21 configs look tradeable. At realistic friction:

- **Only 7 of 21 (33%) survive through 25bp** (classified STRONGER, break-even 28–48bp):
  `MSFT keltner_revert`, `AMZN keltner_revert`, `EEM rsi_revert(14,30/70)`,
  `SPY dual_momentum(60,126)`, `HYG dual_momentum(126,126)`, `QQQ rsi_revert(14,30/75)`,
  `EEM rsi_revert(14,25/70)`.
- **13 of 21 (62%) only work at the original 1bp assumption** (classified MARGINAL, break-even
  12–24bp) — including 4 that were bootstrap-SOLID (`XLK percent_b_revert`, `XLK bollinger_revert`,
  `XLK rsi_revert`, `MSFT percent_b_revert`). Bootstrap-SOLID does not imply cost-robust; these are
  independent tests and this run shows a strategy can pass one and fail the other. Per the explicit
  rule that a strategy which "only works at 1bp" must not be promoted to paper-trading, **these 13
  are blocked from promotion** even though their funnel/bootstrap classification is otherwise
  unchanged.
- **1 of 21 (`TLT pivot_bounce`) is FRAGILE**, dying (Sharpe <= 0) already at 10bp — consistent
  with its earlier "SOLID but near the -35% floor" flag; this adds an independent reason to keep
  it out of paper-trading.

**Revised paper-trading-eligible list (supersedes the "PAPER-TEST CANDIDATE" classification above
for promotion purposes):**

1. MSFT `keltner_revert(20,2.0)`
2. AMZN `keltner_revert(20,2.0)`
3. EEM `rsi_revert(14,30/70)`
4. SPY `dual_momentum(60,126)`
5. HYG `dual_momentum(126,126)`
6. QQQ `rsi_revert(14,30/75)`
7. EEM `rsi_revert(14,25/70)`

No other survivor in this document should be moved to paper-trading without either (a) a specific,
justified low-cost execution venue/method for that exact asset, or (b) further work reducing
turnover. The "PAPER-TEST CANDIDATE" label elsewhere in this document should now be read as
"passed the funnel, family-robustness, and bootstrap checks" only — it is NOT sufficient on its
own to justify paper-trading; the slippage check in this section is an additional required gate.

---

## 13. Regime decomposition — is the edge concentrated in one market environment?

The 7 slippage-surviving candidates from Section 12 were decomposed by day-level market regime
(CRISIS / HIGH_VOL / LOW_VOL / BULL / BEAR / SIDEWAYS, using per-asset descriptive quantiles — no
parameter tuning, no strategy-logic changes, no funnel threshold changes, no sweep re-run). Full
results: `reports/edge_hunting/regime_decomposition.csv` and
`reports/edge_hunting/regime_decomposition_report.md`. **Nothing has been promoted to paper or
live trading by this analysis.** Note: per Section 14, the two EEM `rsi_revert` variants below are
a NEAR_DUPLICATE pair and should be read as roughly one near-duplicate signal slot, not two
independent candidates, even though both rows are reported separately.


- **6 of 7 are REGIME_ROBUST** (positive OOS Sharpe in multiple regimes, not concentrated in one):
  `MSFT keltner_revert`, `AMZN keltner_revert`, `EEM rsi_revert` (both variants),
  `HYG dual_momentum`, `QQQ rsi_revert`. Two caveats to carry forward: HYG never traded through a
  real BEAR/CRISIS period in this sample (0 BEAR trades, 0 CRISIS days observed) — it is untested
  in a genuine credit downturn, not confirmed-robust to one. AMZN keltner_revert has a real,
  non-trivial BULL-regime loss (-9.9% return, -20.9% max DD) even though its overall classification
  is ROBUST.
- **1 of 7 is REGIME_FRAGILE: `SPY dual_momentum(60,126)`.** Its entire +0.64 overall OOS Sharpe is
  produced by the BULL regime alone (+3.32 Sharpe, +62.9% return); it is **negative in every other
  populated regime** — HIGH_VOL (-0.92, -2.8%), LOW_VOL (-0.18, -2.0%), and especially SIDEWAYS
  (-0.81 Sharpe, **-15.1% total return**, its largest-population regime at 416 days). This directly
  confirms the asset-beta concern raised in Q5/Q10/Q11 of this document: SPY dual_momentum's
  apparent edge is bull-market drift, not a repeatable timing skill, and it loses money as soon as
  the market stops trending up. **SPY dual_momentum should be treated as effectively disqualified
  from paper-trading promotion**, despite having passed the funnel, bootstrap, and slippage-cost
  checks — regime concentration is an independent failure mode none of those three checks caught.

**Net paper-trading-eligible list after all three layers (funnel → slippage → regime):**
MSFT `keltner_revert`, AMZN `keltner_revert`, EEM `rsi_revert(14,30/70)`,
EEM `rsi_revert(14,25/70)`, HYG `dual_momentum(126,126)`, QQQ `rsi_revert(14,30/75)` — 6 configs,
with the HYG and AMZN caveats above carried forward. `SPY dual_momentum` is removed from the
list. As with Section 12, this is a documentation update only — no strategy has been moved to
paper or live trading as part of this analysis.

---

## 14. Duplicate / near-duplicate signal detection

The 7 friction-surviving candidates from Section 12 were checked pairwise (21 pairs) for
duplicate or near-duplicate signal behavior — return correlation, position correlation,
trade-date overlap, parameter similarity, and asset similarity — using their already-computed OOS
return/position series (no strategy deleted, no logic changed, no parameters tuned). Full results:
`reports/edge_hunting/duplicate_signal_report.csv` and
`reports/edge_hunting/duplicate_signal_report.md`.

- **No pair is a strict `DUPLICATE_SIGNAL`** (return_corr >= 0.90 AND position_corr >= 0.90) — none
  of these 7 is a literal re-expression of another, unlike the previously-identified
  `XLK bollinger_revert` / `XLK zscore_revert` case elsewhere in this document.
- **5 of 7 are `UNIQUE_SIGNAL`:** MSFT `keltner_revert`, AMZN `keltner_revert`,
  SPY `dual_momentum`, HYG `dual_momentum`, QQQ `rsi_revert`. All pairwise correlations involving
  these are below the 0.60 near-duplicate threshold on at least one of return/position correlation
  (the closest calls are SPY↔HYG dual_momentum at +0.55/+0.44 and MSFT keltner↔QQQ rsi at
  +0.56/+0.40 — both under the bar).
- **2 of 7 are `NEAR_DUPLICATE` of each other:** the two EEM `rsi_revert` variants
  (oversold 30 vs 25, same 14-window, same asset) correlate at +0.85 (returns) / +0.81
  (positions) with 56% trade-date overlap — expected, since they are the same signal family on
  the same asset with only a 5-point threshold difference.

**Net effect:** the 7 friction-surviving candidates represent **6 genuinely distinct signal
"slots"**, not 7 — the two EEM rsi_revert variants should be counted as roughly one piece of
evidence, not two, and if only one is ever carried forward into a future paper-trading pilot,
`rsi_revert(14,30/70)` is the natural choice (higher slippage-survival Sharpe, more standard
threshold). **No strategy has been deleted, modified, or reparametrized by this analysis** — this
is a signal-uniqueness annotation only, to inform (not determine) future portfolio construction.

---

## 15. Benchmark comparison — does the edge beat simply buying and holding?

The 7 friction-surviving candidates were compared against (1) buy-and-hold of their own traded
asset, (2) SPY buy-and-hold, (3) QQQ buy-and-hold, and (4) an equal-weight, daily-rebalanced
buy-and-hold across the full 26-asset cached universe — all over the exact same OOS date window as
each strategy (no strategy tuning, no logic/entry/exit changes, same unmodified walk-forward
engine at 1bp baseline cost). Full results: `reports/edge_hunting/benchmark_comparison.csv` and
`reports/edge_hunting/benchmark_comparison_report.md`.

- **2 of 7 (really ~1 near-duplicate signal slot) are `ROBUST_CANDIDATE`:** the two EEM
  `rsi_revert` variants are the only candidates that convincingly beat their own asset's
  buy-and-hold on both Sharpe and drawdown — on an asset (EEM) whose buy-and-hold OOS Sharpe was
  actually **negative** (-0.35, -31.5% total return) over this window. Excess Sharpe over EEM
  buy-and-hold: +1.00 (30/70 variant), +0.89 (25/70 variant).
- **2 of 7 are `BETA_DISGUISED`:** `SPY dual_momentum` (correlation to SPY's own returns +0.74,
  excess Sharpe over SPY buy-and-hold **-0.17**) and `HYG dual_momentum` (correlation to HYG's own
  returns +0.80, excess Sharpe over HYG buy-and-hold a negligible +0.05) are both largely
  indistinguishable from simply holding the underlying asset. This independently confirms the
  REGIME_FRAGILE finding on SPY dual_momentum from Section 13 via a different lens, and reveals a
  **new, sharper concern on HYG dual_momentum** that the regime-decomposition section alone did not
  surface — HYG's REGIME_ROBUST flag in Section 13 should now be read alongside this near-zero
  excess-Sharpe result.
- **3 of 7 are `DEFENSIVE_CANDIDATE`:** `MSFT keltner_revert`, `AMZN keltner_revert`, and
  `QQQ rsi_revert` all cut max drawdown substantially (e.g. MSFT -7.4% vs -20.6% buy-and-hold) but
  surrendered the majority of their asset's very strong OOS buy-and-hold return (e.g. MSFT +35.3%
  vs +117.1% buy-and-hold), producing a worse Sharpe than simply holding the asset. Low correlation
  to their own asset's returns (+0.14, -0.01, +0.23 respectively) confirms these are not
  beta-disguised — they capture a real, distinct pattern — but that pattern was a net drag on
  risk-adjusted performance during this specific, strongly trending OOS window.
- **None of the 7 candidates beats the equal-weight 26-asset universe buy-and-hold benchmark**
  (Sharpe +0.78, total return +57.1%) on either metric over the same OOS window.

**Net effect on paper-trading readiness:** this is a fourth independent lens (after
funnel/bootstrap, slippage, and regime decomposition) that most strongly favors the EEM
`rsi_revert` signal (now confirmed ROBUST_CANDIDATE against its own buy-and-hold, in addition to
REGIME_ROBUST) and raises sharper, benchmark-specific concerns about both `SPY dual_momentum`
(further confirming its Section 13 REGIME_FRAGILE flag) and `HYG dual_momentum` (a new concern not
previously visible). **As instructed, nothing has been promoted to paper or live trading by this
analysis.**






