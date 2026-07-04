# Benchmark Comparison — 7 Friction-Surviving Candidates vs. Buy-and-Hold

**Scope:** The 7 configs that survived slippage/transaction-cost stress
(Section 12 of `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`): MSFT `keltner_revert`,
AMZN `keltner_revert`, EEM `rsi_revert(14,30/70)`, EEM `rsi_revert(14,25/70)`,
SPY `dual_momentum(60,126)`, HYG `dual_momentum(126,126)`,
QQQ `rsi_revert(14,30/75)`.

**Rules followed:** no strategy tuning, no strategy-logic changes, no
entry/exit rule changes. This reuses the existing unmodified
`edge_hunting.walk_forward.run_walk_forward` engine (baseline 1bp cost) to
get each candidate's OOS returns — same methodology as every prior section.
Benchmarks are pure buy-and-hold (position = 1.0, no trading logic)
evaluated over the exact same OOS date window as each strategy (1,134
overlapping trading days), so every comparison below is apples-to-apples on
out-of-sample days only. **Nothing here is promoted to paper or live
trading.**

**Near-duplicate note:** per `reports/edge_hunting/duplicate_signal_report.md`,
the two EEM `rsi_revert` variants are a NEAR_DUPLICATE pair and should be
read as **one near-duplicate signal slot, not two independent candidates**,
in the interpretation below — even though both rows are reported separately
in full.

Benchmarks compared: (1) buy-and-hold of the candidate's own traded asset,
(2) SPY buy-and-hold, (3) QQQ buy-and-hold, (4) an equal-weight,
daily-rebalanced buy-and-hold across the full 26-asset cached universe (a
descriptive benchmark only, not a strategy).

Full results: `reports/edge_hunting/benchmark_comparison.csv`.

## Classification rule used

- **ROBUST_CANDIDATE** — beats its own asset's buy-and-hold on both Sharpe
  and drawdown (and total return, unless drawdown improvement alone still
  yields a Sharpe win) net of the 1bp cost already baked into the OOS
  returns.
- **DEFENSIVE_CANDIDATE** — mainly reduces drawdown / doesn't lose to
  buy-and-hold on risk-adjusted terms in the qualifying sense used here, but
  underperforms on raw total return (a lower-vol, lower-return substitute
  for holding the asset outright).
- **BETA_DISGUISED** — correlation to the underlying asset's daily returns
  is >= 0.70 AND excess Sharpe over buy-and-hold is <= 0.10 — i.e. the
  strategy is largely just a re-expression of holding the asset, with little
  or no risk-adjusted improvement over simply buying and holding it.
- **REJECT** — fails to beat buy-and-hold on both Sharpe and total return
  with no offsetting drawdown benefit.

---

## Results

| Candidate | Asset | Strat OOS Sharpe | Asset B&H Sharpe | SPY Sharpe | QQQ Sharpe | Strat MaxDD | Asset B&H MaxDD | Strat Total Ret | Asset B&H Total Ret | Excess Ret | Excess Sharpe | Corr to Asset | Beta Warning | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MSFT keltner_revert(20,2.0) | MSFT | +0.71 | +0.85 | +0.81 | +0.72 | -7.4% | -20.6% | +35.3% | +117.1% | -81.8pp | -0.14 | +0.14 | LOW | **DEFENSIVE_CANDIDATE** |
| AMZN keltner_revert(20,2.0) | AMZN | +0.66 | +1.09 | +0.81 | +0.72 | -17.2% | -34.7% | +43.4% | +259.4% | -216.0pp | -0.43 | -0.01 | LOW | **DEFENSIVE_CANDIDATE** |
| EEM rsi_revert(14,30/70) | EEM | +0.65 | -0.35 | +0.81 | +0.72 | -9.9% | -45.2% | +15.8% | -31.5% | +47.3pp | +1.00 | +0.16 | LOW | **ROBUST_CANDIDATE** |
| EEM rsi_revert(14,25/70) | EEM | +0.54 | -0.35 | +0.81 | +0.72 | -7.3% | -45.2% | +10.8% | -31.5% | +42.3pp | +0.89 | +0.10 | LOW | **ROBUST_CANDIDATE** |
| SPY dual_momentum(60,126) | SPY | +0.64 | +0.81 | +0.81 | +0.72 | -16.0% | -19.3% | +31.7% | +60.4% | -28.6pp | -0.17 | **+0.74** | **HIGH** | **BETA_DISGUISED** |
| HYG dual_momentum(126,126) | HYG | +0.54 | +0.50 | +0.81 | +0.72 | -8.9% | -10.6% | +10.9% | +12.2% | -1.4pp | +0.05 | **+0.80** | **HIGH** | **BETA_DISGUISED** |
| QQQ rsi_revert(14,30/75) | QQQ | +0.56 | +0.72 | +0.81 | +0.72 | -4.2% | -24.6% | +14.5% | +69.6% | -55.0pp | -0.16 | +0.23 | LOW | **DEFENSIVE_CANDIDATE** |

