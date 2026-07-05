# EEM Mean-Reversion Expansion Spec

**Status: SPEC ONLY. NOT APPROVED. NOT IMPLEMENTED.**

This document designs a research test. It does not implement it, does not
run it, does not touch strategy code, does not tune any parameters, and
does not change the classification of any existing candidate. Nothing in
this document authorizes paper trading, live trading, or capital
deployment. Implementation begins only after explicit human approval of
this spec.

## 0. Why this test exists

Two current candidates exist because we found a signal on exactly one
asset (EEM) with exactly one strategy family (`rsi_revert`) at two
adjacent parameter settings:

- **Primary**: EEM `rsi_revert(14, 30/70)` — `APPROVED_FOR_PAPER_TEST`
  (unchanged by this spec, and this document does not alter that
  classification anywhere).
- **Conditional backup**: EEM `rsi_revert(14, 25/70)` —
  `BACKUP_PENDING_BOOTSTRAP` (unchanged by this spec, still blocked
  pending its own bootstrap stress test, as already documented in
  `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`).

A signal found on one asset, in one strategy family, at one narrow
parameter neighborhood is exactly the profile of a **potential one-asset
statistical artifact** — it could equally be:

(a) a real, structural mean-reversion property of emerging-market
liquidity/flow dynamics that should generalize across the EM ETF
universe, or

(b) a coincidence of this specific 1,134-day OOS sample on this specific
ticker's specific price history, dressed up by RSI's particular smoothing
of that history, that will not replicate anywhere else.

This spec defines a systematic, pre-registered test to tell (a) from (b)
**before** any further capital-adjacent decision is made about the EEM
signal — including before the conditional backup is even bootstrap-tested,
since if the whole family turns out to be an artifact, that would also
change how much weight to put on the backup's eventual bootstrap result.

---

## 1. Exact asset universe

All assets are tested via the existing `edge_hunting/data_loader.py`
(`yfinance`, `auto_adjust=True`, `MIN_VALID_BARS=500`). No new data source
is introduced.

| Ticker | Name | Category | Data-risk note |
|---|---|---|---|
| EEM | iShares MSCI Emerging Markets ETF | Broad EM (control/reference — this is the original signal asset) | None; already cached |
| VWO | Vanguard FTSE Emerging Markets ETF | Broad EM | None expected |
| IEMG | iShares Core MSCI Emerging Markets ETF | Broad EM | Inception 2012 — shorter history than EEM; confirm >= `MIN_VALID_BARS` before use |
| EWZ | iShares MSCI Brazil ETF | Single-country EM | None expected |
| FXI | iShares China Large-Cap ETF | Single-country EM (China) | None expected |
| INDA | iShares MSCI India ETF | Single-country EM | Inception 2012 — confirm sufficient history |
| EWT | iShares MSCI Taiwan ETF | Single-country EM | None expected |
| EWY | iShares MSCI South Korea ETF | Single-country EM | None expected |
| EWW | iShares MSCI Mexico ETF | Single-country EM | None expected |
| EZA | iShares MSCI South Africa ETF | Single-country EM | Lower liquidity than others — flag if avg volume is materially thinner |
| EIDO | iShares MSCI Indonesia ETF | Single-country EM | Inception 2010 — confirm sufficient history; lower liquidity |
| TUR | iShares MSCI Turkey ETF | Single-country EM | High historical volatility regime (currency crises); expect noisier regime decomposition |
| ILF | iShares Latin America 40 ETF | Regional EM | None expected |
| RSX | VanEck Russia ETF | Single-country EM | **CONDITIONAL — see below** |

### 1.1 RSX handling (explicit, per instruction)

RSX was effectively halted and later delisted/liquidated following the
2022 Russia sanctions regime; its post-February-2022 price data does not
reflect a tradeable, liquid market and its fund was ultimately closed.
Rules for this asset:

1. Attempt to fetch RSX through the existing `data_loader.fetch_symbol`
   exactly as with every other ticker — no special-casing of the fetch
   mechanism itself.
