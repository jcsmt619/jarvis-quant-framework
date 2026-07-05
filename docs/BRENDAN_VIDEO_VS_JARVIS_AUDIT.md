# Brendan Li "9,000 Strategies" Video vs. Jarvis Edge-Hunting Pipeline — Audit

**Status: ANALYSIS ONLY. No code was edited. No backtests were re-run. No
parameters were tuned. This document compares an external, secondhand,
unverified YouTube summary against Jarvis's existing, already-executed
edge-hunting pipeline and its already-produced results.**

## Sources read

- `private_research/youtube_ai_pathways/BRENDAN_9000_STRATEGIES_NOTES.md`
  (paraphrased notes on the video; gitignored, private, unpublished)
- `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` (Sections 1–15)
- `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
- `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md`
- `reports/edge_hunting/funnel_report.md` / `funnel_summary.json`
- `reports/edge_hunting/bootstrap_stress_test.csv`
- `reports/edge_hunting/slippage_stress_report.md`
- `reports/edge_hunting/regime_decomposition_report.md`
- `reports/edge_hunting/benchmark_comparison_report.md`
- Source code inspected for exact implementation details:
  `edge_hunting/funnel.py`, `edge_hunting/walk_forward.py`,
  `edge_hunting/robustness.py`, `edge_hunting/parameter_grid.py`,
  `edge_hunting/data_loader.py`, `edge_hunting/cross_sectional.py`,
  `edge_hunting/eem_expansion.py`, `core/hmm_engine.py`,
  `core/risk_manager.py`

## Critical caveat carried over from the source notes

Brendan Li's video is a single, secondhand YouTube summary promoting a paid
community, with no published methodology, no code, no dataset, and only
round, unverified numbers (9,000 backtests, 524/478 survivors, 44%
OOS-survival rate, 20/18-ticker generalization claims). Every comparison
below treats those numbers as **claims, not verified facts**. Where Jarvis's
own numbers are cited, they come from already-executed, already-documented
pipeline runs — not from this audit re-running anything.

---

## Classification table (18 methodology items)

| # | Item | Classification | Summary |
|---|---|---|---|
| 1 | Daily-bar scope | **MATCHES_JARVIS** | Both are explicitly daily-bar only, no intraday/futures/options |
| 2 | Asset universe | **PARTIALLY_MATCHES** | Similar composition (broad ETFs, sectors, macro, crypto, large caps) but Jarvis's minimum-history bar is far weaker than Brendan's stated ~10-year filter |
| 3 | 15-year data depth | **PARTIALLY_MATCHES** | Jarvis's fetch window is exactly 15 years (2010–2025) but the enforced minimum (`MIN_VALID_BARS=500`, ~2 years) doesn't guarantee any given asset actually has 15 years |
| 4 | Strategy families | **JARVIS_IS_STRONGER** | Jarvis has 47 explicitly coded families across 6 categories vs. Brendan's ~4 loosely-described groups |
| 5 | Parameter grids | **PARTIALLY_MATCHES** | Jarvis's grids are explicit and reproducible, but several (notably `dual_momentum`, 2 combos) are small enough to be flagged as a real weakness in Jarvis's own documentation |
| 6 | Walk-forward construction | **JARVIS_IS_STRONGER** | Jarvis has an explicit, deterministic 5-window 70/30 walk-forward engine; Brendan's description has no window/step/fold detail at all |
| 7 | Six-filter funnel | **JARVIS_IS_STRONGER** | Jarvis's 6 filters are fully named and implemented; Brendan names only 4 and admits 2 are unnamed in the transcript |
| 8 | OOS Sharpe threshold | **MATCHES_JARVIS** | Both use exactly 0.5 |
| 9 | Drawdown threshold | **MATCHES_JARVIS** | Both use exactly -35% |
| 10 | Minimum trade count | **PARTIALLY_MATCHES** | Jarvis uses a hard, explicit 30-trade floor; Brendan mentions the filter conceptually but never states its exact number |
| 11 | Overfitting filter | **PARTIALLY_MATCHES** | Jarvis has a quantitative OOS/IS ratio filter (1.3x) that Brendan's qualitative scatter-plot claim lacks, but neither corrects for the multiple-comparisons problem of testing thousands of configs, and Jarvis's existing `backtest/deflated_sharpe.py`/`backtest/cpcv.py` are not wired into this funnel |
| 12 | Bootstrap reshuffle count | **PARTIALLY_MATCHES** | Same core methodology (pure return-order reshuffling, not resampling) but Jarvis uses 200 reshuffles vs. Brendan's claimed 500 |
| 13 | Category survival analysis | **JARVIS_IS_STRONGER** | Jarvis publishes exact survival % by category AND by all 47 individual families; Brendan gives only a qualitative "mean reversion won" claim |
| 14 | Same-strategy-across-assets analysis | **PARTIALLY_MATCHES** | Jarvis did a rigorous version of this (`EEM_MEAN_REVERSION_EXPANSION_SPEC.md`) but only for the EEM signal specifically, not systematically for every surviving family across the full universe the way Brendan's 20-ticker/18-ticker claim implies |
| 15 | Cross-sectional momentum | **NEEDS_RESEARCH** | Both test it, but Jarvis's own rigorous result (cross-sectional underperformed single-asset momentum) directly contradicts Brendan's claim that cross-sectional "scored much better" — this divergence is unresolved |
| 16 | Risk-management/sizing layer | **PARTIALLY_MATCHES** | Jarvis's dedicated risk infrastructure (Kelly sizing, circuit breakers, leverage caps) is far more advanced than anything Brendan describes, but that infrastructure is not currently wired into the edge-hunting walk-forward validation that produced the paper-trading candidates |
| 17 | Uncorrelated signal layer | **JARVIS_IS_STRONGER** | Jarvis has a concrete, quantitative duplicate/near-duplicate signal-correlation detector already in use; Brendan only states the concept |
| 18 | Regime/HMM layer | **PARTIALLY_MATCHES** | Jarvis has a full look-ahead-safe Gaussian HMM engine, but the regime layer actually used to evaluate edge-hunting candidates (`edge_hunting/regime_decomposition.py`) is a simpler rule-based quantile classifier, not the HMM engine itself |

---

## Detailed findings per item

### 1. Daily-bar scope — MATCHES_JARVIS
Brendan's universe is explicitly daily-bar, "no intraday, no futures, no
options." `edge_hunting/data_loader.py::fetch_symbol` uses `yfinance`
`auto_adjust=True` daily OHLCV exclusively, with no intraday resampling
anywhere in the edge-hunting pipeline. Full match on scope.

- **File(s):** `edge_hunting/data_loader.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap)
- **Implementation risk:** N/A
- **Next action:** None required.