Equal-weight universe benchmark (all 7 rows, same OOS window): Sharpe +0.78,
total return +57.1%, max drawdown -20.6%. Every one of the 7 candidates
underperforms this equal-weight universe benchmark on total return; only the
two EEM rsi_revert rows meaningfully beat it on Sharpe (+0.65/+0.54 vs
+0.78... actually below it too). **None of the 7 candidates beats the
simple equal-weight 26-asset buy-and-hold benchmark on Sharpe.**

---

## Per-candidate interpretation

### MSFT keltner_revert — DEFENSIVE_CANDIDATE
Cuts max drawdown roughly in third (-7.4% vs -20.6% for MSFT buy-and-hold)
but gives up the great majority of MSFT's OOS total return (+35.3% vs
+117.1% buy-and-hold) — MSFT simply had a very strong run over this OOS
window and staying out of the market most of the time (mean-reverting in
and out) missed most of the gain. Correlation to MSFT's own daily returns is
low (+0.14), so this is not beta-disguised — it genuinely trades a distinct,
lower-frequency signal — but it is a worse risk-adjusted bet than just
holding MSFT over this period (Sharpe +0.71 vs +0.85).

### AMZN keltner_revert — DEFENSIVE_CANDIDATE
Same pattern as MSFT, more extreme: max drawdown roughly halved (-17.2% vs
-34.7%) but total return is a small fraction of AMZN's buy-and-hold
(+43.4% vs a striking +259.4%). Correlation to AMZN's own returns is
essentially zero (-0.01) — again not beta-disguised, but this strategy
massively underperformed simply holding AMZN through this OOS window on
every metric except drawdown.

### EEM rsi_revert(14,30/70) — ROBUST_CANDIDATE
The standout of the set. EEM buy-and-hold OOS Sharpe was **negative**
(-0.35, -31.5% total return) over this window — EEM had a rough stretch —
while the strategy posted +0.65 Sharpe and +15.8% total return, cutting max
drawdown from -45.2% (buy-and-hold) to -9.9%. Excess Sharpe of +1.00 and
excess return of +47.3 percentage points are both the largest in the set,
and correlation to EEM's own daily returns is low (+0.16). This is genuine
evidence of a real, non-beta signal on a name that would otherwise have lost
money.

### EEM rsi_revert(14,25/70) — ROBUST_CANDIDATE
Same story as its sibling above (expected, given the NEAR_DUPLICATE
classification): EEM buy-and-hold was -31.5%/-0.35 Sharpe, this variant
delivered +10.8% total return / +0.54 Sharpe with only a -7.3% max
drawdown, and low correlation (+0.10) to the underlying asset. Slightly
weaker than the 30/70 variant on every metric, consistent with the earlier
regime-decomposition finding that the 30/70 threshold is the stronger of
the two. **Per the near-duplicate framing, this and the row above should be
counted as one piece of evidence** — EEM rsi_revert genuinely adds value
over holding EEM outright, but this is one confirmed signal, not two.

