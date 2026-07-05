# QuantConnect/LEAN Mirror Comparison — EEM RSI Mean-Reversion Candidate

**Status: COMPARISON REPORT ONLY. No strategy code was edited. No
parameters were tuned. No Jarvis backtest was re-run — all Jarvis figures
below are taken as-is from existing report files. No paper or live
trading was enabled in either Jarvis or LEAN. This document interprets
two already-completed LEAN Docker backtest runs (an initial full-period
run, and a refined run that adds an explicit EEM buy-and-hold leg)
against already-existing Jarvis reports; it does not authorize any
further action beyond what is recommended in Section 10.**

**Update (refined run):** this document was revised after a second,
refined LEAN mirror run added the previously-missing EEM buy-and-hold
comparison leg (closing the Section 3 gap identified in the initial
version of this report). The revised figures and conclusion are
reflected throughout; the original run's figures are retained inline
where still relevant for context (e.g. Sharpe, fee total, order-timing
note are unchanged between the two runs).


## Sources read

- `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
- `docs/EEM_EXPANSION_DECISION_MEMO.md`
- `docs/QUANTCONNECT_LEAN_EEM_VALIDATION_SPEC.md` (the approved spec this
  run was intended to follow)
- `reports/eem_expansion/eem_expansion_summary.json`
- `reports/eem_expansion/eem_expansion_report.md`
- `reports/edge_hunting/benchmark_comparison_report.md` (EEM buy-and-hold
  figures)
- User-supplied LEAN mirror run summary (project `Jarvis_EEM_RSI_Mirror`,
  local QuantConnect/LEAN Docker backtest)

## Run inputs being compared

| | Jarvis (approved candidate) | LEAN mirror (this run) |
|---|---|---|
| Strategy | `rsi_revert(window=14, oversold=30, overbought=70)` | EEM rsi_revert(14,30/70) |
| Asset | EEM | EEM |
| Date range loaded | 2010-01-01 to 2025-01-01 | 2010-01-01 to 2025-01-01 |
| Scored window | **5-window walk-forward OOS tails only** (~1,134 trading days, ≈4.5 years total) | **Full continuous 2010–2025 period** (≈15 years, no walk-forward split) |
| Starting capital | $100,000 (backtest_engine default) | $100,000 |
| Cost model | 1bp per side (position-change notional) | Fees $429.13 total on 20 orders; slippage/fill model = LEAN default, market orders converted to MarketOnOpen |
| EEM buy-and-hold leg | Sharpe -0.35, total return -31.5% (over Jarvis's OOS window only) | **Now run explicitly** — total return +58.8504%, max drawdown -39.1292%, final value $158,850.38 (over the full 15-year LEAN period) |


This difference in *scored window* (walk-forward OOS tails vs. full
continuous period) is the single most important methodological gap in
this run and is carried through nearly every comparison below — this
LEAN run does **not** yet implement Phase 3 of
`docs/QUANTCONNECT_LEAN_EEM_VALIDATION_SPEC.md` (the walk-forward-OOS
reconstruction). It corresponds to Phase 2 (full-period backtest), which
the spec explicitly labeled a **debugging checkpoint, not the primary
comparison number** (Spec Section 6, Section 18).

---

## 1. Strategy rule equivalence

The LEAN run summary states the strategy as "EEM rsi_revert(14,30/70)" —
the same RSI window and thresholds as the Jarvis approved candidate.
However, per Spec Section 4 and Manual Check #1
(`docs/QUANTCONNECT_LEAN_EEM_VALIDATION_SPEC.md`), the exact **exit**
behavior of Jarvis's `strategy_rsi_revert` was flagged as ambiguous and
requiring empirical confirmation before trusting any LEAN mirror's exit
logic matches it. Nothing in the numbers supplied with this run (no
trade log, no equity curve) confirms whether the LEAN implementation's
exit rule matches Jarvis's actual behavior bar-for-bar. The **order
count evidence below (Section 7) suggests it likely does not fully
match** — this is flagged as unresolved, not assumed one way or the
other.

**Equivalence status: PARTIALLY CONFIRMED, NOT FULLY VERIFIED.** The RSI
formula, window, and threshold values appear equivalent by design intent;
the exit-timing mechanics have not been independently verified against
Jarvis's actual signal/position series (Spec Manual Check #1 has not yet
been performed as part of this run).

## 2. Date range equivalence

**Loaded range matches (2010-01-01 to 2025-01-01). Scored range does
not.** Jarvis's approved Sharpe/drawdown/trade-count figures come from
only the concatenated 30%-OOS tails of 5 sequential walk-forward windows
— roughly 4.5 years of trading days out of the 15 loaded, not the full
15-year period. This LEAN run scores the **entire** 15-year period
continuously. This means the two headline result sets are not directly
comparable on a like-for-like basis yet; the LEAN full-period result is
a different (and looser) measurement than the Jarvis number it is being
compared against.

## 3. Data source differences

Jarvis's EEM daily bars come from `yfinance` (`auto_adjust=True`) via
`edge_hunting/data_loader.py`. The LEAN mirror uses LEAN's own EEM data
provider (source/vendor unspecified in the refined run summary). This
gap is now **partially closed**: the refined run adds an explicit LEAN
EEM buy-and-hold leg (total return +58.8504%, max drawdown -39.1292%,
final value $158,850.38, over the full 2010–2025 LEAN period), which can
be compared directly against Jarvis's own EEM buy-and-hold figures
(`reports/edge_hunting/benchmark_comparison_report.md`: Sharpe -0.35,
total return -31.5%, max drawdown -45.2%, over Jarvis's shorter OOS-only
window).

**These two buy-and-hold numbers are directionally consistent but not
numerically close, and this is expected, not alarming, given they cover
different windows:** Jarvis's -31.5% buy-and-hold figure is measured only
over the ~4.5-year concatenated OOS tails (a period Jarvis's own report
independently describes as "EEM had a rough stretch"), while LEAN's
+58.8504% buy-and-hold figure is measured over the full ~15-year period,
which includes both that rough stretch and EEM's broader multi-year
recovery/growth outside of it. A period that is a small negative-return
slice of a longer, larger positive-return period is not evidence of a
data-vendor discrepancy by itself — **this comparison remains
inconclusive on the data-source question specifically** because the two
buy-and-hold legs still do not share a common scored window. A true
apples-to-apples data-source check still requires running LEAN's EEM
buy-and-hold leg restricted to the same OOS-tail dates Jarvis used
(Recommended Next Step #1, revised below), not just the full-period
leg now available. The previously identified gap — that Alpha/Beta in
the initial run were computed against an unconfirmed, non-EEM benchmark
— is now resolved for the total-return/drawdown metrics (Section 7/8),
but remains open for Alpha/Beta specifically, which were not restated in
the refined run summary.


## 4. Order timing differences

Both the approved Spec (Section 9/10) and this run's own supplied
warning are consistent and mutually confirming: **"market orders
submitted while the market is closed were converted into
MarketOnOpen orders for next open execution."** This matches the Spec's
anticipated Section 10 disclosure exactly — LEAN's honest daily-
resolution convention fills at the next bar's open, not at the same
bar's close the way Jarvis's vectorized `position[t] = signal[t-1]` /
close-to-close return model implicitly assumes. This is a **disclosed,
expected, non-eliminable timing difference**, not a bug — but it does
mean every trade in the LEAN run is filled with a small, real timing
offset relative to what the Jarvis number assumes, contributing
(probably modestly) to the divergence in Sections 7–8 below.

## 5. Transaction cost differences

Jarvis: 1bp of position-change notional per side (`DEFAULT_COST_BPS =
1.0` in `backtest_engine.py`), no separate slippage. LEAN: $429.13 total
fees across 20 orders on a $100,000-to-$185,863 equity path — averaging
roughly $21.50 per order, which on notional trade sizes in this range is
broadly consistent with a small-bps-style cost, but the run summary does
not break out fees as a bps rate, and does not confirm whether an
additional slippage model (beyond the fee) was active or zeroed, per
Spec Section 11's explicit requirement to disable/zero any stacking
slippage model. **This cannot be confirmed as matching the 1bp
assumption without the LEAN project's fee-model configuration being
inspected directly** (Spec Manual Check #4) — flagged as unverified, not
assumed compliant.

## 6. Position sizing differences

Jarvis: unit-signed, 100%-notional long/short/flat (`position ∈
{-1,0,+1}`), no volatility scaling. The LEAN run's low reported
**portfolio turnover (0.37%)** alongside only 20 total orders over 15
years is consistent with an infrequently-flipping, large-notional
position style broadly in the spirit of the Jarvis sizing assumption,
but the run summary doesn't confirm the LEAN algorithm actually
allocates a full 100% of equity per trade (versus some other fixed
fraction) — this should be confirmed against the actual LEAN algorithm
code (Spec Section 5 requirement), not inferred from turnover alone.

## 7. Return, Sharpe, and drawdown differences

| Metric | Jarvis (OOS tails, ~4.5yr) | LEAN strategy (full period, ~15yr) | LEAN EEM buy-and-hold (full period, ~15yr) |
|---|---|---|---|
| Sharpe | +0.65 | +0.158 | not separately reported in refined summary |
| Total return | +15.8% | +85.8630% | +58.8504% |
| CAGR | not directly reported for OOS-only slice | +4.216% (initial run) | not reported |
| Max drawdown | -9.9% | -29.2535% | -39.1292% |
| Final portfolio value ($100k start) | n/a (% terms only) | $185,863.00 | $158,850.38 |
| Trade/order count | ~55 (over ~4.5yr OOS) | 20 filled orders (~10 round trips, over ~15yr) | 1 (buy-and-hold) |
| Exposure | not directly reported (see `exposure` metric in `backtest_engine.run_backtest`) | 34.25% (1,299 of 3,793 days) | 100% (by definition) |
| Win rate | not explicitly reported per-trade in the cited Jarvis docs at this granularity | 80% | n/a |
| Bootstrap worst-case DD | -13.1% (SOLID) | not run | not run |

**The refined run's key new finding: the LEAN RSI strategy beats LEAN's
own EEM buy-and-hold leg on both total return (+85.8630% vs +58.8504%)
and max drawdown (-29.2535% vs -39.1292%), over the identical full
2010–2025 LEAN period, using the identical LEAN data feed, fee model,
and fill assumptions.** This is the single most important new result in
this refined run: it directly answers the specific comparison Jarvis's
own approval basis (`docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
requirement #5 — beat EEM buy-and-hold on both return and drawdown) asks
for, on LEAN's own terms, rather than relying on an unconfirmed
cross-vendor comparison (as the initial run required). Sharpe (+0.158)
remains low in absolute terms and well below the Jarvis OOS figure
(+0.65) — see Section 9/10 for why this gap persists and should not be
over-read either way.

