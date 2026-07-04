# Regime Decomposition — 7 Friction-Surviving Candidates

**Re-run context:** this decomposition uses the same unmodified methodology
as the original run (Section 13) — no parameter tuning, no strategy-logic
changes, no entry/exit rule changes, no funnel threshold changes, existing
cached data, existing walk-forward/OOS engine (1bp baseline cost). Results
are numerically identical to the original run (confirms reproducibility).
This report has been rewritten to fold in the findings of the benchmark
comparison (Section 15) — in particular the ROBUST_CANDIDATE classification
of both EEM `rsi_revert` variants and the BETA_DISGUISED classification of
`SPY dual_momentum` / `HYG dual_momentum` — per the interpretation rules
supplied for this run.

**Near-duplicate note:** per `reports/edge_hunting/duplicate_signal_report.md`,
the two EEM `rsi_revert` variants are a NEAR_DUPLICATE pair and are read as
one near-duplicate signal slot in the interpretation below, even though both
rows are reported in full.

Full per-regime numeric results: `reports/edge_hunting/regime_decomposition.csv`.

## Regime labels used

Six descriptive, priority-ordered regimes assigned per trading day from each
asset's own history (not tuned to any strategy):

1. **CRISIS** — drawdown from trailing 252-day peak <= -20%
2. **HIGH_VOL** — (not crisis) 60-day realized vol in the asset's own top quartile
3. **LOW_VOL** — (not crisis/high-vol) 60-day realized vol in the asset's own bottom quartile
4. **BULL** — (none of the above) trailing 60-day return > +5%
5. **BEAR** — (none of the above) trailing 60-day return < -5%
6. **SIDEWAYS** — everything else

---

## Results by candidate

### MSFT keltner_revert — REGIME_ROBUST
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 0 | — | — | — | — | — | — |
| HIGH_VOL | 201 | +0.98 | +10.3% | -4.2% | 16 | 10% | 16.0 |
| LOW_VOL | 244 | -0.69 | -5.3% | -10.1% | 28 | 21% | 28.0 |
| BULL | 359 | +1.17 | +14.5% | -6.3% | 46 | 22% | 47.0 |
| BEAR | 117 | +0.32 | +1.4% | -6.6% | 10 | 10% | 10.0 |
| SIDEWAYS | 213 | +1.27 | +11.6% | -9.0% | 27 | 12% | 28.0 |

Best: SIDEWAYS. Worst: LOW_VOL. Not concentrated in one regime — positive
Sharpe in HIGH_VOL, BULL, BEAR, and SIDEWAYS; only LOW_VOL is negative and
mild (-0.69 Sharpe, -5.3% return). No CRISIS days observed for MSFT in this
sample (untested in a genuine crash). **Does not collapse in BEAR or
HIGH_VOL** — both are positive. **Portfolio-defense candidate: JUSTIFIED** —
regime behavior is broadly stable and the one weak regime (LOW_VOL) is not a
stress regime.

### AMZN keltner_revert — REGIME_ROBUST (with a real caveat)
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 75 | +0.70 | +4.1% | -6.9% | 6 | 9% | 6.0 |
| HIGH_VOL | 144 | +1.35 | +7.2% | -3.5% | 12 | 21% | 12.0 |
| LOW_VOL | 338 | +1.06 | +12.2% | -4.9% | 45 | 16% | 46.0 |
| BULL | 402 | -0.37 | -9.9% | -20.9% | 46 | 22% | 46.0 |
| BEAR | 33 | **-2.24** | -4.2% | -7.0% | 6 | 18% | 6.0 |
| SIDEWAYS | 142 | +3.29 | +32.7% | -0.6% | 20 | 11% | 20.0 |

Best: SIDEWAYS. Worst: **BEAR (-2.24 Sharpe)**. Positive in CRISIS,
HIGH_VOL, and LOW_VOL — genuinely does NOT collapse in the crisis/high-vol
stress regimes — but is clearly negative in both BULL (-0.37, its largest
regime by day-count at 402 days, with a real -20.9% max drawdown) and BEAR
(-2.24, its worst Sharpe of any regime, on 33 days). This is a mixed
picture: robust through crisis/vol stress, but loses money in a strong
uptrend and loses badly (small sample, only 33 days) in a downtrend.
**Portfolio-defense candidate: JUSTIFIED WITH CAVEAT** — the CRISIS/HIGH_VOL
robustness supports a defensive role, but the BEAR-regime result (n=33, thin
but sharply negative) should be flagged and monitored, not ignored, before
any paper-trading pilot.