2. If data exists but the effective end date is on or before ~March 2022
   (delisting/halt), or if `MIN_VALID_BARS` is not met using only the
   pre-halt window, RSX is **excluded from this test** and reported as
   `EXCLUDED_DELISTED_INSUFFICIENT_DATA` in the final summary — not
   silently dropped, not silently included with stale post-halt data
   treated as real prices.
3. RSX must **never** be included in any walk-forward window that spans
   the halt/delisting event, since a multi-year price freeze (or a single
   enormous repricing gap) would contaminate return, volatility, and
   regime-label calculations for every strategy tested on it. If a clean
   pre-halt-only window exists and satisfies `MIN_VALID_BARS`, it may be
   used ONLY for that pre-halt window, clearly labeled as a truncated,
   non-representative sample, and excluded from every aggregate
   "generalizes across the universe" pass/fail decision in Section 6 —
   it may only appear as a supplementary, individually-labeled data point.
4. If RSX cannot satisfy any of the above cleanly, it is dropped entirely
   and documented as dropped, with the reason given. Under no
   circumstances is RSX data patched, interpolated across the halt gap, or
   forward-filled to manufacture a longer sample.

### 1.2 Minimum data bar for all other assets

Before running any strategy, every asset in the universe (RSX excluded per
1.1) must independently satisfy the existing `MIN_VALID_BARS = 500`
threshold already enforced by `data_loader.fetch_symbol`. Any asset that
fails this bar is excluded and listed by name in the final report — not
silently omitted.

---

## 2. Exact strategy families

All seven families below **already exist, unmodified**, in
`edge_hunting/strategy_library.py` / `STRATEGY_REGISTRY`. No new indicator
or strategy code is written for this test — that is a deliberate design
choice to guarantee this test cannot introduce a fresh source of look-ahead
bias or logic bugs; it only re-applies existing, already-vetted machinery
to a wider universe.

| Family (registry key) | Function | Category |
|---|---|---|
| `rsi_revert` | `strategy_rsi_revert` | MEAN_REVERSION |
| `percent_b_revert` | `strategy_percent_b_revert` | MEAN_REVERSION |
| `bollinger_revert` | `strategy_bollinger_revert` | MEAN_REVERSION |
| `keltner_revert` | `strategy_keltner_revert` | MEAN_REVERSION |
| `zscore_revert` | `strategy_zscore_revert` | MEAN_REVERSION |
| `cci_revert` | `strategy_cci_revert` | MEAN_REVERSION |
| `williams_r_revert` | `strategy_williams_r_revert` | MEAN_REVERSION |

No trend, volume, volatility, pattern, or composite families are included
— this test is deliberately scoped to mean-reversion only, since that is
the category of the original EEM finding, and mixing in unrelated families
would dilute the "does mean-reversion generalize on EM assets" question
this test is designed to answer.

---

## 3. Parameter grids

Two grid tiers are defined per family: (a) a **center grid** built around
the exact parameter values that produced the original EEM signal
(parameter-neighborhood analysis, Section 3.1), and (b) a **standard grid**
using the same values already defined in
`edge_hunting/parameter_grid.py::FAMILY_GRIDS` for cross-sectional coverage
(Section 3.2). Both tiers use only values already present in the existing
codebase or trivial, symmetric extensions of them — no new arbitrary
constants are invented for this test.

### 3.1 Center grid — parameter-neighborhood analysis around the winning EEM RSI settings

The original EEM finding used `rsi_revert(window=14, oversold=30,
overbought=70)`. This grid tests immediate neighbors on all sides to
determine whether the signal is a broad ridge (robust) or an isolated peak
(curve-fit artifact):

| Param | Winning value | Neighborhood tested |
|---|---|---|
| `window` | 14 | 7, 10, 14, 18, 21 |
| `oversold` | 30 | 20, 25, 30, 35 |
| `overbought` | 70 | 65, 70, 75, 80 |

