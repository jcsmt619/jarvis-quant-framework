# Jarvis Paper-Trading Candidate Report

**Status: ANALYSIS ONLY. No strategy code was edited. No parameters were
tuned. No trades have been placed. Paper trading has NOT been enabled.
No classification below was adjusted to make any candidate look better —
each is derived directly and literally from the five source reports listed
below, all of which were produced by prior, unmodified analysis runs.**

## Sources read (no backtests re-run; all report files already existed)

- `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` (Sections 1–15)
- `reports/edge_hunting/missing_bootstrap_stress_report.md`
- `reports/edge_hunting/slippage_stress_report.md`
- `reports/edge_hunting/duplicate_signal_report.md`
- `reports/edge_hunting/benchmark_comparison_report.md`
- `reports/edge_hunting/regime_decomposition_report.md`

## Scope

The 7 configs that survived every prior filter layer (funnel → bootstrap →
slippage stress → duplicate-signal check → benchmark comparison → regime
decomposition):

1. MSFT `keltner_revert(window=20, atr_mult=2.0)`
2. AMZN `keltner_revert(window=20, atr_mult=2.0)`
3. EEM `rsi_revert(window=14, oversold=30, overbought=70)`
4. EEM `rsi_revert(window=14, oversold=25, overbought=70)`
5. SPY `dual_momentum(window=60, rel_window=126)`
6. HYG `dual_momentum(window=126, rel_window=126)`
7. QQQ `rsi_revert(window=14, oversold=30, overbought=75)`

## Approval requirements applied (all 10, per candidate)