### EEM rsi_revert(14,30/70) — REGIME_ROBUST — confirms benchmark ROBUST_CANDIDATE
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 162 | -0.34 | -2.8% | -9.9% | 9 | 10% | 9.0 |
| HIGH_VOL | 155 | +0.83 | +1.5% | -0.7% | 2 | 2% | 2.0 |
| LOW_VOL | 227 | -0.30 | -0.8% | -2.3% | 12 | 8% | 12.0 |
| BULL | 168 | +2.82 | +8.8% | -0.8% | 16 | 8% | 16.0 |
| BEAR | 137 | **+2.38** | +5.5% | -0.9% | 12 | 4% | 12.0 |
| SIDEWAYS | 285 | +0.91 | +3.0% | -1.1% | 4 | 2% | 4.0 |

Best: BULL. Worst: CRISIS (-0.34 Sharpe, -2.8% return, -9.9% max DD — a
real but mild loss, not a collapse). **Critically for the paper-test
eligibility rule: BEAR regime Sharpe is +2.38 (strongly positive) and
HIGH_VOL regime Sharpe is +0.83 (positive)** — the strategy does NOT
collapse in either bear or high-volatility conditions. Only CRISIS shows a
loss, and it is small in magnitude (-2.8%) relative to what EEM buy-and-hold
lost overall (-31.5%, per Section 15). **Verdict: EEM rsi_revert(14,30/70)
remains a paper-test candidate — it passes the required "does not collapse
in bear/high-volatility/crisis" bar (CRISIS is mildly negative, not a
collapse; BEAR and HIGH_VOL are both clearly positive).**

### EEM rsi_revert(14,25/70) — REGIME_ROBUST — confirms benchmark ROBUST_CANDIDATE
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 162 | +0.02 | -0.2% | -7.3% | 6 | 5% | 6.0 |
| HIGH_VOL | 155 | +0.83 | +1.5% | -0.7% | 2 | 2% | 2.0 |
| LOW_VOL | 227 | -0.54 | -1.3% | -2.5% | 8 | 7% | 8.0 |
| BULL | 168 | +2.82 | +8.8% | -0.8% | 16 | 8% | 16.0 |
| BEAR | 137 | +1.35 | +1.9% | 0.0% | 2 | 1% | 2.0 |
| SIDEWAYS | 285 | -0.94 | 0.0% | 0.0% | 0 | 0% | 0.0 |

Best: BULL. Worst: SIDEWAYS (near-zero trading, near-zero effect — not a
real loss, essentially flat/no signal). **CRISIS is essentially flat
(+0.02 Sharpe, -0.2% return) and BEAR/HIGH_VOL are both clearly positive
(+1.35/+0.83)** — this variant also passes the "does not collapse in
bear/high-vol/crisis" bar, even more cleanly than its sibling (CRISIS is
flat rather than mildly negative). **Verdict: also remains a paper-test
candidate on this test alone**, though as the near-duplicate framing notes,
this and the row above should be counted as one confirmed signal, and the
30/70 variant is the stronger of the two on both this test and the earlier
benchmark-comparison excess-Sharpe result (+1.00 vs +0.89).

### SPY dual_momentum(60,126) — REGIME_FRAGILE — regime results CONFIRM (do not contradict) the benchmark BETA_DISGUISED finding
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 0 | — | — | — | — | — | — |
| HIGH_VOL | 134 | **-0.92** | -2.8% | -5.3% | 11 | 20% | 11.0 |
| LOW_VOL | 217 | -0.18 | -2.0% | -8.0% | 16 | 94% | 16.0 |
| BULL | 341 | **+3.32** | +62.9% | -4.1% | 10 | 96% | 10.0 |
| BEAR | 26 | 0.00 | 0.0% | 0.0% | 0 | 0% | 0.0 |
| SIDEWAYS | 416 | **-0.81** | -15.1% | -18.0% | 40 | 71% | 40.0 |