This produces 5 × 4 × 4 = 80 `rsi_revert` configs per asset, applied ONLY
to `rsi_revert` (the family with an actual "winning setting" to build a
neighborhood around). This directly implements the required
"parameter-neighborhood analysis around the winning EEM RSI settings."

### 3.2 Standard grid — the other six mean-reversion families

For `percent_b_revert`, `bollinger_revert`, `keltner_revert`,
`zscore_revert`, `cci_revert`, and `williams_r_revert`, use the existing,
unmodified grids already defined in
`edge_hunting/parameter_grid.py::FAMILY_GRIDS`:

```
percent_b_revert:   window=[20],            lower=[0.05],  upper=[0.95]
bollinger_revert:   window=[20],            num_std=[2.0, 2.5]
keltner_revert:     window=[20],            atr_mult=[2.0]
zscore_revert:      window=[20, 60],        threshold=[1.5, 2.0]
cci_revert:         window=[20],            threshold=[100, 150]
williams_r_revert:  window=[14],            oversold=[-80], overbought=[-20]
```

These are reused verbatim (no new values) to keep this expansion
consistent with every other family already validated elsewhere in this
codebase, and to avoid the appearance of hand-picking new parameter values
that might bias the outcome toward or away from a desired conclusion.

### 3.3 Total scale

- 13 assets (RSX handled per Section 1.1, excluded from the main grid) × 80
  `rsi_revert` center-grid configs = 1,040 backtests
- 13 assets × (1 + 2 + 1 + 4 + 2 + 1) = 13 assets × 11 standard-grid configs
  across the other 6 families = 143 backtests
- **Total: ~1,183 walk-forward backtests** (each backtest = one full 5-window
  walk-forward run per `edge_hunting/walk_forward.py`, unchanged).

This is a large but bounded sweep, consistent in scale with the existing
sweep infrastructure (`edge_hunting/run_sweep.py` already runs
hundreds-to-thousands of configs).

---

## 4. Data requirements

1. All data sourced through `edge_hunting/data_loader.py::fetch_symbol` /
   `load_universe`, unmodified — `yfinance`, `auto_adjust=True`,
   `MIN_VALID_BARS=500`, parquet cache under
   `data/raw/edge_hunting_cache/`.
2. Date range: use the same default range as the existing sweep
   (`start="2010-01-01"`, `end="2025-01-01"`) for consistency with the
   original EEM result and every other candidate already validated in this
   project, UNLESS an asset's inception date is later (e.g. IEMG, INDA,
   EIDO — see Section 1), in which case that asset's window naturally
   starts later and its resulting shorter walk-forward history is reported
   as such, not padded or backfilled.
3. Before running any strategy, log actual bar count, actual start/end
   date, and pass/fail on `MIN_VALID_BARS` for every asset in the universe,
   for full auditability of exactly what data each result is based on.
4. No survivorship-bias correction is attempted or claimed — these are all
   currently-listed, currently-tradeable ETFs (RSX excluded), and the
   report must say so explicitly: this test cannot speak to EM ETFs that
   were delisted or merged away before today for reasons other than the
   RSX-style geopolitical halt (e.g. a fund that simply failed to gather
   assets and was closed) — that is a known, disclosed limitation, not
   something this test claims to solve.

---

## 5. Validation gates

Every surviving config must pass through the **exact same validation
pipeline already used** for every other candidate in this codebase — no
new methodology, no new thresholds, no relaxed or tightened bars relative
to prior work:

1. **Six-filter funnel** — `edge_hunting/funnel.py::evaluate_funnel`,
   unmodified thresholds (`FunnelThresholds` defaults: DD floor -35%, min
   OOS Sharpe 0.5, max OOS Sharpe 2.5, max OOS/IS ratio 1.30x, min 30
   trades, positive in-sample Sharpe required).