### 2. Asset universe — PARTIALLY_MATCHES
Brendan's universe: ~30 assets — broad index ETFs, all major sector ETFs,
commodity/macro (Gold, Oil, Bonds), crypto (BTC, ETH), large-cap single
names. Jarvis's `DEFAULT_UNIVERSE` (29 assets: SPY/QQQ/IWM/DIA, all 8 SPDR
sector ETFs, GLD/USO/TLT/HYG/EFA/EEM/EWZ, BTC-USD/ETH-USD, 8 large caps) is
compositionally almost identical. The gap: Brendan explicitly excluded
assets with <10 years of history (e.g. XLC); Jarvis's `MIN_VALID_BARS = 500`
(~2 years of daily bars) is a far weaker floor — an asset could enter the
sweep with only 2 years of history, materially less rigorous than Brendan's
stated bar.

- **File(s):** `edge_hunting/data_loader.py` (`MIN_VALID_BARS`)
- **Urgent:** No — no current survivor is known to fail a 10-year filter,
  but this hasn't been explicitly checked
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Low — raising `MIN_VALID_BARS` to represent
  ~10 years (~2,500 daily bars) would only shrink the universe, not change
  any strategy code
- **Next action:** Cross-check the 35 original survivors' actual asset
  history length against a 10-year (~2,500 bar) floor; confirm none of them
  is riding on a shorter history than assumed. Research task, not a code
  change.