Best: BULL (by a huge margin). Worst: HIGH_VOL. **The entire strategy's
positive Sharpe comes from the BULL regime alone; it is negative in every
other populated regime**, including its single largest regime by day-count
(SIDEWAYS, 416 days, -15.1% total return — a real, material loss, not a
rounding error). Per the interpretation rule for this run — "SPY/HYG
dual_momentum should remain blocked unless regime results clearly
contradict the benchmark beta-disguised finding" — **these regime results do
not contradict the benchmark finding; they reinforce it.** A strategy whose
entire edge is one bull regime, with a high (94-96%) exposure level in the
regimes where it's active, is textbook consistent with "the strategy is
mostly re-expressing the underlying asset's own bull-market beta," matching
the +0.74 return correlation and negative excess-Sharpe found in the
benchmark comparison. **Verdict: SPY dual_momentum remains BLOCKED from
paper-trading promotion.**

### HYG dual_momentum(126,126) — REGIME_ROBUST label, but regime results also do NOT contradict the benchmark BETA_DISGUISED finding
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 0 | — | — | — | — | — | — |
| HIGH_VOL | 73 | +1.81 | +2.7% | -1.4% | 1 | 68% | 1.0 |
| LOW_VOL | 372 | +0.34 | +1.7% | -3.9% | 11 | 95% | 11.0 |
| BULL | 48 | +5.47 | +5.0% | -1.0% | 2 | 96% | 2.0 |
| BEAR | 9 | — | — | — | — | — | — |
| SIDEWAYS | 632 | +0.11 | +1.0% | -7.9% | 32 | 73% | 32.0 |

Best: BULL. Worst: SIDEWAYS

(mildly positive, +0.11 Sharpe — not a loss). The regime engine's own
`_classify` function labels this REGIME_ROBUST because no populated stress
regime (HIGH_VOL) is negative and it is not "concentrated" by the automated
rule. **However, this label must be read alongside the benchmark-comparison
result, not instead of it.** HYG's own populated regimes are dominated by
SIDEWAYS (632 of ~902 total days, 70%) with consistently high exposure
(68–96% throughout every regime) and very few actual trades (1–11 per
regime) — this pattern (high, nearly-always-on exposure, low turnover, no
BEAR/CRISIS days ever observed) is exactly the signature of a strategy that
is close to being "long HYG most of the time," which is consistent with —
not a contradiction of — the benchmark finding that HYG dual_momentum has
+0.80 correlation to HYG's own returns and only +0.05 excess Sharpe over
simply holding HYG. **Per the interpretation rule, since regime results do
not clearly contradict the beta-disguised finding, HYG dual_momentum
remains BLOCKED from paper-trading promotion**, notwithstanding its
REGIME_ROBUST label — this is a case where the automated regime
classification and the benchmark comparison should not be read as
independent green lights; taken together, they say "not obviously
regime-fragile, but also not demonstrated to beat holding HYG."

### QQQ rsi_revert(14,30/75) — REGIME_ROBUST
| Regime | n days | OOS Sharpe | Total Ret | Max DD | Trades | Exposure | Turnover |
|---|---|---|---|---|---|---|---|
| CRISIS | 2 | -11.23 (n too small) | -2.5% | -2.5% | 1 | 50% | 1.0 |
| HIGH_VOL | 196 | +1.13 | +6.2% | 0.0% | 2 | 1% | 2.0 |
| LOW_VOL | 195 | +0.74 | +1.1% | -1.1% | 6 | 6% | 6.0 |
| BULL | 396 | -0.10 | -0.5% | -3.5% | 19 | 7% | 19.0 |
| BEAR | 57 | +0.36 | +1.0% | -4.2% | 6 | 16% | 6.0 |
| SIDEWAYS | 288 | +1.48 | +8.9% | -1.3% | 8 | 2% | 8.0 |

Best: SIDEWAYS. Worst: BULL (mildly negative, -0.10 Sharpe, small -0.5%
loss — not a meaningful collapse). CRISIS has only 2 days (statistically
meaningless, correctly excluded from the "populated" regime set by the
classifier). **HIGH_VOL and BEAR are both positive** — does not collapse in
either stress regime with sufficient data. **Portfolio-defense candidate:
JUSTIFIED** — regime behavior across HIGH_VOL/LOW_VOL/BEAR/SIDEWAYS is
consistently positive; the only negative regime (BULL) is mild and is
consistent with this being a mean-reversion strategy that naturally
underperforms in a persistent uptrend.