### SPY dual_momentum(60,126) — BETA_DISGUISED
Correlation to SPY's own daily returns is **+0.74**, the highest asset
correlation in the set, and excess Sharpe over SPY buy-and-hold is
**-0.17 (negative)** — the strategy actually has a *worse* risk-adjusted
profile than simply holding SPY (+0.64 vs +0.81 Sharpe), while closely
tracking it. This is the same asset-beta concern already raised in
Sections 5/10/11/13 of the main document, now confirmed directly against
its own benchmark: SPY dual_momentum is not adding value over buy-and-hold,
it is a diluted, higher-turnover way of getting SPY's own beta with a worse
Sharpe and marginally better (but not decisively better) drawdown (-16.0%
vs -19.3%).

### HYG dual_momentum(126,126) — BETA_DISGUISED
Correlation to HYG's own returns is **+0.80**, the highest in the entire
set, and excess Sharpe over HYG buy-and-hold is a negligible +0.05 — barely
distinguishable from simply holding HYG (+0.54 vs +0.50 Sharpe, +10.9% vs
+12.2% total return, -8.9% vs -10.6% max drawdown). Every metric is close to
a wash. Combined with the earlier regime-decomposition caveat that HYG never
traded through a real BEAR/CRISIS period in this sample, this strategy
should be read as **not clearly distinguishable from holding HYG outright**
— it is not losing money, but it is also not demonstrating a real edge over
the benchmark.

### QQQ rsi_revert(14,30/75) — DEFENSIVE_CANDIDATE
Max drawdown improves substantially (-4.2% vs -24.6% for QQQ buy-and-hold)
but total return gives up most of QQQ's strong OOS run (+14.5% vs +69.6%).
Correlation to QQQ's own returns is modest (+0.23) — not beta-disguised,
but clearly a worse risk-adjusted bet than simply holding QQQ over this
window (Sharpe +0.56 vs +0.72).

---

## Net effect on paper-trading readiness

**2 of 7 (really ~1 near-duplicate signal slot) are ROBUST_CANDIDATE:** the
two EEM rsi_revert variants are the only candidates in this set that
convincingly beat their own asset's buy-and-hold on both Sharpe and
drawdown, on an asset that would otherwise have *lost* money over this OOS
window. This is the strongest evidence-based case for paper-trading in the
entire set.

**2 of 7 are BETA_DISGUISED:** SPY dual_momentum and HYG dual_momentum both
show high correlation (+0.74, +0.80) to their own underlying asset and
negligible-to-negative excess Sharpe over simply holding that asset. Neither
should be read as demonstrating a real, independent trading edge — SPY
dual_momentum was already flagged REGIME_FRAGILE in Section 13, and this
benchmark comparison independently confirms the same underlying concern from
a different angle; HYG dual_momentum's edge is now revealed to be nearly
indistinguishable from buy-and-hold once compared directly against it,
which is a materially different (weaker) conclusion than "REGIME_ROBUST"
implied on its own.

**3 of 7 are DEFENSIVE_CANDIDATE:** MSFT keltner_revert, AMZN
keltner_revert, and QQQ rsi_revert all cut drawdown meaningfully but
surrendered the majority of their asset's very strong OOS buy-and-hold
return, resulting in a worse Sharpe than simply holding the asset. These are
not beta-disguised (low correlation to their own asset), so they are
capturing a distinct, real trading pattern — but that pattern was a net
drag on risk-adjusted performance during this specific, strongly trending
OOS window. They may still be useful as a defensive/diversifying sleeve in
a portfolio context (worth a future, separate correlation-to-portfolio
study) but should not be sold as "beats buy-and-hold" strategies.

**None of the 7 beats the equal-weight, 26-asset universe buy-and-hold
benchmark on Sharpe (+0.78) or total return (+57.1%) over the same OOS
window.** This is an important, humbling context check: an investor who
simply bought a naive equal-weight basket of the existing cached universe
would have outperformed every one of these 7 "surviving" strategies on both
metrics over this period.

**As instructed, nothing here is promoted to paper trading.** This report
is diagnostic only, adding a fourth independent lens (after funnel/bootstrap,
slippage, and regime decomposition) that most strongly favors the EEM
rsi_revert signal and raises new, sharper concerns about SPY and HYG
dual_momentum specifically.