### 3. 15-year data depth — PARTIALLY_MATCHES
Jarvis's `fetch_symbol` defaults to `start="2010-01-01", end="2025-01-01"` —
exactly a 15-year nominal window, a striking numeric match to the task's
framing. However, the *enforced* minimum (`MIN_VALID_BARS=500`, ~2 years) is
much shallower than the nominal window, so "15-year depth" is not actually
guaranteed for every asset in the universe — only assets that happen to have
data going back to 2010 get the full window; newer assets (e.g. IEMG,
INDA — see `EEM_MEAN_REVERSION_EXPANSION_SPEC.md` Section 1) get far less
and are still allowed in as long as they clear 500 bars.

- **File(s):** `edge_hunting/data_loader.py` (`fetch_symbol` defaults,
  `MIN_VALID_BARS`)
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Low
- **Next action:** Add an explicit per-asset "actual history length" field
  to sweep output (documentation/reporting change only) so future analyses
  can see which survivors have genuine 15-year depth vs. a shorter effective
  window, without changing the funnel itself.

### 4. Strategy families — JARVIS_IS_STRONGER
Brendan describes two dominant families (trend/momentum, mean reversion)
plus a loosely-grouped "volume/volatility/pattern" bucket reported only in
aggregate. Jarvis's `edge_hunting/parameter_grid.py` + `strategy_library.py`
implement 47 named, individually coded strategy families spanning 6
categories (TREND, MEAN_REVERSION, VOLUME, VOLATILITY, PATTERN, COMPOSITE),
each independently reported in `funnel_report.md`'s per-family survival
table. This is materially more granular than the source video's grouping.

- **File(s):** `edge_hunting/strategy_library.py`,
  `edge_hunting/parameter_grid.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap — Jarvis already exceeds)
- **Implementation risk:** N/A
- **Next action:** None required.

### 5. Parameter grids — PARTIALLY_MATCHES
Brendan gives no detail beyond "a range of parameter settings" per family.
Jarvis's `FAMILY_GRIDS` dict in `parameter_grid.py` is fully explicit and
reproducible (e.g. `rsi_revert`: window∈{7,14} × oversold∈{25,30} ×
overbought∈{70,75} = 8 combos). The gap is internal, already flagged by
Jarvis's own analysis: `dual_momentum` has only **2** parameter combinations
per asset (`window=60|126, rel_window=126`), which
`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` Section 4 explicitly calls out as
inflating that family's apparent 20.7% survival rate — a small-grid
denominator artifact, not evidence of exceptional dual-momentum performance.

- **File(s):** `edge_hunting/parameter_grid.py` (`FAMILY_GRIDS["dual_momentum"]`)
- **Urgent:** No — already documented as a known caveat, not silently missed
- **Changes strategy logic:** Would change results (more grid points → more
  configs tested) but not the strategy's underlying logic/formula
- **Changes validation only:** Yes
- **Implementation risk:** Medium — expanding the `dual_momentum` grid would
  require a full sweep re-run (out of scope for this audit) and could shift
  which specific parameter settings survive
- **Next action:** Flag as a follow-up research item: re-run the sweep (in a
  separate, explicitly-approved task) with a wider `dual_momentum` grid
  (e.g. adding `window=[20,40,90]`, `rel_window=[60,252]`) to test whether
  its high survival rate holds up with a denominator comparable to other
  families, or shrinks toward the pack.

### 6. Walk-forward construction — JARVIS_IS_STRONGER
Brendan's description: "train on old data, test on new data," with no
window sizes, step size, or fold count given. Jarvis's
`edge_hunting/walk_forward.py` is fully explicit: 5 sequential
non-overlapping windows, each split 70% in-sample / 30% out-of-sample, OOS
tails stitched into one combined series that is the primary score (the
in-sample portion of each window is discarded from the final metric). This
is already noted as more rigorous in the source notes themselves
(`BRENDAN_9000_STRATEGIES_NOTES.md` Section 4).

- **File(s):** `edge_hunting/walk_forward.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap)
- **Implementation risk:** N/A
- **Next action:** None required.

