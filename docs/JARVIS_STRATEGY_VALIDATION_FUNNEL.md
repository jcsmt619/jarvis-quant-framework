# Jarvis Strategy Validation Funnel — Architecture Specification

> **Status:** DRAFT — design only. Do not implement until explicitly approved.
> **Origin:** Inspired by the *concept* of a large-scale strategy-testing funnel
> described in AI Pathways community material (a workflow that screens many
> candidate strategies down to a small surviving set through successive
> filters). **No proprietary code, prompts, or specific implementation
> details from that material are reproduced here.** This document is an
> independent design built entirely from Jarvis's own existing modules
> (`backtest/`, `edge_hunting/`, `core/`, `risk_of_ruin.py`) and its own
> validation philosophy already documented in `docs/STRATEGY_VALIDATION_GATE.md`,
> `docs/EDGE_HUNTING_PIPELINE_SPEC.md`, and `docs/NOISE_TEST_SPEC.md`.
> **Scope of this document:** design only. No code, no schema files, no new
> modules are created by this document.

---

## 1. Purpose

Jarvis already has a single-strategy validation gate
(`docs/STRATEGY_VALIDATION_GATE.md`) and a single-experiment pipeline
(`docs/EDGE_HUNTING_PIPELINE_SPEC.md`). What's missing is a **funnel** —
a staged sequence of increasingly expensive, increasingly strict filters
that a strategy (or a batch of many strategy *candidates*, e.g. every
member of a strategy family across a parameter grid) passes through one
stage at a time, getting rejected as early and cheaply as possible if it
doesn't clear a stage. This is the same "cheap filters first, expensive
filters last" principle used in the AI Pathways workflow this was inspired
by, but is not that workflow's code — it is a fresh design against Jarvis's
existing modules.

**Why a funnel and not just "run the full gate on everything":**

- Running full CPCV + deflated Sharpe + stress tests + noise tests on every
  candidate in a parameter grid (e.g. 50 strategies × 30 parameter
  combinations = 1,500 candidates) is computationally wasteful. Most
  candidates are obviously dead (negative Sharpe, catastrophic drawdown)
  and should be rejected in milliseconds, not after a 10-minute CPCV run.
- A funnel makes the **cost of rejection increase with the strength of the
  evidence already gathered** — cheap stages filter volume, expensive
  stages filter survivors.
- A funnel produces an honest audit trail: every rejected candidate has a
  recorded stage + reason, not a silent drop.

## 2. Relationship to Existing Jarvis Docs (no duplication, no contradiction)

| Existing doc | What it defines | How this funnel relates |
|---|---|---|
| `docs/STRATEGY_VALIDATION_GATE.md` | The final PASS/FAIL hard/soft gate criteria for ONE strategy that has already been fully backtested | This funnel's **final stage (Stage 10)** is exactly that gate, applied at the end, not duplicated with different numbers |
| `docs/EDGE_HUNTING_PIPELINE_SPEC.md` | The single-experiment pipeline: load config → fetch data → build features → backtest → benchmark → robustness battery → report → gate | This funnel is what runs **upstream** of and **around** that pipeline when testing many candidates; the pipeline's steps 5-9 correspond to funnel Stages 4-10 for a single survivor |
| `docs/NOISE_TEST_SPEC.md` | Synthetic-data noise test (gaussian walk + block bootstrap) | Reused directly as part of Stage 6 (bootstrap/Monte Carlo robustness) |
| `docs/EXPERIMENT_CONFIG_SCHEMA.md` | Per-experiment YAML config | Each candidate that survives to Stage 4+ gets materialized as one of these configs |
| `docs/STRATEGY_LIBRARY_EXPANSION_SPEC.md` | Four new strategy candidates | These (and any future strategy) are exactly the kind of candidates that would enter this funnel at Stage 1 |
| `docs/NOISE_TEST_SPEC.md` / `risk_of_ruin.py` | Monte Carlo trade-order resampling | Reused in Stage 6 |
| `backtest/performance.py` (`regime_breakdown`) | Regime-conditioned performance table | Reused directly in Stage 8 |

This funnel does not replace any existing spec. It is the orchestration
layer that sits above them when validating more than one candidate at a
time, and it reuses every existing metric/module rather than inventing new
statistics.

## 3. Design Principles

1. **Fail fast, fail cheap.** Stages are ordered from cheapest/coarsest to
   most expensive/strictest. A candidate is evaluated stage-by-stage and
   stops the moment it fails one — no wasted computation on later stages.
2. **No stage is skippable for strategies destined for paper/live trading.**
   A candidate may exit the funnel early for *research/comparison*
   purposes (e.g., "let's see how far a naive candidate gets"), but nothing
   is eligible for `docs/STRATEGY_VALIDATION_GATE.md` sign-off, and
   therefore for paper trading, without clearing all 10 stages.
3. **Every rejection is recorded, never silent.** A failed candidate
   produces a `funnel_report.json`/`.md` entry with the exact stage,
   metric, threshold, and value that caused rejection — mirroring the
   existing `failure_reasons.md` convention in
   `docs/STRATEGY_VALIDATION_GATE.md` §4.
4. **Reuses existing modules; invents no new statistics.** Every metric in
   this funnel maps to a function that already exists (or is already
   speced) in `backtest/performance.py`, `backtest/cpcv.py`,
   `backtest/deflated_sharpe.py`, `backtest/stress_test.py`,
   `risk_of_ruin.py`, or the proposed `backtest/noise_test.py`.