---

## Summary table

| Candidate | Best regime | Worst regime | Concentrated? | Classification | Collapses in BEAR/HIGH_VOL/CRISIS? |
|---|---|---|---|---|---|
| MSFT keltner_revert | SIDEWAYS | LOW_VOL | No | REGIME_ROBUST | No |
| AMZN keltner_revert | SIDEWAYS | BEAR | No | REGIME_ROBUST | No (but BEAR itself is sharply negative, n=33) |
| EEM rsi_revert(30/70) | BULL | CRISIS | No | REGIME_ROBUST | No — CRISIS mildly negative only |
| EEM rsi_revert(25/70) | BULL | SIDEWAYS | No | REGIME_ROBUST | No — CRISIS ~flat |
| SPY dual_momentum | BULL | HIGH_VOL | **Yes** | **REGIME_FRAGILE** | **Yes — negative in HIGH_VOL and SIDEWAYS** |
| HYG dual_momentum | BULL | SIDEWAYS | No (by automated rule) | REGIME_ROBUST (label) / **effectively beta-consistent** | No populated stress regime is negative, but see beta-disguised caveat above |
| QQQ rsi_revert | SIDEWAYS | BULL | No | REGIME_ROBUST | No |

---

## Net effect on paper-trading readiness (after folding in the benchmark comparison)

1. **EEM rsi_revert (both variants, ~1 near-duplicate signal slot) — REMAINS A PAPER-TEST
   CANDIDATE.** It passes both required bars: benchmark comparison shows it
   beats EEM buy-and-hold on Sharpe/return/drawdown (ROBUST_CANDIDATE), and
   this regime decomposition confirms it does not collapse in BEAR
   (+2.38/+1.35 Sharpe) or HIGH_VOL (+0.83 both variants) — CRISIS is only
   mildly negative (30/70 variant) or flat (25/70 variant), not a collapse.
   This remains the strongest evidence-based candidate in the entire set.

2. **SPY dual_momentum — REMAINS BLOCKED.** Regime results (entire edge from
   one BULL regime, negative in HIGH_VOL and SIDEWAYS, its largest regime by
   day count) do not contradict — they reinforce — the benchmark
   BETA_DISGUISED finding (+0.74 correlation to SPY, negative excess Sharpe).

3. **HYG dual_momentum — REMAINS BLOCKED**, despite an automated REGIME_ROBUST
   label. The regime evidence (near-constant high exposure, low turnover,
   dominant SIDEWAYS bucket, no BEAR/CRISIS days ever observed) does not
   clearly contradict the benchmark BETA_DISGUISED finding (+0.80 correlation,
   +0.05 excess Sharpe) — per the interpretation rule for this run, the
   absence of contradiction means it stays blocked. This is a meaningful
   downgrade from the plain REGIME_ROBUST label alone.

4. **MSFT keltner_revert and QQQ rsi_revert — JUSTIFIED as portfolio-defense
   candidates.** Both show broadly positive Sharpe across HIGH_VOL, LOW_VOL,
   BEAR, and SIDEWAYS regimes, with only one mild, non-stress-regime
   weak spot each (MSFT: LOW_VOL; QQQ: BULL). Combined with the benchmark
   comparison's DEFENSIVE_CANDIDATE finding (real drawdown reduction, lower
   total return than buy-and-hold), this supports using them as a
   volatility-dampening sleeve rather than a return-seeking core position —
   not as a "beats buy-and-hold" strategy.

5. **AMZN keltner_revert — JUSTIFIED as a portfolio-defense candidate WITH
   CAVEAT.** It is robust through CRISIS/HIGH_VOL/LOW_VOL but loses money in
   its largest regime (BULL, 402 days, -20.9% max DD) and shows a sharply
   negative BEAR-regime Sharpe (-2.24) on a thin 33-day sample. The
   CRISIS/HIGH_VOL robustness is genuinely useful for a defensive role, but
   the BEAR-regime result should be treated as an open question (small
   sample) rather than a settled positive, and revisited if/when more BEAR
   days accumulate in the cached data.

**As instructed, nothing has been promoted to paper or live trading by this
analysis.** No parameters were tuned, no strategy logic or entry/exit rules
were changed, and no funnel thresholds were altered.