2. **Walk-forward OOS methodology** — `edge_hunting/walk_forward.py`,
   unmodified (5 windows, 70/30 in-sample/OOS split per window, OOS tails
   stitched into one combined series, no shuffling, no negative shifts).
3. **Bootstrap stress test** — `edge_hunting/robustness.py::
   bootstrap_stress_test`, unmodified (200 reshuffles, seed=42, reorder-
   only of OOS daily returns, SOLID/FRAGILE at the -35% worst-case-drawdown
   threshold).
4. **Slippage stress at 1/5/10/25/50bp** — same cost levels and same
   STRONGER / MARGINAL / FRAGILE / DOES_NOT_WORK_EVEN_AT_1BP classification
   logic already implemented in `edge_hunting/slippage_stress.py`
   (`COST_LEVELS_BPS = [1.0, 5.0, 10.0, 25.0, 50.0]`), applied via the same
   `run_walk_forward` calls at each cost level.
5. **Benchmark comparison** — against (a) the traded asset's own
   buy-and-hold, (b) SPY buy-and-hold, (c) QQQ buy-and-hold, and (d) the
   equal-weight universe buy-and-hold, using
   `edge_hunting/benchmark_comparison.py`'s existing methodology
   (`_buy_hold_metrics`, `_equal_weight_universe_returns`,
   `_beta_warning`, `_classify` — all unmodified). Note: for this test, the
   "equal-weight universe" benchmark should be computed twice and reported
   separately — once using the existing default cross-asset universe
   (`data_loader.DEFAULT_UNIVERSE`), and once using an equal weight of
   **only the 13 EM assets tested here** — so a result can be distinguished
   from "beats a global 27-asset basket" versus "beats simply owning a
   basket of EM ETFs," which is the more relevant comparison for an
   EM-specific mean-reversion claim.
6. **Regime decomposition** — same six-regime labeling methodology and
   `REGIME_ROBUST` / `REGIME_DEPENDENT` / `REGIME_FRAGILE` classification
   already implemented in `edge_hunting/regime_decomposition.py`
   (`label_regimes`, `_classify`), unmodified, computed per-asset (regime
   quantile thresholds are already asset-specific in the existing code, so
   this generalizes correctly with zero changes).
7. **Duplicate-signal check** — same pairwise return/position correlation
   methodology and DUPLICATE_SIGNAL / NEAR_DUPLICATE / INDEPENDENT
   thresholds already implemented in
   `edge_hunting/duplicate_signal_detection.py`, applied across ALL
   surviving configs from this expansion (not just the original two EEM
   configs) — this is essential, since the whole point of testing 13
   related EM assets is that they are expected to be significantly
   correlated with each other, and any "new" survivor on VWO that is
   secretly 95% the same trade as the existing EEM signal (unsurprising,
   given EEM/VWO/IEMG are all broad, highly-correlated EM baskets) must be
   flagged as a duplicate, not counted as independent confirmation.
8. **Parameter-neighborhood analysis** (new use of existing data, no new
   methodology) — reuse `edge_hunting/robustness.py::
   parameter_sensitivity` (family-level ROBUST/MIXED/LIKELY_CURVE_FIT
   flag, based on mean/std of OOS Sharpe and positive-fraction across
   configs in a family) applied specifically to the Section 3.1 center
   grid, both (a) pooled across all 13 EM assets for the `rsi_revert`
   family as a whole, and (b) computed separately per-asset, so a
   "ROBUST" pooled flag driven by only 1 of 13 assets can be caught (see
   Section 6.3).

No validation gate here is new, relaxed, or invented for this test. This
is a deliberate constraint: if the EEM edge only "passes" once a bar is
lowered, that is itself evidence the original finding does not generalize.

---

## 6. Pass/fail criteria

### 6.1 Per-config pass/fail (identical bar to every existing candidate)