5. **Family-aware, not one-size-fits-all.** Different strategy families have
   different natural trade frequencies, holding periods, and data
   requirements (e.g., pairs/stat-arb needs a cointegration test that a
   momentum strategy never needs). The gates in §5 are the default; §6
   defines per-family overrides/additions.
6. **Options and futures strategy families are DESIGNED but NOT ENABLED.**
   Jarvis has no options or futures data/broker/risk infrastructure today
   (confirmed in `private_research/skool/SKOOL_JARVIS_GAP_REPORT.md`
   §1/§2/§6 and `docs/YOUTUBE_TO_JARVIS_ACTION_PLAN.md`). Those two family
   sections below are included for completeness per this design request,
   but are explicitly marked **NOT RUNNABLE TODAY** — implementing them
   requires the (separately gated, unapproved) options/futures scope
   expansion first.

## 4. The Ten-Stage Funnel (generic, applies to every family)

```
┌───────────────────────────────────────────────────────────────────────┐
│  CANDIDATE POOL (one strategy × one parameter combination = 1 unit)   │
└───────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 1 — BASIC PROFITABILITY FILTER              (cheapest)     │
  ├─────────────────────────────────────────────────────────────────┤
  │ In-sample, single full-history backtest (no walk-forward yet).   │
  │ Reuses: backtest/performance.compute_metrics()                   │
  │ Gate: total_return > 0  AND  sharpe > 0  AND  profit_factor > 1.0│
  │ Rejects: strategies that lose money even with full hindsight —   │
  │          the absolute cheapest possible filter.                  │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 2 — DRAWDOWN FILTER                                        │
  ├─────────────────────────────────────────────────────────────────┤
  │ Same in-sample run as Stage 1 (no re-simulation needed).          │
  │ Reuses: backtest/performance._max_drawdown()                     │
  │ Gate: max_drawdown <= family default ceiling (see §6)             │
  │       AND longest_underwater_bars <= family default (see §6)      │
  │ Rejects: strategies whose single best-case run already implies    │
  │          an unsurvivable drawdown — no point testing OOS.         │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 3 — TRADE-COUNT MINIMUM FILTER                              │
  ├─────────────────────────────────────────────────────────────────┤
  │ Same in-sample run.                                               │
  │ Reuses: len(result.trades) from Stage 1's run                     │
  │ Gate: total_trades >= family minimum (see §6)                     │
  │ Rejects: strategies with too few trades for ANY later statistic   │
  │          (Sharpe, DSR, CPCV) to be meaningful. This MUST run       │
  │          before Stage 4+ because a 3-trade "strategy" wastes a    │
  │          full walk-forward + CPCV run for a result that is        │
  │          statistically noise by construction.                     │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 4 — OUT-OF-SAMPLE FILTER                                    │
  ├─────────────────────────────────────────────────────────────────┤
  │ Single train/test split (e.g. 70/30 chronological), NOT yet the   │
  │ full rolling walk-forward (that's Stage 5 — this is a cheaper,    │
  │ coarser first OOS check).                                         │
  │ Reuses: backtest/backtester.py single-split mode                  │
  │ Gate: oos_sharpe > 0  AND  oos_sharpe >= 0.3 * in_sample_sharpe    │
  │       (the ratio check catches severe in-sample overfitting where │
  │        performance collapses out-of-sample)                       │
  │ Rejects: strategies whose edge doesn't survive a single honest    │
  │          train/test split — before paying for the full rolling    │
  │          walk-forward.                                            │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 5 — WALK-FORWARD FILTER                                     │
  ├─────────────────────────────────────────────────────────────────┤
  │ Full rolling walk-forward across all windows (train_window /      │
  │ test_window / step_size from docs/EXPERIMENT_CONFIG_SCHEMA.md).   │
  │ Reuses: backtest/backtester.py WalkForwardBacktester (existing)   │
  │ Gate: OOS Sharpe (aggregated across all windows) >= H1 threshold   │
  │       (0.5 default, see docs/STRATEGY_VALIDATION_GATE.md)          │
  │       AND max_drawdown across full OOS <= H2 threshold (25%)       │
  │       AND % of individual windows with positive return >= 55%     │
  │          (a NEW check not in the single-strategy gate — this is   │
  │           the funnel-specific "is this at least directionally     │
  │           consistent across time" filter, cheaper than full CPCV) │
  │ Rejects: strategies that only worked in one lucky historical       │
  │          period.                                                  │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 6 — SLIPPAGE / FEE ROBUSTNESS FILTER                         │
  ├─────────────────────────────────────────────────────────────────┤
  │ Re-run Stage 5's walk-forward THREE times with fee/slippage        │
  │ multipliers: 1x (baseline, already have it), 3x, 5x                │
  │ (e.g. baseline 5 bps slippage → 15 bps → 25 bps; baseline           │
  │  commission x3, x5).                                                │
  │ Reuses: backtest/backtester.py (same, different `fees` config)      │
  │ Gate: OOS Sharpe at 3x fees/slippage still > 0                       │
  │       AND OOS Sharpe at 3x fees/slippage >= 0.5 * baseline Sharpe    │
  │ Rejects: strategies whose "edge" is actually just picking up        │
  │          pennies in front of a bulldozer — high-frequency,          │
  │          low-per-trade-edge strategies that only look good because  │
  │          the backtest under-charges for execution costs. This is    │
  │          especially critical for mean-reversion and pairs families  │
  │          (see §6) which trade often and thinly.                     │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 7 — PARAMETER SENSITIVITY FILTER                             │
  ├─────────────────────────────────────────────────────────────────┤
  │ Re-run Stage 5's walk-forward with each key parameter perturbed     │
  │ ±10% and ±20% independently (one-at-a-time, not full grid search    │
  │ at this stage — that already happened upstream when the parameter   │
  │ grid was defined; here we're testing LOCAL stability around the     │
  │ winning point).                                                     │
  │ Reuses: same walk-forward backtester, looped over perturbed configs │
  │ Gate: Sharpe sign never flips across ANY single-parameter ±20%       │
  │       perturbation AND no single perturbation collapses Sharpe by   │
  │       more than 50% relative to the unperturbed value                │
  │       (same rule as existing H8 in docs/STRATEGY_VALIDATION_GATE.md, │
  │        reused here rather than redefined)                            │
  │ Rejects: strategies sitting on a "lucky spike" in parameter space —  │
  │          i.e., curve-fit to one specific parameter value rather than │
  │          a genuinely robust region.                                  │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 8 — REGIME SPLIT FILTER                                      │
  ├─────────────────────────────────────────────────────────────────┤
  │ Reuses: backtest/performance.regime_breakdown() (existing,          │
  │         consumes the HMM regime history already produced during     │
  │         the walk-forward)                                           │
  │ Gate: strategy must be profitable (positive return contribution) in │
  │       AT LEAST 2 of the regimes it spends >= 10% of time in — a     │
  │       single-regime strategy is fragile to regime misclassification │
  │       AND no single regime accounts for >80% of total P&L           │
  │          (concentration check — catches strategies that are really  │
  │           "long the 2020-2021 bull market" wearing a regime-model   │
  │           costume)                                                   │
  │ Rejects: strategies whose entire edge lives in one historical        │
  │          regime/era.                                                 │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 9 — BOOTSTRAP / MONTE CARLO ROBUSTNESS FILTER (expensive)     │
  ├─────────────────────────────────────────────────────────────────┤
  │ Three sub-checks, all reused directly from existing/speced modules: │
  │  (a) CPCV: backtest/cpcv.py backtest_paths() → Sharpe distribution  │
  │      Gate: >= 60% of phi paths positive (same as existing H4)       │
  │  (b) Deflated Sharpe: backtest/deflated_sharpe.py, with HONEST      │
  │      n_trials = size of the parameter grid this candidate came from │
  │      (not 1 — the funnel context means many candidates were tried,  │
  │       and DSR must be charged for the true search size)             │
  │      Gate: DSR >= 0.80 (same as existing H3)                        │
  │  (c) Noise test: backtest/noise_test.py (per docs/NOISE_TEST_SPEC.md)│
  │      block-bootstrap-shuffled generator, n_sims >= 200               │
  │      Gate: real Sharpe >= 95th percentile of noise distribution      │
  │  (d) Trade-order Monte Carlo: risk_of_ruin.py resampling of the      │
  │      realized trade P&L sequence (existing module)                   │
  │      Gate: probability of >25% drawdown across resampled trade       │
  │            orderings <= 10%                                          │
  │ Rejects: strategies whose result is a product of the specific        │
  │          historical path or the specific number of candidates        │
  │          searched, not genuine structure.                            │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 10 — BENCHMARK COMPARISON FILTER                             │
  ├─────────────────────────────────────────────────────────────────┤
  │ Reuses: backtest/backtester.py benchmark_random(), buy&hold,        │
  │         SMA200 trend follower — SAME covered region + SAME risk     │
  │         rules for all benchmarks (existing convention)              │
  │ Gate: must beat random allocation (mean Sharpe) — HARD               │
  │       must beat buy&hold — SOFT/informational only (per existing     │
  │       H5/S1 split in docs/STRATEGY_VALIDATION_GATE.md — a            │
  │       risk-managed edge is allowed to underperform buy&hold in a     │
  │       pure bull run and still be a legitimate, lower-variance edge)  │
  │ Rejects: strategies indistinguishable from a coin-flip allocator.    │
  └─────────────────────────────────────────────────────────────────┘
         │ survivors
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ FINAL: docs/STRATEGY_VALIDATION_GATE.md full hard/soft gate check   │
  │ (re-verifies everything above under the single-strategy gate's own  │
  │  numbering H1-H8/S1-S6 for the formal PASS/FAIL record — this is    │
  │  not redundant work, it is the canonical sign-off artifact that     │
  │  already exists and that paper-trading eligibility depends on)      │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼
     ELIGIBLE FOR PAPER TRADING
```