### 7. Six-filter funnel — JARVIS_IS_STRONGER (with one caveat)
Brendan names 4 filters explicitly (Sharpe > 0.5, max DD < -35%, IS/OOS
overfit ratio, min trade count) and admits the remaining 2 of "six" are not
individually named in the transcript. Jarvis's `edge_hunting/funnel.py`
fully implements and names all 6: `max_drawdown`, `min_oos_sharpe`,
`max_oos_sharpe` (a 2.5 ceiling that Brendan's source never mentions at
all), `oos_over_is_ratio`, `min_trade_count`, `positive_in_sample`. Jarvis's
funnel is a strict superset of what Brendan describes, adding both a
suspiciously-good ceiling filter and an explicit positive-in-sample
requirement neither present in the source.

- **File(s):** `edge_hunting/funnel.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap)
- **Implementation risk:** N/A
- **Next action:** None required. (Note for completeness: Section 8 of
  `JARVIS_EDGE_HUNTING_ANALYSIS.md` confirms the 2.5 ceiling filter never
  fired across all 2,697 backtests — reassuring but not proof of zero
  look-ahead risk elsewhere.)

### 8. Out-of-sample Sharpe threshold — MATCHES_JARVIS
Both use exactly **0.5** as the minimum acceptable OOS Sharpe
(`FunnelThresholds.min_oos_sharpe = 0.5`). Exact numeric convergence.

- **File(s):** `edge_hunting/funnel.py`
- **Urgent:** No
- **Next action:** None required — cited in the private notes as "informal
  convergent validation," not a reason to change either threshold.

### 9. Drawdown threshold — MATCHES_JARVIS
Both use exactly **-35%** as the OOS max-drawdown floor
(`FunnelThresholds.max_drawdown_floor = -0.35`). Exact numeric convergence.

- **File(s):** `edge_hunting/funnel.py`
- **Urgent:** No
- **Next action:** None required.

### 10. Minimum trade count — PARTIALLY_MATCHES
Jarvis's floor is an explicit, hard **30 trades**
(`FunnelThresholds.min_trade_count = 30`), and
`JARVIS_EDGE_HUNTING_ANALYSIS.md` Section 7 documents exactly how this
filter behaves (28 configs rejected, several with attractive Sharpe values
correctly rejected anyway for having only 20–28 trades). Brendan's source
mentions this filter conceptually ("ensures statistical viability") but
never states the exact trade-count number used, so the two cannot be
numerically compared — only conceptually.

- **File(s):** `edge_hunting/funnel.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A — nothing to change on Jarvis's side;
  the gap is in the source material's own specificity, not in Jarvis
- **Implementation risk:** N/A
- **Next action:** None required on Jarvis's side. Treat Brendan's
  unspecified number as unverifiable and do not attempt to match it exactly.