A single (asset, family, params) config is a **survivor** if and only if
it passes gates 1–4 in Section 5 exactly as any other candidate in this
codebase would need to (funnel survival, bootstrap SOLID, slippage
STRONGER at minimum through 10bp, and not REJECT-tier on benchmark
comparison). This reuses the exact bars already established; nothing is
loosened to make it easier for EM assets to "pass" than it was for the
original 7 candidates.

### 6.2 Family-level generalization pass/fail

A strategy family (e.g. `rsi_revert`) is classified, across the 13-asset EM
universe, as:

- **GENERALIZES** — at least 4 of the 13 assets (excluding RSX) produce an
  independent (per Section 5.7 duplicate check — not itself a
  NEAR_DUPLICATE/DUPLICATE_SIGNAL of another surviving EM asset in the
  same family) survivor, AND the family-level `parameter_sensitivity` flag
  (Section 5.8) is ROBUST when pooled across those independent survivors.
- **PARTIALLY_GENERALIZES** — 2–3 of the 13 assets produce an independent
  survivor, or the pooled sensitivity flag is MIXED rather than ROBUST.
- **DOES_NOT_GENERALIZE (LIKELY_SINGLE_ASSET_ARTIFACT)** — 0–1 of the 13
  assets (i.e., EEM alone, or nothing at all) produces a survivor, or the
  pooled sensitivity flag is LIKELY_CURVE_FIT.

The "4 of 13" and "2-3 of 13" thresholds are deliberately conservative
(roughly 30% and 15-23% hit rates respectively) because EM ETFs are highly
cross-correlated by construction (they all hold overlapping baskets of the
same underlying EM equities) — a real, structural EM mean-reversion effect
should be expected to show up on a meaningful minority of these assets,
not necessarily all 13, since idiosyncratic differences (single-country
concentration risk, currency effects, local market microstructure,
liquidity) will cause the effect to be stronger on some assets than others.
Requiring "at least 4 independent survivors" guards against calling a
single lucky asset (or two near-duplicate broad-EM-basket assets, which
Section 5.7 would catch anyway) a "generalizing" result.

### 6.3 The specific EEM-artifact check (per-asset breakdown requirement)

Because EEM itself is IN the 13-asset universe and is the source of the
original finding, the pooled `rsi_revert` sensitivity flag from Section
5.8(a) MUST be cross-checked against the per-asset breakdown from Section
5.8(b) before drawing any conclusion:

- If the pooled flag is ROBUST/GENERALIZES **only because EEM's own strong
  result is inflating the pooled mean**, and the per-asset breakdown shows
  EEM is a clear outlier (e.g., EEM's mean OOS Sharpe across its 80
  center-grid configs is more than 1 standard deviation above the mean of
  the other 12 assets' per-asset means), this must be flagged explicitly
  as `POOLED_RESULT_DRIVEN_BY_EEM_OUTLIER` in the final report, and the
  family-level classification (Section 6.2) must be downgraded by one tier
  from what the raw pooled numbers alone would suggest.
- This check exists specifically to prevent the exact failure mode this
  whole test is designed to catch: mistaking "EEM is unusually good at
  this, and the pooled average looks fine because EEM alone drags it up"
  for "this generalizes across EM."

### 6.4 Overall test verdict

The test's single headline conclusion is one of:

- **EDGE LIKELY REAL AND EM-STRUCTURAL** — `rsi_revert` (or another family)
  classified GENERALIZES per 6.2, with no `POOLED_RESULT_DRIVEN_BY_EEM_
  OUTLIER` flag per 6.3.
- **EDGE PARTIALLY GENERALIZES / EM-SUBSET-SPECIFIC** — PARTIALLY_
  GENERALIZES per 6.2, or GENERALIZES with the 6.3 outlier flag present
  (downgraded one tier as specified).
- **EDGE LIKELY A ONE-ASSET (EEM) ARTIFACT** — DOES_NOT_GENERALIZE per 6.2
  for every family tested.

This verdict answers the goal stated at the top of the task directly and
is the single most important number this entire spec produces.

---

## 7. Anti-overfitting warnings

1. **This is a confirmatory test, not a new hunting expedition.** The
   center grid (Section 3.1) is explicitly anchored to the ALREADY-FOUND
   EEM setting. If, after running this test, the "best" result turns out
   to be some other family/asset/parameter combination that was NOT the
   original EEM finding, that new result must NOT be silently promoted to
   candidate status by this test — it would itself need the exact same
   independent skepticism (full funnel → bootstrap → slippage → benchmark
   → regime → duplicate pipeline, PLUS its own future out-of-sample
   confirmation) as any brand-new discovery, not a shortcut promotion just
   because it emerged from a test that was framed around EEM.
2. **1,183 backtests is a large multiple-comparisons problem.** Running
   ~1,183 configs and finding some fraction "pass" the funnel is expected
   by chance alone at standard significance levels — the funnel's Sharpe
   thresholds are not multiple-comparison-corrected. This is precisely WHY
   Section 6 requires clearing a materially higher bar (independent
   survivors across MULTIPLE assets, not just one config passing) rather
   than treating any single passing config as meaningful on its own.
3. **Do not cherry-pick the parameter-neighborhood grid after seeing
   results.** The Section 3.1 grid (window ∈ {7,10,14,18,21}, oversold ∈
   {20,25,30,35}, overbought ∈ {65,70,75,80}) must be fixed and run in its
   entirety BEFORE looking at any individual result, and the full grid's
   results must be reported — including the ones that fail — not just a
   filtered subset that happens to look good.
4. **High cross-correlation among the 13 EM assets makes "independent
   confirmation" easy to fake and hard to earn.** This is precisely why
   Section 5.7 (duplicate-signal check) is applied to ALL new survivors
   from this expansion, and why Section 6.2 requires the survivors used
   to count toward "GENERALIZES" to be mutually INDEPENDENT (not
   NEAR_DUPLICATE/DUPLICATE_SIGNAL of each other) — five broad-basket EM
   ETFs all confirming the "same" trade is one data point, not five.
5. **A short or thin sample must not be reported as decisive.** Assets with
   shorter histories (IEMG, INDA, EIDO — see Section 1) or thinner
   liquidity (EZA, EIDO) will have systematically noisier walk-forward
   results. Any GENERALIZES/DOES_NOT_GENERALIZE verdict driven materially
   by these thinner-sample assets must be flagged as lower-confidence in
   the final report, with the higher-confidence, longer-history assets
   (EEM, VWO, EWZ, FXI, EWT, EWY, EWW, ILF) given more evidentiary weight
   in the qualitative writeup, even though the quantitative pass/fail
   counting in Section 6.2 treats them equally by design (to avoid a
   different, subtler form of after-the-fact cherry-picking about which
   assets "count").
6. **Bootstrap SOLID and slippage STRONGER do not mean "will work live."**
   These gates, exactly as used everywhere else in this codebase, describe
   robustness to reshuffled historical return ORDER and to modeled
   transaction cost — they say nothing about genuinely novel future
   conditions (e.g., an EM debt crisis unlike anything in the 2010–2025
   sample). This limitation, already disclosed for the original EEM
   candidate in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`, applies
   identically here and must be restated in this test's final report, not
   dropped just because it's a repeated caveat.
7. **A negative/DOES_NOT_GENERALIZE result is a valid and useful outcome,
   not a failed test.** If this test concludes the EEM edge is likely a
   one-asset artifact, that is exactly the kind of honest finding this
   framework exists to produce, and it must be reported with the same
   rigor and prominence as a positive finding — this spec explicitly
   rejects any framing where only a "successful" (edge confirmed) outcome
   would be written up.

---

## 8. Implementation phases (for future approval — not started)

**Phase 0 — Data audit (read-only, no backtests)**
Fetch/cache all 13 non-RSX assets (Section 1) plus attempt RSX per Section
1.1. Log actual bar counts, date ranges, and `MIN_VALID_BARS` pass/fail for
every asset. Produce a data-availability table before any strategy code
runs. Exit criterion: every asset's status (INCLUDED / EXCLUDED_SHORT_
HISTORY / EXCLUDED_DELISTED_INSUFFICIENT_DATA) is known and documented.

**Phase 1 — Sweep execution**
Run the ~1,183 configs (Section 3.3) through the existing
`edge_hunting/walk_forward.py` engine, unmodified, at the standard 1bp
baseline cost, producing per-config OOS Sharpe/drawdown/trade-count/etc.
— identical mechanism to every prior sweep in this codebase. No new
backtest logic is written in this phase.

**Phase 2 — Funnel + bootstrap**
Apply the unmodified six-filter funnel (Section 5.1) to all Phase 1
results. Run the unmodified bootstrap stress test (Section 5.3) on every
funnel survivor only (not on the full 1,183 — consistent with how bootstrap
testing has always been scoped to survivors elsewhere in this codebase).

**Phase 3 — Slippage + benchmark + regime + duplicate**
Apply Sections 5.4–5.7 to every bootstrap-SOLID survivor from Phase 2.

**Phase 4 — Parameter-neighborhood and generalization analysis**
Apply Section 5.8 and compute the Section 6 pass/fail classifications
(per-config, per-family, EEM-outlier check, and the single headline
verdict).

**Phase 5 — Report**
Write `reports/edge_hunting/eem_expansion_report.md` (data audit table,
full per-config results appendix, per-family generalization table, the
Section 6.3 EEM-outlier check result, the Section 6.4 headline verdict,
and every Section 7 anti-overfitting warning restated with test-specific
numbers filled in). No paper-trading or capital-allocation recommendation
is made in this report; it strictly answers the generalization question.
If new independent survivors are found (per Section 7.1), they are listed
separately as "candidates requiring their own full, independent future
validation" — not promoted.

Each phase requires the prior phase's output to exist before starting; no
phase is skipped or reordered. Implementation of Phase 0 does not begin
until this spec is explicitly approved.

---

## 9. Tests required (before or alongside implementation)

Consistent with this codebase's existing testing discipline (see
`tests/test_edge_hunting.py`, `tests/test_look_ahead.py`), the following
tests must exist before Phase 1 results are trusted:

1. **`test_eem_expansion_no_lookahead`** — reuse the same determinism/no-
   lookahead pattern as `tests/test_edge_hunting.py`'s existing look-ahead
   test: confirm that for any of the new (asset, family, params) configs
   introduced by this expansion, the signal at time *t* is unchanged if
   future rows (t+1 onward) are truncated from the input `df` — i.e., the
   existing anti-lookahead contract in `strategy_library.py` holds for
   every new asset, not just the assets it was originally tested against.
2. **`test_eem_expansion_rsx_handling`** — unit test that RSX is either (a)
   fully excluded with the `EXCLUDED_DELISTED_INSUFFICIENT_DATA` label, or
   (b) included ONLY as a pre-halt truncated, individually-labeled,
   aggregate-excluded data point, per Section 1.1 — never silently
   included as if it were a normal, continuously-tradeable asset.
3. **`test_eem_expansion_min_bars_enforced`** — confirm every asset in the
   final results table independently satisfies `MIN_VALID_BARS`, and that
   any asset failing this bar appears in an explicit exclusion list rather
   than being dropped without explanation.
4. **`test_eem_expansion_duplicate_check_applied_to_all_survivors`** —
   confirm the duplicate-signal check (Section 5.7) is run pairwise across
   ALL survivors from this expansion (not just against the original 2 EEM
   configs), since this is the specific gate that prevents highly-
   correlated EM basket ETFs from being miscounted as independent
   confirmations.
5. **`test_eem_expansion_no_threshold_drift`** — confirm the
   `FunnelThresholds`, bootstrap 200-reshuffle/seed=42/-35% floor,
   slippage cost levels, and regime-labeling quantile methodology used in
   this expansion are byte-for-byte identical (same default dataclass
   values, same imported functions) to the ones already used elsewhere in
   `edge_hunting/`, guarding against silent threshold-loosening creeping in
   during implementation.
6. **`test_eem_expansion_center_grid_matches_original_setting`** — confirm
   the Section 3.1 center grid actually contains `(window=14, oversold=30,
   overbought=70)` as one of its 80 combinations (i.e., the original
   winning setting is itself re-tested as part of the neighborhood, not
   accidentally excluded by an off-by-one in the grid construction).
7. **`test_eem_expansion_pooled_vs_per_asset_consistency`** — confirm the
   Section 6.3 EEM-outlier check is actually computed from the per-asset
   breakdown (Section 5.8b) and correctly downgrades the family
   classification when the outlier condition is met, using a synthetic
   fixture (e.g., 12 assets with near-zero Sharpe and 1 asset with a very
   high Sharpe) to verify the downgrade logic fires as specified.

All of these are extensions of the existing test philosophy in this repo
(determinism, no-lookahead, no-threshold-drift) applied to the specific
new failure modes this expansion introduces (RSX delisting, cross-asset
duplication, pooled-average masking a single outlier) — none require new
testing infrastructure beyond what `tests/test_edge_hunting.py` already
establishes.

---

## 10. How to decide whether the EEM edge is real or likely a one-asset artifact

This is the direct, single-paragraph answer the task asked for, restating
Section 6.4 in decision-procedure form:

**Run Phases 0–4. Look at the family-level classification for
`rsi_revert` specifically (Section 6.2), cross-checked against the
EEM-outlier flag (Section 6.3).** If `rsi_revert` is `GENERALIZES` with no
outlier flag — meaning at least 4 of the 13 EM assets (excluding RSX and
excluding any assets that turn out to be NEAR_DUPLICATE/DUPLICATE_SIGNAL
of each other) independently pass the exact same funnel → bootstrap →
slippage → benchmark pipeline already used for every other candidate in
this codebase, AND the pooled parameter-sensitivity flag is ROBUST without
being driven by EEM alone — then the edge is **likely real and
structural** to EM mean-reversion, and EEM is simply the asset where it
happens to be strongest or was found first, not a special case. If instead
only EEM (and possibly its two nearest, highly-correlated broad-basket
siblings VWO/IEMG, which the duplicate check would likely flag as
NEAR_DUPLICATE of EEM rather than independent confirmations) pass, or if
the pooled statistics turn out to be propped up by EEM's own outlier
performance per Section 6.3, then the honest conclusion is that the
original finding is **likely a one-asset (EEM) artifact** — a real result
on real out-of-sample data, but one that should not be assumed to
generalize, and should be weighted accordingly (i.e., treated as a
single, isolated data point rather than as one confirmed instance of a
broader, more trustworthy EM-wide effect) in any future paper-trading or
portfolio-construction decision involving the EEM signal or its
conditional backup.

---

## Explicit scope boundary (restating the task's constraints)

- This document is a **spec only**. No code in `edge_hunting/` has been
  added, modified, or run as part of producing this document.
- No backtests were executed to produce this spec — all references to
  "the original EEM finding," "the existing funnel/bootstrap/slippage/
  benchmark/regime/duplicate methodology," etc. are descriptions of
  code and results that already existed in this repository before this
  spec was written.
- The classification of EEM `rsi_revert(14,30/70)` as
  `APPROVED_FOR_PAPER_TEST (PRIMARY)` and EEM `rsi_revert(14,25/70)` as
  `BACKUP_PENDING_BOOTSTRAP` in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  are both unchanged by this document.
- No parameter was tuned to force a particular outcome anywhere in this
  spec; every parameter grid either reuses existing values verbatim
  (Section 3.2) or is a symmetric, pre-registered neighborhood around an
  already-published finding (Section 3.1).
- **Implementation does not begin until this spec is explicitly approved.**