### 4.1 Why this ordering

Cheapest-to-most-expensive, and cheapest-to-reject-most-candidates first:

| Stage | Relative cost | Typical rejection rate (illustrative, not a promise) |
|---|---|---|
| 1. Basic profitability | ~instant (1 backtest run) | High — rejects most random/bad candidates |
| 2. Drawdown | ~free (reuses Stage 1 output) | Medium |
| 3. Trade-count minimum | ~free (reuses Stage 1 output) | Medium (catches sparse-signal candidates) |
| 4. Out-of-sample | 1 extra backtest run | Medium-high (overfitting shows up early) |
| 5. Walk-forward | N backtest runs (N = # windows) | Medium |
| 6. Slippage/fee robustness | 3x the Stage 5 cost | Medium (kills thin-edge/high-turnover candidates) |
| 7. Parameter sensitivity | ~4-8x the Stage 5 cost (perturbations) | Low-medium |
| 8. Regime split | ~free (reuses Stage 5's regime history) | Low-medium |
| 9. Bootstrap/Monte Carlo | Most expensive (CPCV + DSR + 200+ noise sims + trade MC) | Low (candidates reaching here already survived a lot) |
| 10. Benchmark comparison | ~free (reuses existing equity curves) | Low |

By the time a candidate reaches Stage 9 (the most expensive stage), it has
already survived eight cheaper filters — this is the entire point of a
funnel shape rather than running everything on everything.

## 5. Default Gate Thresholds (baseline; §6 gives per-family deltas)

| Stage | Metric | Default threshold |
|---|---|---|
| 1 | total_return | > 0 |
| 1 | sharpe (in-sample) | > 0 |
| 1 | profit_factor | > 1.0 |
| 2 | max_drawdown | ≤ 30% (funnel default; note stricter 25% at the FINAL gate per H2) |
| 2 | longest_underwater_bars | ≤ 252 (1 trading year) |
| 3 | total_trades | ≥ 30 (statistical minimum for any Sharpe/DSR claim) |
| 4 | oos_sharpe | > 0 |
| 4 | oos_sharpe / in_sample_sharpe | ≥ 0.30 |
| 5 | aggregated OOS sharpe | ≥ 0.5 |
| 5 | aggregated OOS max_drawdown | ≤ 25% |
| 5 | % windows positive | ≥ 55% |
| 6 | OOS sharpe @ 3x fees | > 0 |
| 6 | OOS sharpe @ 3x fees / baseline | ≥ 0.50 |
| 7 | Sharpe sign flip on ±20% param perturbation | never |
| 7 | Sharpe collapse on ±20% param perturbation | ≤ 50% |
| 8 | regimes with positive contribution (of regimes ≥10% time) | ≥ 2 |
| 8 | single-regime P&L concentration | ≤ 80% |
| 9 | CPCV % paths positive | ≥ 60% |
| 9 | DSR (honest n_trials) | ≥ 0.80 |
| 9 | Noise test percentile | ≥ 95th |
| 9 | Trade-order MC: P(DD > 25%) | ≤ 10% |
| 10 | beats random allocation | required (hard) |
| 10 | beats buy & hold | informational (soft) |

These are the funnel's own pre-filter defaults. They intentionally sit at
or slightly looser than the FINAL `docs/STRATEGY_VALIDATION_GATE.md`
thresholds (e.g., Stage 2's 30% vs. the final gate's 25%) so that the
funnel doesn't reject a candidate for a reason the final gate would also
reject it for — the funnel's job is to save compute, not to be stricter
than the canonical gate. The FINAL stage always re-applies the canonical
thresholds from `docs/STRATEGY_VALIDATION_GATE.md` as the authoritative
record.

## 6. Per-Strategy-Family Specialization

Each family below overrides/extends the generic §5 defaults where its
economics genuinely differ, and specifies its own data/history/parameter
requirements. Nothing here changes any existing strategy file — this is a
funnel *configuration* per family, analogous to how
`docs/EXPERIMENT_CONFIG_SCHEMA.md` configs vary per experiment today.

---

### 6.1 Mean Reversion

*(Existing Jarvis example: `strategies/baseline_ema_rsi.py`)*

| Aspect | Spec |
|---|---|
| **Required data** | Daily OHLCV (existing `data_fetcher.py`); no additional source needed |
| **Minimum history** | 5 years (1,260 daily bars) — mean-reversion regimes cycle over months, need multiple cycles |
| **Parameter grid (example)** | `rsi_period ∈ {7,14,21}`, `rsi_oversold ∈ {20,25,30,35}`, `rsi_overbought ∈ {65,70,75,80}`, `ema_fast ∈ {10,20,30}`, `ema_slow ∈ {40,50,60}`, `atr_multiplier ∈ {1.5,2.0,2.5}` → ~3×4×4×3×3×3 = 1,296 combinations before funnel filtering |
| **Validation metrics used** | All ten generic stages apply unmodified, EXCEPT: |
| **Stage 3 override** | `total_trades ≥ 50` (raised from 30 — mean reversion trades frequently; a "mean reversion" candidate with only 30 trades over 5 years is suspiciously inactive and likely mis-specified) |
| **Stage 6 override (STRICTEST of all families)** | Slippage/fee multiplier test extended to 5x AND 10x, not just 3x. Gate: OOS Sharpe @ 10x fees still > 0. **Rationale:** mean reversion is the family most likely to be a fee/slippage illusion — frequent small-edge trades are exactly what transaction costs erode fastest. |
| **Stage 8 addition** | Must show positive contribution specifically in `range_bound`/`choppy`-labeled HMM regimes (not just "2 of N regimes") — a mean-reversion strategy that only makes money in trending regimes is mislabeled. |
| **Common failure reasons** | (1) Fails Stage 6 at 5-10x fees — "edge" was transaction-cost noise. (2) Fails Stage 8 regime check — actually a disguised trend strategy. (3) Fails Stage 3 — too few trades for any statistic to mean anything. |

---

### 6.2 Momentum

| Aspect | Spec |
|---|---|
| **Required data** | Daily OHLCV, plus a broad-market proxy return series (e.g. SPY) if using relative/cross-sectional momentum |
| **Minimum history** | 10 years (2,520 daily bars) — momentum's edge is known to have multi-year regime dependence (works well pre-2018, degrades in some periods); short histories overstate confidence |
| **Parameter grid (example)** | `lookback ∈ {20,60,90,126,252}`, `skip_recent ∈ {0,5,10}` (skip most-recent days to avoid short-term reversal contamination), `rebalance_freq ∈ {weekly, monthly}`, `top_n_pct ∈ {0.1,0.2,0.3}` |
| **Stage 5 override** | Minimum 8 walk-forward windows required (raised from generic default) — momentum needs to be tested across multiple distinct market cycles (2015-16 chop, 2017 low-vol grind, 2018 Q4 selloff, 2020 crash+recovery, 2022 bear, etc.), not just 3-4 windows. |
| **Stage 8 addition** | Explicit check against the known "momentum crash" failure mode: flag (not necessarily hard-reject, but must be surfaced) if the single worst drawdown occurs at a regime transition (e.g., sharp reversal after a crash) — reuses `backtest/stress_test.py`'s regime misclassification injection. |
| **Common failure reasons** | (1) Fails Stage 5 minimum-windows requirement — insufficient history for a momentum claim. (2) Fails Stage 7 — momentum is notoriously lookback-sensitive; small changes to lookback window often flip results. (3) Fails Stage 9 noise test — momentum backtests are especially prone to matching the specific historical trend structure of the sample period. |

---

### 6.3 Breakout

| Aspect | Spec |
|---|---|
| **Required data** | Daily OHLCV; needs accurate high/low (not just close) since breakout logic is range-based |
| **Minimum history** | 5 years (1,260 bars) |
| **Parameter grid (example)** | `channel_period ∈ {20,55,100}` (classic Turtle-style channel lengths), `breakout_confirmation_bars ∈ {1,2,3}`, `atr_multiplier_stop ∈ {1.5,2.0,3.0}`, `volume_confirmation ∈ {true,false}` |
| **Stage 1 override** | Because breakout strategies are naturally low-win-rate/high-payoff, `profit_factor > 1.0` alone is too loose a Stage 1 filter for this family — ADD `avg_win / avg_loss ≥ 1.5` as a Stage 1 co-requirement, since breakout strategies with `profit_factor` barely above 1.0 and a payoff ratio under 1.5 are usually noise. |
| **Stage 3 override** | `total_trades ≥ 20` (lowered from 30) — breakout signals are inherently rarer than mean-reversion signals; 20 clean breakout trades over the minimum history is acceptable given the more info-rich, "big directional" nature of each individual trade. |
| **Stage 6 note** | Less sensitive to fee multiplier than mean reversion (fewer, larger trades) — default 3x/5x from §5 is sufficient, no override needed. |
| **Common failure reasons** | (1) Fails Stage 1's payoff-ratio co-requirement — false breakouts dominate. (2) Fails Stage 2 drawdown — breakout strategies whipsaw badly in choppy/range-bound periods, producing outsized consecutive-loss drawdowns. (3) Fails Stage 8 — heavily concentrated in trending-regime P&L, as expected, but must still show it's not a single-era artifact. |

---

### 6.4 Trend Following

*(Existing Jarvis relevance: `core/regime_strategies.py` trend-following posture; `docs/STRATEGY_LIBRARY_EXPANSION_SPEC.md`'s Residual Momentum is adjacent)*

| Aspect | Spec |
|---|---|
| **Required data** | Daily OHLCV; ideally multi-decade history for asset classes where available |
| **Minimum history** | 15 years (3,780 daily bars) — trend-following's defining property (a small number of very large winning trades) requires enough history to actually contain a handful of major trends (2008 crash, 2020 crash, a multi-year bull market, at least one prolonged chop period) |
| **Parameter grid (example)** | `trend_ma_period ∈ {50,100,150,200}`, `entry_confirmation ∈ {ma_cross, adx_threshold}`, `adx_threshold ∈ {20,25,30}`, `trailing_stop_atr_mult ∈ {2.0,3.0,4.0}` |
| **Stage 3 override** | `total_trades ≥ 15` (lowered further than breakout) — genuine trend-following strategies are explicitly designed to trade rarely and hold long; a strict 30-trade minimum would systematically reject the family's core design intent. To compensate for the lower trade count reducing statistical power, Stage 9's DSR gate is RAISED to `≥ 0.85` for this family specifically. |
| **Stage 5 override** | Because trend-following P&L is famously lumpy (most of the return from a handful of trades), Stage 5's "% windows positive ≥ 55%" is RELAXED to `≥ 40%` — a trend follower can lose money in most rolling windows and still be a legitimate strategy if the few winning windows are large enough. This relaxation is compensated by keeping Stage 9's noise-test and DSR bars at their strictest settings. |
| **Common failure reasons** | (1) Fails Stage 9's raised DSR bar — too few large trades to statistically distinguish from luck. (2) Fails Stage 2 — trend followers can have long, painful drawdowns during chop; many candidates die here. (3) Fails Stage 6 — whipsaw-driven false entries during choppy periods rack up fees disproportionate to the (rare) big wins. |

---

### 6.5 Pairs / Statistical Arbitrage

*(Existing Jarvis relevance: `pairs_scanner.py`, `backtest/pairs_backtest.py`)*

| Aspect | Spec |
|---|---|
| **Required data** | Daily (or intraday, if available) OHLCV for BOTH legs of every candidate pair; requires a cointegration/correlation pre-screen (existing `pairs_scanner.py` logic) before any pair even enters the funnel |
| **Minimum history** | 3 years (756 bars) for the cointegration test itself, but the FUNNEL requires an ADDITIONAL out-of-sample period of at least 1 year beyond the cointegration-fitting window — i.e., cointegration is fit on data the funnel's Stage 4+ never sees, to avoid the classic pairs-trading trap of fitting the spread on the same data used to test it |
| **Parameter grid (example)** | `lookback_zscore ∈ {20,40,60}`, `entry_zscore ∈ {1.5,2.0,2.5}`, `exit_zscore ∈ {0.0,0.5}`, `stop_zscore ∈ {3.0,3.5,4.0}`, `cointegration_pvalue_max ∈ {0.01,0.05}` |
| **Stage 0 (NEW, family-specific pre-stage before Stage 1)** | Cointegration/correlation stability pre-screen: the pair must show statistically significant cointegration (ADF/Engle-Granger p-value ≤ threshold) on the FIT window, AND the spread's half-life of mean reversion must fall in a sane range (e.g., 2-60 bars — too fast = noise, too slow = not actually mean-reverting on a tradeable horizon). Pairs failing this never enter Stage 1 at all. |
| **Stage 6 override (STRICTEST alongside mean reversion)** | Pairs trading is executed as two simultaneous legs — fee/slippage is effectively doubled versus a single-instrument strategy. Funnel must model slippage on BOTH legs independently (not a single blended assumption) and test at 3x/5x/10x. |
| **Stage 8 addition** | Must verify the cointegration relationship itself is stable across the regime-split windows — reuses `core/capital_allocator.py`'s `compute_correlation_matrix()` (already confirmed to exist per `docs/STRATEGY_LIBRARY_EXPANSION_SPEC.md` §2.3) to check the pair's correlation didn't structurally break during any sub-period. A pair whose cointegration existed pre-2020 but vanished post-2020 fails here even if the blended full-history backtest looks fine. |
| **Common failure reasons** | (1) Fails the Stage 0 pre-screen — spurious/non-cointegrated pair. (2) Fails Stage 8's cointegration-stability check — regime-dependent relationship, not a genuine structural link (e.g., two stocks that were correlated only because they were both COVID-recovery plays). (3) Fails Stage 6's dual-leg fee test — the spread is too tight relative to round-trip costs on both legs. |

---

### 6.6 Volatility / Risk-Premia

*(Existing Jarvis relevance: `vol_allocation.py`)*

| Aspect | Spec |
|---|---|
| **Required data** | Daily OHLCV plus a volatility proxy (realized vol from returns is sufficient; VIX-level data is a nice-to-have but not required for stocks/ETFs-only scope) |
| **Minimum history** | 10 years (2,520 bars) — must span at least 2 distinct "vol regime" cycles (a low-vol grind and a vol-spike event) to have any claim to a genuine risk-premia edge rather than a single-regime artifact |
| **Parameter grid (example)** | `vol_lookback ∈ {10,20,30,60}`, `vol_percentile_entry ∈ {10,20,30}` (e.g., enter when realized vol is in the bottom 10-30th percentile), `target_vol ∈ {10%,15%,20%}` (for vol-targeting sizing variants), `rebalance_freq ∈ {daily,weekly}` |
| **Stage 2 override (STRICTEST drawdown ceiling of all families)** | `max_drawdown ≤ 20%` (tightened from the generic 30%) — risk-premia/short-vol-style strategies have a well-documented "picking up nickels in front of a steamroller" failure mode (large infrequent tail losses); the funnel should be LESS forgiving on drawdown for this family, not more. |
| **Stage 9 addition (family-specific, beyond the generic four sub-checks)** | Explicit tail-risk stress test using `backtest/stress_test.py`'s crash injection at an ELEVATED severity (default crash injection settings from `docs/EXPERIMENT_CONFIG_SCHEMA.md` use -5% to -15% gaps; this family's Stage 9 requires an additional run at -20% to -30% gap severity) — reusing the existing stress-test module with a stricter parameter, not new code. Gate: worst-case drawdown at elevated severity ≤ 40% (looser than the elevated stress implies catastrophic risk is expected to be worse under stress, but must still be survivable). |
| **Common failure reasons** | (1) Fails Stage 2's tightened 20% ceiling — classic short-vol blowup profile. (2) Fails the elevated Stage 9 tail-stress addition — strategy is empirically fine in normal markets but catastrophic in a true vol event, which is exactly the risk this family must screen for. (3) Fails Stage 8 — most of the "edge" concentrated in the single longest low-vol grind period in the sample (e.g., 2017 or 2023-2024), not representative of the family's actual risk. |

---

### 6.7 Options Strategies — **NOT RUNNABLE TODAY**

| Aspect | Spec |
|---|---|
| **Status** | **DESIGN ONLY — no options data/Greeks/broker infrastructure exists in Jarvis today.** Per `private_research/skool/SKOOL_JARVIS_GAP_REPORT.md` §1/§2 and `docs/YOUTUBE_TO_JARVIS_ACTION_PLAN.md` item #3, options remain "not planned — major scope expansion." This section documents what the funnel WOULD require if that scope were ever separately approved; it does not authorize or schedule that work. |
| **Required data (if approved)** | Full options chain history (bid/ask, volume, open interest) per underlying, plus implied volatility surface, plus computed/verified Greeks (delta, gamma, theta, vega). None of `data_fetcher.py`, `data/feature_engineering.py`, or any existing data source in this repo provides this today. |
| **Minimum history (if approved)** | 5+ years of full chain history per underlying — options-specific effects (IV crush around earnings, term-structure shape, skew) need multiple full IV cycles, and clean historical options chain data is materially harder to source than equity OHLCV. |
| **Parameter grid (example, if approved)** | `dte_target ∈ {30,45,60,90}`, `delta_target ∈ {0.15,0.20,0.30,0.40}` (for spreads/verticals), `iv_rank_entry_threshold ∈ {30,50,70}`, `profit_target_pct ∈ {25%,50%,75%}`, `stop_loss_pct_of_credit ∈ {100%,150%,200%}` |
| **Stage 6 override (would be MOST severe of any family)** | Options bid/ask spreads are frequently 5-15% of the option's price for anything beyond the most liquid names/strikes — the generic 3x/5x fee multiplier is insufficient. This family would require an explicit BID/ASK SPREAD model (fill at mid ± half-spread, not last price) rather than a flat slippage bps assumption, plus a liquidity filter (minimum open interest/volume) that rejects candidates in illiquid contracts before Stage 1 even runs. |
| **Stage 9 addition (would be required)** | Assignment/early-exercise risk modeling for American-style equity options, and a dedicated Greeks-based stress test (IV shock ±50%, underlying gap ±10%, simultaneous) beyond what `backtest/stress_test.py` currently models for linear equity positions. |
| **Common failure reasons (anticipated)** | Bid/ask-spread-driven Stage 6 failures would likely be the dominant rejection reason for this family — many options "edges" visible in naively-priced backtests evaporate once realistic fill assumptions are applied. |
| **Blocking prerequisite** | New options data source integration + Greeks computation + options-aware risk manager rules + (per `docs/BROKER_BREADTH_SPEC.md`'s pattern) a broker adapter capability check for options trading support — none of which this document authorizes. |

---

### 6.8 Futures Strategies — **NOT RUNNABLE TODAY**

| Aspect | Spec |
|---|---|
| **Status** | **DESIGN ONLY — no futures data/margin/roll infrastructure exists in Jarvis today.** Futures were not identified as an existing capability anywhere in the current codebase (`broker/alpaca_client.py` is equities/ETF-focused; no futures contract roll logic, no margin/leverage model beyond the existing equity leverage cap in `core/risk_manager.py`). This section documents what the funnel WOULD require if that scope were ever separately approved; it does not authorize or schedule that work. |
| **Required data (if approved)** | Continuous, roll-adjusted futures price series (back-adjusted or ratio-adjusted, clearly documented which method) per contract, PLUS raw individual-contract data to correctly model roll dates/costs — continuous-only series hide the roll-yield effect this family's edge (or lack thereof) partly depends on. |
| **Minimum history (if approved)** | 15-20 years where available — many futures-specific effects (term structure/carry, seasonality) are slow-moving and need a long sample; also most futures markets have far fewer independent "regime" observations per unit of calendar time than equities. |
| **Parameter grid (example, if approved)** | `roll_method ∈ {calendar_days_before_expiry, volume_based}`, `contracts_held ∈ {front_month, second_month}`, `trend_lookback ∈ {20,60,120}` (for trend/carry-style futures strategies), `margin_utilization_target ∈ {20%,40%,60%}` |
| **Stage 2 override (would be required)** | Drawdown must be computed on MARGIN-BASED equity, not notional exposure — futures leverage means a modest-looking price move can be a large drawdown on posted margin. The generic §5 defaults (which assume equity-style 1:1 notional accounting) are not directly applicable; this family needs its own equity-curve construction before Stage 2 can even run meaningfully. |
| **Stage 6 override (would be required)** | Roll costs (contango/backwardation-driven slippage at each roll date) must be explicitly modeled as a distinct cost line item, separate from per-trade slippage/commission — a strategy that looks profitable ignoring roll cost can be a net loser once roll cost is included, and this is a well-documented futures-specific failure mode. |
| **Stage 9 addition (would be required)** | Margin-call/liquidation stress test — simulate a sequence of adverse moves against the modeled margin_utilization_target and verify the position would not have been forcibly liquidated, which is a risk category equity strategies (as currently modeled in `core/risk_manager.py`) don't need to consider. |
| **Common failure reasons (anticipated)** | Roll-cost-driven Stage 6 failures, and margin-based Stage 2 drawdown failures that don't show up at all under a naive notional-equity accounting — i.e., this family's biggest risk is a funnel that FORGOT to specialize Stage 2/Stage 6 and gave a false pass. |
| **Blocking prerequisite** | New futures data source (continuous + individual contracts) + roll-cost model + margin-based risk accounting in `core/risk_manager.py` + (per `docs/BROKER_BREADTH_SPEC.md`'s pattern) a broker adapter capable of futures execution — none of which this document authorizes. |

---

## 7. Output Report Format

Extends the existing `reports/experiments/{name}/` convention
(`docs/EDGE_HUNTING_PIPELINE_SPEC.md` §7) with a funnel-level rollup, since
the funnel typically evaluates many candidates, not one:

```
reports/funnel_runs/{run_id}/
├── funnel_summary.json          # one row per candidate: family, params, final stage
│                                 # reached, PASS/FAIL, all stage-by-stage metrics
├── funnel_summary.md            # human-readable version of the above, sorted by
│                                 # family then by final stage reached (descending)
├── survivors/
│   └── {strategy_name}/         # for every candidate that reached the FINAL stage:
│       ├── config_snapshot.yaml #   the exact materialized experiment config
│       └── ... (same reports/experiments/{name}/ structure as today)
├── rejected/
│   └── {strategy_name}/
│       ├── failure_reasons.md   # EXACT stage + metric + threshold + actual value
│       │                        # that caused rejection (same convention as the
│       │                        # existing single-strategy failure_reasons.md,
│       │                        # but with a `stage` field added)
│       └── config_snapshot.yaml
└── funnel_config_snapshot.yaml  # the parameter grid + family + thresholds used
                                  # for this entire run, for reproducibility
```

### 7.1 `funnel_summary.json` schema (illustrative)

```json
{
  "run_id": "2026-07-04_mean_reversion_grid",
  "family": "mean_reversion",
  "total_candidates": 1296,
  "candidates": [
    {
      "candidate_id": "rsi14_os30_ob70_ema20_50_atr2.0",
      "params": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
                 "ema_fast": 20, "ema_slow": 50, "atr_multiplier": 2.0},
      "final_stage_reached": 6,
      "verdict": "FAIL",
      "failure_stage": 6,
      "failure_reason": "OOS Sharpe @ 10x fees = -0.12 (must be > 0)",
      "stage_metrics": {
        "stage_1": {"total_return": 0.18, "sharpe": 0.61, "profit_factor": 1.34},
        "stage_2": {"max_drawdown": -0.14, "longest_underwater_bars": 88},
        "stage_3": {"total_trades": 142},
        "stage_4": {"oos_sharpe": 0.41, "oos_is_ratio": 0.67},
        "stage_5": {"agg_oos_sharpe": 0.55, "agg_oos_max_dd": -0.19, "pct_windows_positive": 0.61},
        "stage_6": {"sharpe_3x_fees": 0.22, "sharpe_5x_fees": 0.04, "sharpe_10x_fees": -0.12}
      }
    }
  ],
  "survivors_count": 3,
  "rejection_breakdown_by_stage": {
    "stage_1": 812, "stage_2": 201, "stage_3": 94, "stage_4": 88,
    "stage_5": 61, "stage_6": 37, "stage_7": 0, "stage_8": 0,
    "stage_9": 0, "stage_10": 0
  }
}
```

The `rejection_breakdown_by_stage` field is itself a valuable diagnostic —
if e.g. Stage 6 (fee robustness) is rejecting the most candidates for a
given family, that's a signal the entire family/parameter-space is
fee-sensitive, worth knowing at the family level, not just per-candidate.

### 7.2 `failure_reasons.md` (per rejected candidate — extends existing convention)

```markdown
# Failure Reasons — mean_reversion / rsi14_os30_ob70_ema20_50_atr2.0

## Verdict: FAIL

## Funnel Stage Reached: 6 of 10 (Slippage/Fee Robustness Filter)

## Failure Detail

- **Stage 6: OOS Sharpe @ 10x fees = -0.12 (must be > 0)**
  This candidate cleared Stages 1-5 (profitable, acceptable drawdown,
  sufficient trade count, positive OOS, stable across walk-forward
  windows) but its edge does not survive realistic-to-pessimistic
  transaction cost assumptions. At baseline fees, Sharpe was 0.61; at 3x
  fees, 0.22; at 5x fees, 0.04; at 10x fees, -0.12. The edge appears to be
  substantially a function of under-charged trading costs rather than
  genuine structure.

## Stages Passed (for reference)

1. Basic profitability: PASS (return 18%, Sharpe 0.61, PF 1.34)
2. Drawdown: PASS (max DD -14%, underwater 88 bars)
3. Trade-count minimum: PASS (142 trades ≥ 50 required for this family)
4. Out-of-sample: PASS (OOS Sharpe 0.41, ratio to in-sample 0.67)
5. Walk-forward: PASS (aggregated OOS Sharpe 0.55, 61% windows positive)

## Recommendation

Do not advance to Stage 7+. If this parameter region is of further
interest, consider whether a lower-turnover variant (fewer trades per
year) of the same rule set would survive the fee-robustness stage, since
the underlying signal (Stages 1-5) is not obviously broken — only its
current implementation's trading frequency is too costly.
```

## 8. What This Document Does NOT Do

- ❌ Does not create any new Python module, config schema, or file.
- ❌ Does not modify `docs/STRATEGY_VALIDATION_GATE.md`,
  `docs/EDGE_HUNTING_PIPELINE_SPEC.md`, or `docs/NOISE_TEST_SPEC.md` — it
  is additive/orchestration-only, exactly like those documents are
  relative to each other.
- ❌ Does not implement, schedule, or approve options or futures support —
  §6.7 and §6.8 are explicitly marked not-runnable-today design sections.
- ❌ Does not reproduce any proprietary code, prompt text, or specific
  implementation detail from the AI Pathways community material that
  inspired the *idea* of a staged funnel — every mechanism specified above
  maps to a Jarvis module that already exists or is already speced in this
  repo's own docs.
- ❌ Does not authorize implementation. Per the instruction this document
  was created under: **design only.**

---

**Approval required:** Do not implement any part of this funnel until this
design is explicitly approved, and even then, implementation should proceed
one stage/module at a time (mirroring the sequencing discipline used in
`docs/STRATEGY_LIBRARY_EXPANSION_SPEC.md` §5), not as a single large
change.