**Two caveats remain, and must not be glossed over just because the
buy-and-hold comparison now works cleanly:** (a) this is still the
full-period comparison (Section 2), not the walk-forward-OOS
reconstruction that is Jarvis's actual approved-metric methodology, so
"beats buy-and-hold" here is a LEAN-native result, not yet a strict
apples-to-apples match to the Jarvis number; and (b) the order-count gap
(20 orders / ~10 round trips over 15 years in LEAN vs. ~55 trades over
~4.5 OOS years in Jarvis) is still present and unexplained (Section 9).


## 8. Whether LEAN directionally confirms Jarvis

**Yes, and more concretely than in the initial run.** The refined LEAN
mirror, run on an independent engine (QuantConnect/LEAN) with an
independent data pipeline and independent order/fill simulation, now
directly confirms the specific comparison Jarvis's own approval basis
rests on: **the RSI strategy beats LEAN's own EEM buy-and-hold on both
total return (+85.8630% vs +58.8504%) and max drawdown (-29.2535% vs
-39.1292%) over the identical 15-year period, data feed, and cost
model.** This is a materially stronger form of directional confirmation
than "the rule is merely net profitable in isolation" (the initial
run's finding) — it is now "the rule outperforms passively holding the
same asset," which is the actual claim under test. Combined with a
favorable win/loss shape (80% win rate, 4.40 profit/loss ratio), this is
real, non-trivial evidence that **EEM RSI(14,30/70) mean reversion can
make money, and can beat buy-and-hold, under a fully independent
engine.**


## 9. Whether the mismatch is explainable

**Mostly yes, for the return/drawdown comparison — the buy-and-hold
result now gives that gap a coherent, non-alarming explanation. The
Sharpe gap and order-count gap remain only partially explained.**

**Return/drawdown outperformance vs. buy-and-hold (Section 7/8): well
explained.** The strategy beating LEAN's own EEM buy-and-hold on both
return and drawdown, in the same LEAN run with the same data feed and
cost model, is a clean, internally consistent result — there is no
cross-vendor ambiguity left in *this specific* comparison, because both
legs come from the same engine and the same underlying price series.

**Sharpe gap (+0.158 LEAN vs. +0.65 Jarvis OOS): still only partially
explained.** Three candidate explanations remain, none fully isolated:

1. **Window-length/scope mismatch (Section 2).** Comparing a ~4.5-year
   OOS-only slice against a ~15-year full-period run is not
   apples-to-apples by design — this alone would be expected to produce
   a lower, noisier Sharpe in the LEAN full-period number, independent
   of any implementation difference. This is the most likely single
   largest contributor and is a benign, expected effect of comparing
   different-length windows, not a red flag.
2. **Order-timing/fill difference (Section 4).** The disclosed
   MarketOnOpen conversion is a real, expected, small per-trade drag
   relative to Jarvis's close-to-close assumption, but is unlikely on
   its own to explain the full gap.
3. **Possible exit-rule implementation nuance (Sections 1, 7).** The
   order-count difference (20 orders / ~10 round trips over 15 years in
   LEAN vs. ~55 trades over ~4.5 OOS years in Jarvis) remains
   unconfirmed as either a genuine implementation mismatch or simply a
   consequence of the much longer, calmer full-period window producing
   fewer RSI threshold crossings on average. This has not been resolved
   with a trade log or signal-series inspection (Manual Check #1) and
   remains the single most important open technical question, but it no
   longer casts doubt on the *return/drawdown* finding in Section 7/8,
   which stands on its own within the LEAN-only comparison.

**None of the remaining Sharpe-gap explanations has been ruled in or
ruled out with hard evidence.** But the previously largest open item —
the missing benchmark leg — is now resolved, which materially changes
the overall explainability picture for the better.

## 10. Whether Jarvis confidence should increase, stay the same, or decrease

**Confidence should increase — meaningfully more than in the initial
run, though still not to the point of treating this as a fully resolved,
live-ready validation.**

Reasons confidence should now increase more than "modestly":
- The refined run closes the single largest gap flagged in the initial
  version of this report (Section 3/9): there is now a clean,
  same-engine, same-data, same-cost-model comparison showing the
  strategy **beats EEM buy-and-hold on both total return and max
  drawdown** — precisely the comparison Jarvis's own approval
  requirement #5 is built on. This is a materially stronger result than
  "the strategy is merely profitable in isolation."
- This finding was produced independently — different engine, different
  data vendor, different order/fill simulation, different codebase —
  and still lands on the same qualitative conclusion Jarvis's own
  `benchmark_comparison_report.md` reached: EEM RSI(14,30/70)
  mean-reversion outperforms passively holding EEM.
- The favorable win/loss shape (80% win rate, 4.40 profit/loss ratio) is
  additional, consistent, non-suspicious corroborating detail.

Reasons this should still not be treated as full validation or a
live-readiness signal:
- **Sharpe is still low (+0.158)** relative to the Jarvis-reported
  +0.65, and on its own would not clear Jarvis's own funnel
  (`FunnelThresholds.min_oos_sharpe = 0.5`) if evaluated as a fresh
  candidate. A strategy can beat buy-and-hold on return/drawdown while
  still having a mediocre absolute risk-adjusted profile — both things
  are true here simultaneously and neither cancels out the other.
- **Trade count is small** (20 orders / ~10 round trips over 15 years),
  which limits the statistical confidence that can be placed in any of
  the LEAN run's summary statistics — a strategy trading only ~10 times
  over 15 years has a small effective sample size for a win-rate or
  Sharpe estimate, regardless of how favorable the sample looks.
- **Data-source validation is still pending** in the strict sense
  described in Section 3: the LEAN buy-and-hold leg was compared against
  Jarvis's buy-and-hold leg only qualitatively (different windows), not
  on the same OOS-tail dates — a true apples-to-apples data-vendor
  cross-check (Recommended Next Step #1, revised) has not yet been done.
- The walk-forward-OOS reconstruction (Spec Phase 3) — the methodology
  that actually matches how Jarvis's approved numbers were computed —
  still has not been run in LEAN; this remains a full-period comparison.

**Net position: this result meaningfully increases confidence in the
underlying EEM RSI mean-reversion effect being real and not a
Jarvis-specific backtest artifact, and it directly and successfully
answers the specific buy-and-hold comparison the original approval was
based on. It does not, however, resolve every open question (low
absolute Sharpe, small trade count, pending strict data-source
cross-check), and it does not make the candidate ready for live capital.
The appropriate next step is to treat this candidate as now eligible
for paper-trading gate design work (i.e., defining the specific
promotion criteria, monitoring, and kill-switch conditions a paper-test
would need before real capital is ever considered) — not for live
deployment, and not yet for skipping straight to paper trading itself
without that gate design being completed first. No change to the
candidate's classification in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
is made by this report; that remains a separate, later decision.**


---

## Recommended next step

**Item 1 below (explicit EEM buy-and-hold LEAN leg) is now DONE** as of
the refined run — see Sections 3/7/8. The remaining gaps, in priority
order:

1. ~~Explicit EEM buy-and-hold LEAN leg (Spec Phase 1)~~ — **complete.**
   The refined run added this leg in the same LEAN project/engine, same
   date range, same fee assumptions, directly enabling the Section 7/8
   outperformance finding. Remaining sub-item: restrict this leg to the
   same OOS-tail dates Jarvis used, for a true apples-to-apples
   data-vendor cross-check (Section 3) — this specific narrower
   comparison has not yet been done.
2. **Equity curve export** from the LEAN run, to inspect the actual
   drawdown path and compare its shape/timing against what would be
   expected from Jarvis's own OOS equity curve.
3. **Trade log export** from the LEAN run, to resolve the order-count
   discrepancy (Section 7/9) — specifically, to check each trade's entry
   RSI value, exit RSI value, and holding period against what Jarvis's
   actual signal/position series would imply for the same dates (Spec
   Manual Check #1).
4. **Closer Jarvis/LEAN methodology alignment**, specifically:
   implementing the 5-window walk-forward-OOS reconstruction (Spec Phase
   3) rather than only the full-period run, so the primary comparison
   number is scored on a like-for-like basis with the actual Jarvis
   approved figures, not the full 15-year period.
5. **Paper-trading gate design** (new, given the increased confidence
   from this refined run) — before any paper-trading run is actually
   started, define the specific promotion criteria, monitoring
   thresholds, and kill-switch/rollback conditions the candidate would
   need to satisfy. This is design work only — it does not itself start
   paper trading, and should be treated as a distinct, subsequent task
   from this comparison report.

Only after items 2–4 are addressed should this comparison be revisited
for a fuller confidence read; item 5 (gate design) can proceed in
parallel since it does not depend on further backtest results. Per
`docs/EEM_EXPANSION_DECISION_MEMO.md`, a Norgate (or equivalent) data
cross-check also remains a separate, additional recommended step beyond
the LEAN mirror itself.


---

## Explicit scope boundary

- This is a comparison and interpretation report only. No strategy code
  in `edge_hunting/` or the LEAN project was edited to produce it.
- No parameter was tuned, in either Jarvis or LEAN, to produce this
  report.
- No Jarvis backtest was re-run; all Jarvis figures are taken from
  existing, previously-generated report files.
- No candidate's classification in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  was changed by this report.
- Paper trading and live trading remain disabled in both systems;
  nothing in this report authorizes either.