### 11. Overfitting filter — PARTIALLY_MATCHES
Brendan's overfitting evidence is a qualitative IS-vs-OOS scatter plot
claim ("only ~44% of in-sample winners stayed winners OOS") — no deflated
Sharpe ratio, no CPCV, no multiple-testing correction is described at this
stage. Jarvis's `oos_over_is_ratio` filter is quantitative (OOS Sharpe must
not exceed 1.3× in-sample Sharpe) and `JARVIS_EDGE_HUNTING_ANALYSIS.md`
Section 9 documents its real effect (145 configs rejected, several showing
OOS Sharpe exploding from a near-zero in-sample base — "the hallmark of
noise rather than skill"). This is a genuinely stronger, numeric filter than
Brendan's qualitative plot. **However**, neither Brendan's approach nor
Jarvis's funnel corrects for the multiple-comparisons problem inherent in
testing ~2,700 (Jarvis) or ~9,000 (Brendan, claimed) configurations
simultaneously — with that many trials, some number of "survivors" are
expected by pure chance even after every individual filter is applied.
Jarvis already has purpose-built tooling for exactly this
(`backtest/deflated_sharpe.py`, `backtest/cpcv.py`) elsewhere in the
codebase, but it is **not** currently wired into the `edge_hunting` funnel
or any of the 35 survivors' evaluation.

- **File(s):** `edge_hunting/funnel.py` (existing ratio filter, working as
  intended); `backtest/deflated_sharpe.py`, `backtest/cpcv.py` (exist,
  unused here)
- **Urgent:** Yes, in the sense that it is the single largest un-addressed
  statistical risk in the whole pipeline — 2,697 trials were run and only
  the "beat 0.5 Sharpe simple filter" bar was applied per-config, with no
  correction for how many configs were tried in aggregate
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Medium — applying a deflated Sharpe ratio
  correction after the fact (using the existing `backtest/deflated_sharpe.py`
  module, unmodified) to the 35 survivors would not change any strategy
  code, but could downgrade some or all of the current "PAPER-TEST
  CANDIDATE" classifications
- **Next action:** Recommend a dedicated follow-up task (not this audit,
  which is explicitly analysis-only): run the existing, unmodified
  `backtest/deflated_sharpe.py` against the 35 survivors, treating the
  total number of trials (2,697) as the multiple-testing correction input,
  and report whether any of the current 7 paper-trading-eligible candidates
  survive a deflated-Sharpe-adjusted threshold.

### 12. Bootstrap reshuffle count — PARTIALLY_MATCHES
Both approaches use the same core technique: reshuffle the *order* of
already-realized returns (not resample their values) to test sensitivity to
lucky sequencing. Brendan's source claims **500** reshuffles. Jarvis's
`edge_hunting/robustness.py::DEFAULT_N_RESHUFFLES = 200`. Same
methodology, less than half the reshuffle count. This is a real, checkable
quantitative gap (not a methodology gap).

- **File(s):** `edge_hunting/robustness.py` (`DEFAULT_N_RESHUFFLES`)
- **Urgent:** No — 200 reshuffles is already a reasonable sample for a
  percentile-based (p5/p50/p95) worst-case estimate; this is a
  precision/robustness improvement, not a correctness bug
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Low — increasing `DEFAULT_N_RESHUFFLES` to 500
  is a one-line constant change with no strategy-logic impact, but would
  require re-running `bootstrap_stress_test` for all previously-tested
  survivors to get updated percentile/worst-case numbers
- **Next action:** Low-priority follow-up: re-run the existing, unmodified
  bootstrap methodology at `n_reshuffles=500` for the current 7
  paper-trading-eligible candidates specifically, to confirm their
  SOLID/FRAGILE flags are stable at the higher reshuffle count Brendan's
  source claims to use. Not urgent given the deterministic seed already
  used (`seed=42`) makes the existing 200-reshuffle results reproducible
  and directionally informative.

### 13. Category survival analysis — JARVIS_IS_STRONGER
Brendan's source gives only a qualitative claim: mean reversion was the
only net-positive category on average; trend, momentum, volume, composite,
volatility, pattern were all net-negative on average. Jarvis's
`funnel_report.md` / `funnel_summary.json` publish exact numbers: survival
rate AND mean OOS Sharpe **per category** (MEAN_REVERSION 2.5%
survival / +0.14 mean Sharpe vs. every other category negative) **and per
individual family** (all 47, down to 0.0% for 35 of them). This is a much
more granular, falsifiable dataset than Brendan's aggregate claim.

- **File(s):** `edge_hunting/funnel.py` (produces the per-category/family
  stats), `reports/edge_hunting/funnel_report.md`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap — Jarvis already exceeds)
- **Implementation risk:** N/A
- **Next action:** None required.

### 14. Same-strategy-across-assets analysis — PARTIALLY_MATCHES
Brendan's claim: RSI mean reversion survived on 20 different tickers,
Keltner reversion on 18 — used as evidence the effect isn't asset-specific
luck (numbers unverified, from the original ~9,000-backtest universe).
Jarvis has performed a genuinely rigorous version of exactly this question,
but **only for the EEM `rsi_revert` signal specifically**
(`docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` /
`edge_hunting/eem_expansion.py`), testing generalization across a curated
13-asset emerging-market ETF universe. Per the private research notes
(`BRENDAN_9000_STRATEGIES_NOTES.md` Section 15), that test found RSI
reversion generalized across "9 of 13 EM assets tested" — a similarly
flavored, independently-derived result, but on a much smaller, purpose-built
universe than either Brendan's full 20-ticker claim or Jarvis's own 29-asset
main sweep. **The main sweep itself has never had this same
"how many distinct tickers does each surviving family generalize across"
question asked and answered systematically** — it currently only reports
per-family survival *rate* (count of surviving configs / total configs in
that family), not a distinct-asset count analogous to Brendan's "20
tickers" framing.

