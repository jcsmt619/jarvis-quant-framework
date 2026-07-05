# QuantConnect/LEAN Mirror Comparison — EEM RSI Mean-Reversion Candidate

**Status: COMPARISON REPORT ONLY. No strategy code was edited. No
parameters were tuned. No Jarvis backtest was re-run — all Jarvis figures
below are taken as-is from existing report files. No paper or live
trading was enabled in either Jarvis or LEAN. This document interprets
one already-completed LEAN Docker backtest run against already-existing
Jarvis reports; it does not authorize any further action beyond what is
recommended in Section 10.**

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
provider (source/vendor unspecified in the run summary provided). Per
Spec Section 15 (failure case #1) and Manual Check #3, a data-vendor
discrepancy check requires an explicit **EEM buy-and-hold-only** LEAN run
compared against Jarvis's own EEM buy-and-hold figures
(`reports/edge_hunting/benchmark_comparison_report.md`: Sharpe -0.35,
total return -31.5% over the OOS window). **This run summary does not
include a LEAN EEM buy-and-hold leg at all** — the reported Alpha
(-0.025) and Beta (0.737) are computed against LEAN's own default
benchmark (not disclosed in the summary, but conventionally SPY unless
configured otherwise), not against EEM buy-and-hold. This is a
meaningful gap: **we cannot yet distinguish "the strategy beats EEM
buy-and-hold" (the actual Jarvis approval basis) from "the strategy has
negative alpha/moderate beta to some other, unspecified benchmark."**
This is the single largest open item carried into Section 10's
recommendation.

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

| Metric | Jarvis (OOS tails, ~4.5yr) | LEAN (full period, ~15yr) | Directionally aligned? |
|---|---|---|---|
| Sharpe | +0.65 | +0.158 | Yes (both positive) but **LEAN is much lower** |
| Total return | +15.8% | +85.863% | Not comparable (different window lengths — LEAN's is over 3.3x the time) |
| CAGR | not directly reported for OOS-only slice | +4.216% | N/A |
| Max drawdown | -9.9% | -29.300% | Both negative, but **LEAN's is ~3x deeper** |
| Trade/order count | ~55 (over ~4.5yr OOS) | 20 (over ~15yr full period) | **Notably lower trade frequency in LEAN** given the much longer window — this is the strongest single piece of evidence that the LEAN exit-rule implementation (Section 1) may not exactly match Jarvis's actual signal behavior, and should be investigated via Manual Check #1 before drawing further conclusions from trade-level statistics |
| Win rate | not explicitly reported per-trade in the cited Jarvis docs at this granularity | 80% | N/A (Jarvis win-rate convention is per contiguous position-segment, per `backtest_engine._win_rate`; not confirmed the LEAN 80% figure uses the same segment definition) |
| Bootstrap worst-case DD | -13.1% (SOLID) | not run | LEAN mirror has not yet reproduced the bootstrap stress test |

**Both Sharpe and total return are positive in both systems — the
directional sign of the edge agrees.** But the *magnitude* comparison is
weak for two compounding reasons that must not be conflated: (a) the
scored windows are different lengths and different date sub-ranges
(Section 2), so a lower full-period Sharpe is *expected* even under a
perfectly faithful mirror, simply because the full 15-year period
includes stretches (including the in-sample portions Jarvis's walk-
forward explicitly excludes from its OOS score) that were never claimed
to perform as well; and (b) the order-count and drawdown gap (20 orders,
-29.3% DD in LEAN vs. ~55 trades, -9.9% DD in Jarvis) is large enough
that it may also reflect a genuine implementation difference in exit
timing (Section 1), not just a window-length effect. **These two
possible explanations have not yet been separated from each other in
this run.**

## 8. Whether LEAN directionally confirms Jarvis

**Yes, directionally, at the level of "does this rule make money at all
under an independent engine" — but not yet at the level of "does it beat
the right benchmark by the right margin."** The LEAN mirror, run on an
independent engine (QuantConnect/LEAN) with an independent data pipeline
and independent order/fill simulation, produced a strategy that: (a) is
net profitable over the full 15-year window (+85.9%, CAGR +4.2%), (b)
has a positive (if low) Sharpe ratio (+0.158), and (c) shows a favorable
win/loss profile (80% win rate, 4.40 profit/loss ratio). This is
consistent with — not contradictory to — the core Jarvis claim that EEM
RSI(14,30/70) mean reversion is not purely noise. **EEM RSI mean
reversion can make money under an independent engine.** That is a real,
meaningful, positive data point.

## 9. Whether the mismatch is explainable

**Partially, and only qualitatively so far — not yet quantitatively
resolved.** Three candidate explanations for the Sharpe/drawdown gap have
been identified, but none has been isolated as *the* cause:

1. **Window-length/scope mismatch (Section 2).** Comparing a ~4.5-year
   OOS-only slice against a ~15-year full-period run is not
   apples-to-apples by design — this alone would be expected to produce
   a lower, noisier Sharpe and deeper drawdown in the LEAN full-period
   number, independent of any implementation difference.
2. **Order-timing/fill difference (Section 4).** The disclosed
   MarketOnOpen conversion is a real, expected, small per-trade drag
   relative to Jarvis's close-to-close assumption, but is unlikely on
   its own to explain a gap this large (Sharpe 0.65 vs 0.16).
3. **Possible exit-rule implementation mismatch (Sections 1, 7).** The
   order-count discrepancy (55 trades in ~4.5 OOS years vs. only 20
   orders in ~15 full years) is the most concerning unexplained finding
   in this run and is the leading candidate explanation for at least
   part of the gap — but this has not been confirmed, because Manual
   Check #1 (dumping and inspecting Jarvis's actual signal/position
   series) has not yet been performed, and no LEAN trade log or equity
   curve was provided with this run to inspect on the LEAN side either.
4. **Benchmark mismatch (Section 3).** The reported Alpha/Beta are
   against an unconfirmed, likely non-EEM benchmark, so they cannot yet
   be used to explain or refute anything about the EEM-buy-and-hold
   comparison that is the actual basis of Jarvis's approval.

**None of these four explanations has been ruled in or ruled out with
evidence beyond the summary statistics supplied.** This is the core
reason this run should be read as encouraging but incomplete, not as a
resolved validation.

## 10. Whether Jarvis confidence should increase, stay the same, or decrease

**Confidence should increase modestly — not substantially, and not to
the point of changing the candidate's approval status.**

Reasons to increase confidence, even modestly:
- An independent engine, independent data vendor, and independent
  order/fill simulation, implementing (nominally) the same rule, produced
  a net-profitable, positive-Sharpe result over 15 years on EEM — this is
  a real, non-trivial piece of corroborating evidence that the
  RSI-mean-reversion effect on EEM is not an artifact unique to this
  codebase's own backtest engine or to `yfinance`'s specific price
  history.
- The win-rate/profit-loss-ratio shape (80% win rate, 4.40 P/L ratio) is
  qualitatively consistent with a mean-reversion strategy that takes
  many small losses and occasional large wins snapping back from
  extremes — a sensible, non-suspicious shape for this strategy type.

Reasons this should not be read as a strong or full confirmation:
- **Sharpe is low (+0.158)** relative to the Jarvis-reported +0.65, and
  the Probabilistic Sharpe Ratio of 0.045% (essentially ~0) indicates
  LEAN's own statistical confidence that the *true* Sharpe is
  meaningfully above zero is itself very weak in this particular run —
  this number on its own would not clear Jarvis's own funnel
  (`FunnelThresholds.min_oos_sharpe = 0.5`) if it were being evaluated
  as a fresh candidate.
- **Alpha is negative (-0.025) against whatever benchmark LEAN used by
  default** — and critically, that benchmark has not been confirmed to
  be EEM buy-and-hold, which is the actual, correct comparison per
  Jarvis's own approval requirement #5. A negative alpha against an
  unconfirmed benchmark is not evidence against the strategy, but it is
  also not the specific evidence needed to support it.
- **Order timing and fill assumptions differ** from Jarvis's model in a
  disclosed, understood, but unquantified way (Section 4), and the
  order-count discrepancy (Section 7/9) raises a real, unresolved
  question about whether the LEAN implementation's exit logic is even
  fully faithful to the Jarvis rule it's meant to mirror.
- This run corresponds to Spec Phase 2 (full-period sanity check), which
  the approved spec explicitly said should **not** be treated as the
  primary comparison number (Spec Section 6, Section 18) — Phase 1
  (EEM buy-and-hold benchmark leg) and Phase 3 (walk-forward-OOS
  reconstruction) have not yet been run.

**Net position: this result is a genuine, modestly positive data point —
"an independent backtest of a nominally-similar rule doesn't blow up or
lose money" is worth something — but it is well short of the
apples-to-apples, benchmark-anchored comparison needed to move the EEM
`rsi_revert(14,30/70)` candidate beyond its current
`APPROVED_FOR_PAPER_TEST` status, and well short of resolving the open
questions raised in `docs/EEM_EXPANSION_DECISION_MEMO.md`'s Section 10
(the original recommendation for independent validation). No change to
the candidate's classification in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
is warranted based on this run alone.**

---

## Recommended next step

Run a **stricter LEAN mirror** that closes the specific gaps identified
above, in priority order:

1. **Explicit EEM buy-and-hold LEAN leg** (Spec Phase 1) — run in the
   same LEAN project/engine, same date range, same fee assumptions, and
   report its own Sharpe/return/drawdown directly against Jarvis's EEM
   buy-and-hold figures (Sharpe -0.35, total return -31.5%) using the
   tight tolerance band in Spec Section 14. This is the cheapest, single
   highest-value next step and resolves the Section 3/9 benchmark
   ambiguity directly.
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

Only after these four items are addressed should this comparison be
revisited for a stronger confidence read — and even then, per
`docs/EEM_EXPANSION_DECISION_MEMO.md`, a Norgate (or equivalent)
data cross-check remains a separate, additional recommended step beyond
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
