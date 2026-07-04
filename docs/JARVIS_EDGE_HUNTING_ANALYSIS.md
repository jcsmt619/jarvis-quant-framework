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
| 1 | NVDA | dual_momentum(60,126) | 0.98 | not tested | ROBUST (family) | **NEEDS MORE ROBUSTNESS TESTING** — sibling configs on other names came back FRAGILE |
| 2 | AMZN | dual_momentum(60,126) | 0.98 | not tested | ROBUST (family) | **NEEDS MORE ROBUSTNESS TESTING** — same concern as #1 |
| 3 | AAPL | dual_momentum(60,126) | 0.95 | FRAGILE (-42.7%) | ROBUST (family) | **REJECT** |
| 4 | BTC-USD | atr_breakout | 0.88 | FRAGILE (-60.1%) | MIXED, mean -0.35 | **REJECT** |
| 5 | XLK | percent_b_revert | 0.84 | SOLID (-25.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 6 | AAPL | dual_momentum(126,126) | 0.77 | FRAGILE (-48.8%) | ROBUST (family) | **REJECT** |
| 7 | QQQ | cci_revert | 0.73 | SOLID (-19.0%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 8 | MSFT | keltner_revert | 0.71 | SOLID (-23.6%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 9 | MSFT | dual_momentum(126,126) | 0.71 | FRAGILE (-50.9%) | ROBUST (family) | **REJECT** |
| 10 | TLT | rsi_revert(7,25/70) | 0.70 | SOLID (-15.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 11 | EFA | rsi_revert(7,25/70) | 0.69 | SOLID (-15.0%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 12 | AMZN | keltner_revert | 0.66 | not tested | ROBUST (family, sibling MSFT SOLID) | **NEEDS MORE ROBUSTNESS TESTING** |
| 13 | XLF | dual_momentum(126,126) | 0.66 | FRAGILE (-39.4%) | ROBUST (family) | **REJECT** |
| 14 | XLF | dual_momentum(60,126) | 0.65 | FRAGILE (-37.1%) | ROBUST (family) | **REJECT** |
| 15 | EEM | rsi_revert(14,30/70) | 0.65 | SOLID (-13.1%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 16 | TLT | pivot_bounce | 0.64 | SOLID (-31.0%, near floor) | ROBUST | **NEEDS MORE ROBUSTNESS TESTING** — SOLID but worst-case DD close to the -35% funnel floor, plus unusually high turnover/exposure |
| 17 | SPY | dual_momentum(60,126) | 0.64 | SOLID (-28.3%) | ROBUST (family) | **PAPER-TEST CANDIDATE** — note sibling configs on other names were fragile; SPY specifically tested SOLID |
| 18 | EFA | rsi_revert(7,30/70) | 0.63 | SOLID (-19.3%) | ROBUST | **PAPER-TEST CANDIDATE** |
| 19 | ETH-USD | donchian_breakout | 0.63 | FRAGILE (-40.6%) | ROBUST (family) | **REJECT** |
| 20 | MSFT | percent_b_revert | 0.63 | not tested | ROBUST (family, sibling XLK SOLID) | **NEEDS MORE ROBUSTNESS TESTING** |
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
| 32 | GOOGL | rsi_revert(7,30/75) | 0.53 | not tested | ROBUST (family) | **NEEDS MORE ROBUSTNESS TESTING** |
| 33 | HYG | dual_momentum(60,126) | 0.52 | SOLID (-13.3%) | ROBUST (family) | **PAPER-TEST CANDIDATE** |
| 34 | XLY | dual_momentum(60,126) | 0.51 | FRAGILE (-39.0%) | ROBUST (family) | **REJECT** |
| 35 | AAPL | macd_rsi_confirm | 0.50 | FRAGILE (-53.7%, worst of all) | MIXED, mean -0.22 | **REJECT** — outlier survivor from a losing family, at the exact pass threshold, worst fragility score of the entire set |

### Summary counts

- **REJECT:** 11
- **NEEDS MORE ROBUSTNESS TESTING:** 9
- **PAPER-TEST CANDIDATE:** 14
- **RESEARCH CANDIDATE ONLY:** 1

Nearly all 14 paper-test candidates are mean-reversion strategies (RSI, %B, Keltner, CCI,
Bollinger, Ultimate Oscillator) on liquid ETFs/large-caps and one bond ETF (`HYG dual_momentum`).
No `dual_momentum` survivor on an equity/equity-ETF underlying survived both the bootstrap test
and the family-outlier check without being flagged FRAGILE — the entire equity-side `dual_momentum`
cluster (AAPL, MSFT, XLF, XLY, plus the two untested NVDA/AMZN configs) should be treated as
unconfirmed at best, rejected at worst, pending the missing bootstrap runs and regime
decomposition described in Q11.