- **File(s):** `reports/edge_hunting/funnel_report.md` (would need a new
  "distinct assets per surviving family" column);
  `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md` /
  `edge_hunting/eem_expansion.py` (existing EEM-specific precedent)
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Low — this is a reporting/aggregation change
  over already-existing `sweep_results.csv` / `top_survivors.csv` data, not
  a new backtest
- **Next action:** Recommend a follow-up analysis task (not implementation)
  that groups the existing `sweep_results.csv` by family and counts
  distinct assets with a passing survivor, for every surviving family
  (`dual_momentum`, `rsi_revert`, `keltner_revert`, etc.), producing a
  direct, apples-to-apples counterpart to Brendan's "20 tickers / 18
  tickers" claim using Jarvis's own already-computed data — no new sweep
  required.

### 15. Cross-sectional momentum — NEEDS_RESEARCH
Both test the same idea. Brendan's claim: basic single-asset momentum
scored "near zero," while a cross-sectional (rank assets against each
other, long top / short bottom) version "scored much better." Jarvis's own
already-executed test (`edge_hunting/cross_sectional.py`, documented in
`JARVIS_EDGE_HUNTING_ANALYSIS.md` Section 10 /
`reports/edge_hunting/cross_sectional_momentum_report.md`) found the
**opposite**: cross-sectional momentum's mean OOS Sharpe (0.03 across three
lookbacks) was roughly a third of single-asset `dual_momentum`'s mean OOS
Sharpe (0.10), and none of the three cross-sectional lookbacks cleared even
the 0.5 minimum-Sharpe funnel bar that several single-asset survivors
cleared. This is a direct empirical contradiction between the two sources,
not a methodology gap — Jarvis's version is unambiguously more rigorous
(walk-forward OOS discipline, no-lookahead rebalancing per
`cross_sectional.py`'s own docstring), so the disagreement is not explained
by Jarvis's implementation being weaker. Plausible explanations include:
different universes, different lookback/rebalance parameters, or Brendan's
claim being anecdotal/unverified marketing content rather than a rigorous
result. This is exactly the kind of divergence the task asks to flag rather
than silently resolve.

- **File(s):** `edge_hunting/cross_sectional.py`,
  `reports/edge_hunting/cross_sectional_momentum_report.md`
- **Urgent:** No — this is a research question, not a defect; Jarvis's own
  result already stands on its own rigor regardless of Brendan's claim
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Low if pursued — testing additional
  lookback/rebalance-frequency combinations for cross-sectional momentum
  would only add more configs to an existing, working module
- **Next action:** Flag as an open research question rather than a gap to
  close: if a future task wants to pursue this, test a wider grid of
  rebalance frequencies and lookbacks in `cross_sectional.py` (which
  currently only tests 3m/6m/12-1 lookbacks at a fixed 21-day rebalance) to
  see whether the underperformance is parameter-specific or a genuine,
  robust finding that contradicts the video's claim. Do not treat Brendan's
  claim as evidence that Jarvis's cross-sectional implementation is wrong.

### 16. Risk-management/sizing layer — PARTIALLY_MATCHES
Brendan's source explicitly declines to give a concrete sizing algorithm —
"depends on the trader's own capital, risk tolerance, time horizon," no
Kelly formula or fixed-fractional rule described. Jarvis has substantially
more machinery: `utils/kelly_criterion.py`, `kelly_sizer.py`,
`core/capital_allocator.py`, and especially `core/risk_manager.py`, which
implements circuit breakers (daily/weekly/peak-drawdown hard stops with a
kill-switch lock file), full-Kelly sizing with concentration/leverage caps,
dynamic leverage rules, and a `validate_signal()` gate every order must
pass (ATR stop, spread/liquidity checks, duplicate-trade blocking,
exposure caps, correlation-based position reduction). This is categorically
more advanced than anything the source describes. **The gap is
architectural, not capability-based**: the edge-hunting walk-forward engine
(`edge_hunting/walk_forward.py` / `edge_hunting/backtest_engine.py`) that
produced the 35 survivors and the 7 current paper-trading-eligible
candidates does **not** route position sizing through `core/risk_manager.py`
or the Kelly sizers at all — the sweep uses its own simple position/cost
model (`compute_position`, `compute_returns` with a flat `cost_bps`
turnover charge), entirely independent of the live-trading risk stack.

- **File(s):** `edge_hunting/backtest_engine.py` (`compute_position`,
  `compute_returns`); `core/risk_manager.py`, `kelly_sizer.py`,
  `core/capital_allocator.py` (exist, not connected to edge_hunting)
- **Urgent:** Yes, before any paper-trading pilot is actually enabled — the
  candidate strategies in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md` have
  never been evaluated with Jarvis's own circuit breakers or Kelly sizing
  applied; their reported Sharpe/drawdown numbers are for a fixed-notional,
  simple-cost backtest only, not what would actually happen once
  `risk_manager.py`'s caps and vetoes are layered on top in live/paper
  execution
- **Changes strategy logic:** No — the entry/exit signal logic would be
  identical; only position-sizing/veto behavior would change
- **Changes validation only:** Yes, but it is validation that materially
  affects whether reported Sharpe/drawdown numbers are representative of
  what paper trading would actually produce
- **Implementation risk:** Medium — integrating `risk_manager.py`'s
  `validate_signal()` and Kelly sizing into the edge-hunting walk-forward
  path (or into a pre-paper-trading gate) is a real engineering task with
  behavioral consequences (it could reject or resize trades the current
  backtest assumed), not a documentation-only change
- **Next action:** Before enabling any paper-trading pilot for the 7
  currently-eligible candidates, run their existing OOS signal series
  through `core/risk_manager.py`'s `validate_signal()` gate and Kelly sizer
  (as a separate, explicitly-scoped follow-up task) to see whether the
  approved candidates survive with realistic sizing/veto behavior applied,
  before any capital-adjacent decision is made. This is a recommendation
  only — not something this audit implements.

### 17. Uncorrelated signal layer — JARVIS_IS_STRONGER
Brendan's source states the concept ("combine with other, uncorrelated
signals") with no implementation. Jarvis has a concrete, already-used tool:
`edge_hunting/duplicate_signal_detection.py`, which computes pairwise
return correlation, position correlation, and trade-date overlap between
candidate signals, and was used in `JARVIS_EDGE_HUNTING_ANALYSIS.md`
Section 14 to correctly identify the two EEM `rsi_revert` variants as
NEAR_DUPLICATE (56% trade-day overlap) and collapse them into "one
near-duplicate signal slot" for portfolio-construction purposes. This is
exactly the kind of quantitative signal-uniqueness check Brendan's source
only gestures at conceptually.

- **File(s):** `edge_hunting/duplicate_signal_detection.py`
- **Urgent:** No
- **Changes strategy logic:** No
- **Changes validation only:** N/A (no gap — Jarvis already exceeds)
- **Implementation risk:** N/A
- **Next action:** None required for the layer itself. (Note: this layer
  answers "are two candidate signals duplicates of each other" — it is a
  different question from "does the risk-sizing layer combine multiple
  approved signals into one portfolio," which is Item 16's integration gap,
  not this item's.)

### 18. Regime/HMM layer — PARTIALLY_MATCHES
Brendan's source proposes a conceptual stack: base signal → risk sizing →
combine uncorrelated signals → regime detection on top via an HMM
classifying bear/trending/choppy/bull, applying momentum in
trending/bull regimes and mean reversion in choppy/ranging regimes — no
implementation detail given. Jarvis has a genuinely sophisticated, already
look-ahead-tested HMM engine (`core/hmm_engine.py`: Gaussian HMM with
automatic `n_components` selection via BIC over {3,4,5,6,7}, forward
algorithm only — never Viterbi — so filtered state estimates never revise
using future data, verified by `tests/test_look_ahead.py`) plus
`core/regime_strategies.py` for regime-conditional strategy selection. This
is architecturally more advanced than anything the source describes.
**However**, the regime layer actually used to evaluate the 7 paper-trading
candidates in Sections 13 of `JARVIS_EDGE_HUNTING_ANALYSIS.md` and
`reports/edge_hunting/regime_decomposition_report.md` is
`edge_hunting/regime_decomposition.py` — a simple, rule-based, priority-
ordered quantile classifier (CRISIS = drawdown ≤ -20%; HIGH_VOL/LOW_VOL =
top/bottom quartile of 60-day realized vol; BULL/BEAR = trailing 60-day
return thresholds; else SIDEWAYS), **not** the HMM engine at all. The two
regime-detection systems (`core/hmm_engine.py` and
`edge_hunting/regime_decomposition.py`) are independent implementations
answering a similar question with different methods, and the more
sophisticated one was not used for the edge-hunting candidate evaluation
that actually shaped the current paper-trading recommendations.

- **File(s):** `core/hmm_engine.py` (unused here),
  `edge_hunting/regime_decomposition.py` (actually used)
- **Urgent:** No — the rule-based classifier is transparent, deterministic,
  and not obviously wrong; it may be an intentional simplicity choice for
  a diagnostic-only research layer, not a defect
- **Changes strategy logic:** No
- **Changes validation only:** Yes
- **Implementation risk:** Medium if pursued — re-running the regime
  decomposition using `core/hmm_engine.py`'s filtered states instead of the
  quantile rules could change which regime each historical day is assigned
  to, which could change the "does this candidate collapse in BEAR/CRISIS"
  verdicts currently underpinning the paper-trading classifications (e.g.
  `SPY dual_momentum`'s REGIME_FRAGILE / BLOCKED status)
- **Next action:** Recommend, as a separate future research task (not this
  audit), re-running the existing regime decomposition for the current 7
  candidates using `core/hmm_engine.py`'s filtered regime states instead of
  the quantile-rule classifier, to check whether the two methods agree on
  which candidates are regime-robust vs. regime-fragile. If they diverge,
  that would be a materially important finding for the paper-trading
  candidate list; if they agree, it strengthens confidence in the existing
  conclusions without requiring any code change.

---

## Summary

**No capability gap was found that Brendan's video describes and Jarvis
lacks entirely.** Every one of the 18 methodology items has *some* Jarvis
implementation, and on the majority of items (8 of 18: items 4, 6, 7, 13,
17, plus exact numeric matches on items 8–9) Jarvis's implementation is
more rigorous, more granular, or more explicit than the secondhand video
description. This corroborates the private research note's own conclusion
(`BRENDAN_9000_STRATEGIES_NOTES.md`, "No capability gap identified").

**The real findings of this audit are internal integration and rigor
gaps, not missing capabilities:**

1. **Multiple-comparisons / deflated-Sharpe correction is not applied**
   to the 2,697-backtest sweep despite the tooling existing elsewhere in
   the repo (`backtest/deflated_sharpe.py`, `backtest/cpcv.py`) — Item 11,
   flagged urgent.
2. **The risk-management/sizing layer is not connected to the edge-hunting
   pipeline** that produced the current paper-trading candidates — Item 16,
   flagged urgent, directly relevant before any paper-trading pilot is
   enabled.
3. **The sophisticated HMM regime engine is not the regime layer actually
   used** to evaluate paper-trading candidates; a simpler quantile-rule
   classifier was used instead — Item 18, medium priority.
4. **Cross-sectional momentum results diverge between the two sources** —
   Item 15, an open research question, not a defect in either.
5. Several smaller, lower-priority quantitative gaps (bootstrap reshuffle
   count 200 vs. 500 claimed; minimum-history filter weaker than Brendan's
   stated 10-year bar; `dual_momentum`'s thin 2-combo parameter grid) are
   already partly self-documented in Jarvis's own analysis and are
   candidates for future, separately-scoped follow-up tasks.

**Nothing in this audit changes any strategy logic, re-runs any backtest,
or moves any candidate's classification.** All "next action" items above
are recommendations for separately-approved future work, consistent with
the task's explicit instruction not to implement anything here.