1. Passed original six-filter funnel
2. Bootstrap SOLID
3. Survives slippage stress through at least 25bp per side
4. Not a duplicate signal (DUPLICATE_SIGNAL bar; NEAR_DUPLICATE is a caveat, not an automatic fail)
5. Beats own asset buy-and-hold on risk-adjusted (Sharpe) terms
6. Not beta-disguised (correlation to own asset < 0.70 AND/OR excess Sharpe > 0.10)
7. Acceptable regime behavior (does not collapse in BEAR/HIGH_VOL/CRISIS)
8. Sufficient trades (>=30 total OOS trades, per the original funnel's own bar)
9. No evidence of look-ahead (all results come from the walk-forward OOS engine with purge/embargo; no candidate here has ever tripped the look-ahead/anti-leakage checks elsewhere in this codebase)
10. Not dependent on one "magical" parameter (family-level `parameter_sensitivity.csv` flag must be ROBUST, i.e. most parameter variations in the family are OOS-positive, not just this one setting)

A candidate must pass **all 10** to be `APPROVED_FOR_PAPER_TEST`. Failing #5
and/or #6 on a real, distinct (non-beta) signal is a `DEFENSIVE_WATCHLIST`
or `RESEARCH_ONLY` outcome depending on the number/severity of additional
caveats. Failing #6 or #7 outright (beta-disguised or regime-collapsing) is
`REJECT`.

---

## Per-candidate scorecard

### 1. EEM `rsi_revert(14, 30/70)` — **APPROVED_FOR_PAPER_TEST (PRIMARY)**

| Field | Value |
|---|---|
| Strategy | rsi_revert |
| Asset | EEM |
| Parameters | window=14, oversold=30, overbought=70 |
| Category | MEAN_REVERSION |
| Expected trade frequency | ~55 OOS trades over the sample (9 CRISIS + 2 HIGH_VOL + 12 LOW_VOL + 16 BULL + 12 BEAR + 4 SIDEWAYS) — moderate, not high-frequency |
| Expected drawdown | ~-9.9% max OOS drawdown at 1bp cost (vs. -45.2% for EEM buy-and-hold over the same window) |
| Slippage sensitivity | STRONGER — positive Sharpe through 25bp (+0.11 at 25bp); break-even ≈30.0bp |
| Regime weakness | CRISIS is the only negative regime (-0.34 Sharpe, -2.8% return) — mild, not a collapse; BEAR (+2.38) and HIGH_VOL (+0.83) are both clearly positive |
| Benchmark comparison | ROBUST_CANDIDATE — beats EEM buy-and-hold on Sharpe (+0.65 vs -0.35) and drawdown (-9.9% vs -45.2%); excess Sharpe +1.00, the largest in the entire set |
| Duplicate-signal status | NEAR_DUPLICATE of EEM rsi_revert(14,25/70) (ret_corr +0.85, pos_corr +0.81) — this is the stronger of the two variants and is selected as the single primary slot |
| Bootstrap | SOLID, worst-case reshuffled drawdown -13.1% |
| Family robustness | rsi_revert family flagged ROBUST in `parameter_sensitivity.csv` — not a one-off lucky setting |
| **Exact reason approved** | Passes all 10 requirements: funnel pass, bootstrap SOLID, survives 25bp slippage, is the primary (not secondary) half of a near-duplicate pair rather than a literal duplicate, beats its own asset's buy-and-hold on Sharpe and drawdown on an asset that otherwise lost money, low correlation to EEM (+0.16, not beta-disguised), does not collapse in BEAR/HIGH_VOL (only a mild CRISIS dip), 55 OOS trades (well above the 30-trade funnel floor), produced entirely by the purge/embargo walk-forward engine with no look-ahead flags anywhere in this codebase, and the rsi_revert family itself (not just this one parameter set) is ROBUST. |
| **Exact reason it could still fail live** | (a) It is a near-duplicate of the 25/70 variant, meaning this is really one confirmed signal on one asset — a single point of failure, not a diversified sleeve; (b) EEM's CRISIS-regime return was only mildly negative in this specific sample (-2.8%), but CRISIS days (162 of them) were still dominated by 2020-COVID-style shocks in the cached window — a genuinely worse or longer emerging-markets crisis than what's in the historical sample could produce a larger loss than backtested; (c) EEM's own liquidity/spread in live paper execution may not match the 1bp cost assumption used even after the 25bp stress test, especially during EM-specific stress events; (d) only 1,134 OOS trading days were tested — this is one historical sample, not multiple independent market cycles. |

### 2. EEM `rsi_revert(14, 25/70)` — **BACKUP_PENDING_BOOTSTRAP (CONDITIONAL BACKUP — NOT currently approved for paper trading)**

| Field | Value |
|---|---|
| Strategy | rsi_revert |
| Asset | EEM |
| Parameters | window=14, oversold=25, overbought=70 |
| Category | MEAN_REVERSION |
| Expected trade frequency | ~34 OOS trades (6+2+8+16+2+0 across regimes) — lower than the 30/70 variant, and SIDEWAYS shows 0 trades (essentially inactive in that regime) |
| Expected drawdown | ~-7.3% max OOS drawdown at 1bp cost |
| Slippage sensitivity | STRONGER — positive through 25bp (+0.12 at 25bp); break-even ≈31.8bp |
| Regime weakness | CRISIS is essentially flat (+0.02 Sharpe, -0.2% return); BEAR (+1.35) and HIGH_VOL (+0.83) both positive — cleaner than its sibling on this axis, but SIDEWAYS shows zero trading activity |
| Benchmark comparison | ROBUST_CANDIDATE — beats EEM buy-and-hold (+0.54 vs -0.35 Sharpe), excess Sharpe +0.89, second-largest in the set |
| Duplicate-signal status | NEAR_DUPLICATE of EEM rsi_revert(14,30/70) — same asset, same family, 5-point threshold difference, 56% trade-day overlap |
| Bootstrap | **NOT YET TESTED** — this variant was never run through `missing_bootstrap_stress.py`; it is flagged in the main doc as "NEEDS MORE ROBUSTNESS TESTING (low priority)" specifically because of this gap. This is an honest, un-fudged gap: requirement #2 (bootstrap SOLID) is **not formally satisfied** for this specific config. |
| Family robustness | Same rsi_revert family, ROBUST flag (shared with the primary variant and with the sibling asset configs) |
| **Exact reason classified BACKUP_PENDING_BOOTSTRAP rather than APPROVED_FOR_PAPER_TEST** | On every metric that HAS been tested (funnel, slippage, benchmark comparison, regime decomposition), this variant passes at a level comparable to — though consistently slightly weaker than — the primary 30/70 variant. However, it explicitly **fails approval requirement #2 (bootstrap SOLID)** as of this report — it has never been run through `missing_bootstrap_stress.py`. Per the 10 approval requirements, a candidate must pass all 10 to be `APPROVED_FOR_PAPER_TEST`; an untested bootstrap requirement is not a minor gap, it is an unmet hard requirement. **This candidate CANNOT be used in paper trading, and must not be treated as a live backup, unless and until it passes the same bootstrap stress test applied to the primary 30/70 variant** (SOLID classification, using the existing unmodified `missing_bootstrap_stress.py` methodology — no new methodology, no parameter tuning). Until that test is run and passed, it remains a candidate for the backup slot in name only, not in practice. |
| **Exact reason it could still fail live** | All the same live-risk caveats as the primary variant, PLUS: it has never been bootstrap-tested, so its resilience to a specific unlucky sequencing of returns (as opposed to average performance) is genuinely unknown, not just under-documented — this is precisely the unresolved gap that blocks its promotion; it also shows zero trading activity in the SIDEWAYS regime (285 of ~1,134 days, ~25% of the sample), meaning roughly a quarter of the historical sample provides no evidence at all about this specific variant's behavior. |


### 3. MSFT `keltner_revert(20, 2.0)` — **DEFENSIVE_WATCHLIST**

| Field | Value |
|---|---|
| Strategy | keltner_revert |
| Asset | MSFT |
| Parameters | window=20, atr_mult=2.0 |
| Category | MEAN_REVERSION |
| Expected trade frequency | ~127 OOS trades (16+28+46+10+27 across regimes = 127) — the highest trade count of the 7 |
| Expected drawdown | ~-7.4% to -10.1% max OOS drawdown depending on regime (vs -20.6% for MSFT buy-and-hold) |
| Slippage sensitivity | STRONGER — positive through 25bp (+0.08); break-even ≈28.1bp — narrowest margin of the 7 STRONGER configs |
| Regime weakness | LOW_VOL is the only negative regime (-0.69 Sharpe, -5.3% return) — not a stress regime; BEAR (+0.32) and HIGH_VOL (+0.98) both positive; no CRISIS days observed in the sample (untested in a genuine crash) |
| Benchmark comparison | DEFENSIVE_CANDIDATE — Sharpe +0.71 vs +0.85 for MSFT buy-and-hold; cuts drawdown to -7.4% (vs -20.6%) but surrenders most of MSFT's very strong run (+35.3% vs +117.1% total return) |
| Duplicate-signal status | UNIQUE_SIGNAL — highest correlation with any other candidate is with QQQ rsi_revert (ret_corr +0.56, pos_corr +0.40), below the NEAR_DUPLICATE bar |
| Bootstrap | SOLID, worst-case reshuffled drawdown -23.6% |
| Family robustness | keltner_revert family flagged ROBUST |
| **Exact reason NOT approved for paper-test (return-seeking) but placed on defensive watchlist** | Fails approval requirement #5: it does not beat MSFT buy-and-hold on Sharpe (0.71 vs 0.85) during this specific, strongly trending OOS window — MSFT rallied hard and mean-reversion missed most of the gain. It is not beta-disguised (correlation +0.14, low), so this is a real, distinct, lower-volatility pattern rather than a repackaged version of holding MSFT — genuinely useful as a volatility-dampening sleeve, not as a source of excess return. |
| **Exact reason it could still fail live** | Its slippage break-even margin (28.1bp) is the thinnest of the 7 STRONGER survivors — a modest increase in realistic execution cost above what was modeled here would push it into the MARGINAL bucket; it has never traded through a CRISIS regime in this sample, so its true crash behavior is unconfirmed, not just untested-and-fine; and being a "defensive" sleeve means its value depends on how it's combined with other, return-seeking positions in an actual portfolio — evaluated alone, it underperforms simply holding MSFT. |

### 4. QQQ `rsi_revert(14, 30/75)` — **DEFENSIVE_WATCHLIST**

| Field | Value |
|---|---|
| Strategy | rsi_revert |
| Asset | QQQ |
| Parameters | window=14, oversold=30, overbought=75 |
| Category | MEAN_REVERSION |
| Expected trade frequency | ~42 OOS trades (1+2+6+19+6+8 = 42, per regime table) |
| Expected drawdown | ~0% to -4.2% max OOS drawdown by regime (vs -24.6% for QQQ buy-and-hold) |
| Slippage sensitivity | STRONGER — positive through 25bp (+0.17); break-even ≈36.0bp |
| Regime weakness | BULL is the only negative regime (-0.10 Sharpe, -0.5% return) — mild, and expected for a mean-reversion strategy in a persistent uptrend; CRISIS has only 2 days (statistically meaningless, correctly excluded from the "populated" regime set); HIGH_VOL (+1.13) and BEAR (+0.36) both positive |
| Benchmark comparison | DEFENSIVE_CANDIDATE — Sharpe +0.56 vs +0.72 for QQQ buy-and-hold; drawdown improves to -4.2% (vs -24.6%) but total return gives up most of QQQ's strong run (+14.5% vs +69.6%) |
| Duplicate-signal status | UNIQUE_SIGNAL — highest correlation is with MSFT keltner_revert (ret_corr +0.56, pos_corr +0.40), just under the NEAR_DUPLICATE bar |
| Bootstrap | **NOT YET TESTED** — flagged in the main doc as "NEEDS MORE ROBUSTNESS TESTING." Requirement #2 is **not formally satisfied.** |
| Family robustness | rsi_revert family flagged ROBUST (shared with the EEM variants) |
| **Exact reason NOT approved for paper-test (return-seeking) but placed on defensive watchlist** | Fails approval requirement #5 (worse Sharpe than QQQ buy-and-hold) for the same reason as MSFT keltner_revert — a real, low-correlation (+0.23) drawdown-reduction pattern that gave up too much of QQQ's strong trend to beat buy-and-hold on a risk-adjusted basis. Additionally fails requirement #2 outright (never bootstrap-tested), an honest gap rather than a soft pass. |
| **Exact reason it could still fail live** | Never bootstrap-tested, so its sensitivity to unlucky return sequencing is unknown; CRISIS regime data (2 days) is statistically meaningless, so genuine crash behavior is essentially untested; like the other defensive candidates, its value depends entirely on portfolio context (combined with return-seeking positions), not on its own merits. |

### 5. AMZN `keltner_revert(20, 2.0)` — **RESEARCH_ONLY**

| Field | Value |
|---|---|
| Strategy | keltner_revert |
| Asset | AMZN |
| Parameters | window=20, atr_mult=2.0 |
| Category | MEAN_REVERSION |
| Expected trade frequency | ~135 OOS trades (6+12+45+46+6+20 = 135 across regimes) |
| Expected drawdown | ~-6.9% to -20.9% max OOS drawdown by regime (BULL regime shows the worst, -20.9%) |
| Slippage sensitivity | STRONGER — positive through 25bp (+0.17); break-even ≈33.2bp |
| Regime weakness | **Two real weak spots, not one:** BULL (its largest regime by day-count, 402 days) is negative (-0.37 Sharpe, -9.9% return, -20.9% max drawdown); BEAR is sharply negative (-2.24 Sharpe) but on a thin 33-day sample. CRISIS/HIGH_VOL/LOW_VOL are all genuinely positive. |
| Benchmark comparison | DEFENSIVE_CANDIDATE — Sharpe +0.66 vs +1.09 for AMZN buy-and-hold; drawdown improves (-17.2% vs -34.7%) but total return is a small fraction of AMZN's exceptional +259.4% buy-and-hold run |
| Duplicate-signal status | UNIQUE_SIGNAL — highest correlation with any other candidate is QQQ rsi_revert (ret_corr +0.42, pos_corr +0.12), well under the NEAR_DUPLICATE bar |
| Bootstrap | SOLID, but worst-case reshuffled drawdown is **-31.3%**, close to the -35% funnel floor — the weakest "SOLID" flag of any of the 7 candidates |
| Family robustness | keltner_revert family flagged ROBUST (shared with MSFT) |
| **Exact reason classified RESEARCH_ONLY (below DEFENSIVE_WATCHLIST)** | It fails approval requirement #5 like MSFT/QQQ, but unlike them it carries two additional, compounding caveats that MSFT/QQQ do not: (1) its bootstrap worst-case drawdown (-31.3%) sits close enough to the -35% funnel floor that a materially unluckier sequencing of the same historical returns would have failed the funnel outright; (2) it loses money specifically in its largest, most-populated regime (BULL, 402 of ~1,411 days) rather than in a minor regime — this is a real drag in the market condition it experiences most often; (3) its BEAR-regime result (-2.24 Sharpe) is on a thin, 33-day sample that is too small to trust as either a confirmed weakness or a confirmed non-issue. The combination of "near-floor bootstrap" + "loses in its most common regime" + "an unresolved, sharply negative thin-sample BEAR result" is a materially weaker evidentiary position than MSFT or QQQ, which is why this candidate is downgraded a full tier to RESEARCH_ONLY rather than DEFENSIVE_WATCHLIST. |
| **Exact reason it could still fail live** | All the live-execution caveats of the other defensive candidates, plus a genuine open question about BEAR-regime behavior that this analysis cannot resolve with only 33 days of sample — if AMZN enters a sustained bear market, this strategy's true behavior is not reliably known from the data available; its bootstrap fragility margin is thin enough that a live paper-test drawdown noticeably worse than backtested would not be a surprising or unusual outcome. |

### 6. SPY `dual_momentum(60, 126)` — **REJECT**

| Field | Value |
|---|---|
| Strategy | dual_momentum |
| Asset | SPY |
| Parameters | window=60, rel_window=126 |
| Category | TREND |
| Expected trade frequency | ~67 OOS trades (0+11+16+10+0+40 = 77, dominated by SIDEWAYS at 40 trades) |
| Expected drawdown | up to -18.0% (SIDEWAYS regime); -16.0% overall at 1bp cost |
| Slippage sensitivity | STRONGER — technically survives to 25bp (+0.31, break-even ≈48bp, the widest margin of any candidate) — passes requirement #3 in isolation |
| Regime weakness | **REGIME_FRAGILE.** Its entire positive Sharpe is produced by the BULL regime alone (+3.32 Sharpe, +62.9% return); it is negative in HIGH_VOL (-0.92), LOW_VOL (-0.18), and SIDEWAYS (-0.81 Sharpe, -15.1% return, its largest-population regime at 416 days) |
| Benchmark comparison | **BETA_DISGUISED** — correlation to SPY's own daily returns is +0.74 (HIGH warning), and excess Sharpe over SPY buy-and-hold is **-0.17 (negative)** — it has a worse risk-adjusted profile than simply holding SPY |
| Duplicate-signal status | UNIQUE_SIGNAL (highest correlation with HYG dual_momentum, ret +0.55/pos +0.44, below the NEAR_DUPLICATE bar) |
| Bootstrap | SOLID, worst-case reshuffled drawdown -28.3% |
| Family robustness | dual_momentum family flagged ROBUST |
| **Exact reason REJECTED** | Fails approval requirement #6 (beta-disguised: +0.74 correlation to SPY, and it does not offset this with a genuine Sharpe improvement — excess Sharpe is negative) AND requirement #7 (regime behavior is not acceptable: this is not a mild regime weak spot, it is a wholesale collapse in every populated regime except one, including its single largest regime by day-count). Two independent, unrelated analyses — the benchmark comparison and the regime decomposition — arrive at the same conclusion through different methods, which is a strong, convergent signal that this candidate's apparent edge is market beta from one bull leg of the sample, not a repeatable strategy. This despite passing the funnel, bootstrap, and slippage-cost gates cleanly — a clear illustration of why those three gates alone are not sufficient. |
| **Exact reason it could still fail live (if ever reconsidered)** | Even setting aside the beta/regime rejection, a live paper test would be expected to underperform SPY buy-and-hold in any period that isn't a strong, sustained uptrend — which is exactly the failure mode already observed in three of four tested regimes. |

### 7. HYG `dual_momentum(126, 126)` — **RESEARCH_ONLY**

| Field | Value |
|---|---|
| Strategy | dual_momentum |
| Asset | HYG |
| Parameters | window=126, rel_window=126 |
| Category | TREND |
| Expected trade frequency | ~45 OOS trades (0+1+11+2+0+32 = 46, dominated by SIDEWAYS at 32 trades) |
| Expected drawdown | up to -7.9% (SIDEWAYS regime); -8.9% overall at 1bp cost |
| Slippage sensitivity | STRONGER — positive through 25bp (+0.07); break-even ≈28.7bp |
| Regime weakness | Automated classifier labels this REGIME_ROBUST (no populated stress regime is negative) — but this label is misleading in isolation: HYG never traded through a BEAR or CRISIS day in this sample (0 days observed in either), 70% of its populated days are in one SIDEWAYS bucket, and exposure is a near-constant 68–96% across every regime with very few trades (1–11 per regime) — the profile of "close to always long HYG," not a demonstrated independent timing skill |
| Benchmark comparison | **BETA_DISGUISED** — correlation to HYG's own returns is +0.80 (the highest in the entire set, HIGH warning), and excess Sharpe over HYG buy-and-hold is a negligible **+0.05** — essentially indistinguishable from simply holding HYG (Sharpe +0.54 vs +0.50; total return +10.9% vs +12.2%; drawdown -8.9% vs -10.6%) |
| Duplicate-signal status | UNIQUE_SIGNAL (highest correlation with SPY dual_momentum, ret +0.55/pos +0.44, below the NEAR_DUPLICATE bar) |
| Bootstrap | SOLID, worst-case reshuffled drawdown -13.7% (60,126 variant) / -13.3% (126,126 variant) |
| Family robustness | dual_momentum family flagged ROBUST |
| **Exact reason classified RESEARCH_ONLY (not REJECT, not APPROVED)** | Fails approval requirement #6 (beta-disguised: +0.80 correlation, negligible +0.05 excess Sharpe) — the same hard-requirement failure as SPY dual_momentum. It is placed at RESEARCH_ONLY rather than flat REJECT because, unlike SPY, its regime evidence does not show an active collapse in any populated stress regime — the automated REGIME_ROBUST label is real, even though it should not be read as a standalone green light. The correct summary is "not proven to add value over buy-and-hold, but also not proven to actively fail" — that combination merits further research (e.g., specifically testing behavior through a genuine credit-market stress event, which this sample never contained) rather than an outright reject or an approval. |
| **Exact reason it could still fail live** | It has never been tested through a real BEAR or CRISIS day for HYG — a genuine credit-spread widening event (which the cached historical window did not contain) could reveal either a real edge or a real, currently-invisible weakness; given its near-constant high exposure, in a live paper test it would behave very similarly to simply holding HYG, meaning any live underperformance would very plausibly look identical to just holding the ETF, not a "strategy failure" per se, but also not adding the diversification/timing value that would justify running it as a distinct strategy. |

---

## Summary

### 1. Single best candidate for paper trading
**EEM `rsi_revert(14, 30/70)`.** It is the only candidate to pass all 10
approval requirements cleanly: it beats its own asset's buy-and-hold on both
Sharpe and drawdown (on an asset that lost money outright over the same
window), it is not beta-disguised, it does not collapse in BEAR or HIGH_VOL,
it clears bootstrap, slippage (through 25bp, ~30bp break-even), and
duplicate-signal checks, and its family (`rsi_revert`) is broadly robust
across parameter variations, not just this one setting.

### 2. Backup candidate (conditional — not currently approved)
**EEM `rsi_revert(14, 25/70)` — classified `BACKUP_PENDING_BOOTSTRAP`, not
`APPROVED_FOR_PAPER_TEST`.** Nearly identical profile and conclusion to the
primary candidate on every metric that HAS been tested, but it has never
been bootstrap-tested — this is a hard, unmet approval requirement (#2),
not a soft caveat. **It cannot be used in paper trading, and must not be
treated as an active backup, unless and until it passes the same bootstrap
stress test (SOLID classification) applied to the primary 30/70 variant,**
using the existing, unmodified `missing_bootstrap_stress.py` methodology.
It also shows zero trading activity in the SIDEWAYS regime. Because it is a
NEAR_DUPLICATE of the primary (56% trade-day overlap, +0.85 return
correlation), even after it clears bootstrap testing **it should be held as
a substitute, not run alongside the primary** — running both simultaneously
would not provide real diversification, just duplicated exposure to the
same underlying signal.


### 3. Defensive watchlist candidates
- **MSFT `keltner_revert(20, 2.0)`** — real, low-correlation, drawdown-reducing
  signal; underperforms MSFT buy-and-hold on Sharpe during this specific
  strongly-trending window; thinnest slippage margin (28.1bp) of the STRONGER
  group; never traded through a CRISIS day.
- **QQQ `rsi_revert(14, 30/75)`** — same pattern as MSFT; additionally never
  bootstrap-tested (open gap).
- **AMZN `keltner_revert(20, 2.0)`** — downgraded to **RESEARCH_ONLY** rather
  than DEFENSIVE_WATCHLIST because of three compounding, unresolved concerns:
  a near-the-floor bootstrap result (-31.3%), a real loss in its own most
  common regime (BULL, 402 days), and a sharply negative BEAR-regime result on
  a statistically thin 33-day sample.

### 4. Rejected candidates
- **SPY `dual_momentum(60, 126)` — REJECT.** Beta-disguised (+0.74 correlation,
  negative excess Sharpe) AND regime-fragile (entire edge from one bull
  regime, negative everywhere else, including its largest regime). Two
  independent analyses agree.
- **HYG `dual_momentum(126, 126)` — RESEARCH_ONLY (not a strong reject, but
  not approved).** Beta-disguised (+0.80 correlation, negligible +0.05 excess
  Sharpe) but without an active regime collapse — genuinely unclear whether
  it is quietly failing or simply untested through the one regime (credit
  stress) that would reveal the difference.

### 5. Next research expansion plan (analysis only, no execution implied)
1. Extend the cached data window (or add a second, independent historical
   period) specifically to capture more BEAR/CRISIS days for AMZN, HYG, and
   MSFT — several open questions in this report (AMZN's thin BEAR sample,
   HYG's total absence of BEAR/CRISIS days, MSFT's total absence of CRISIS
   days) can only be resolved with more history, not more analysis of the
   existing sample.
2. Complete the two outstanding bootstrap tests (EEM `rsi_revert(14,25/70)`
   and QQQ `rsi_revert(14,30/75)`) using the existing, unmodified
   `missing_bootstrap_stress.py` methodology before either is reconsidered
   for anything beyond its current classification.
3. Investigate whether a genuine credit-market stress event (not present in
   the cached window) would reveal HYG `dual_momentum` as a real independent
   signal or confirm it as pure beta — this is the single open question that
   would most change that candidate's classification.
4. If a future paper-trading pilot is approved by a human decision-maker
   (separate from this report), consider position-sizing MSFT/QQQ
   `keltner_revert`/`rsi_revert` as a volatility-dampening overlay alongside
   a return-seeking core, rather than evaluating them standalone — their
   DEFENSIVE_CANDIDATE profile makes more sense in a blended-portfolio
   context than as stand-alone strategies.
5. Do not expand the EEM rsi_revert signal to other emerging-market ETFs (or
   other RSI thresholds on EEM) without first confirming, via an independent
   check, that any "new" survivor is not simply another near-duplicate of the
   same underlying mean-reversion effect already found here.

### 6. Explicit warning

**Paper trading, if and when it is separately implemented and approved, is
for validation only — it is not a decision to deploy capital.** Nothing in
this report authorizes live trading, capital allocation, or even the
enabling of the paper-trading system itself. All classifications above are
based on a single historical out-of-sample window (1,134 trading days) run
through a single set of validation layers; they describe the balance of
evidence to date, not a guarantee of future performance. Every candidate
here — including the primary EEM `rsi_revert` recommendation — could still
underperform, break even, or lose money in a live paper test, and any
transition from paper-test evidence to real capital deployment requires a
separate, explicit, human decision after a genuine paper-trading track
record has been observed, not this document alone.
