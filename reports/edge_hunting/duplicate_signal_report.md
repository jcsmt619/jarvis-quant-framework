# Duplicate / Near-Duplicate Signal Detection — 7 Friction-Surviving Candidates

**Scope:** The 7 configs that survived slippage/transaction-cost stress
(Section 12 of `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`): MSFT `keltner_revert`,
AMZN `keltner_revert`, EEM `rsi_revert(14,30/70)`, EEM `rsi_revert(14,25/70)`,
SPY `dual_momentum(60,126)`, HYG `dual_momentum(126,126)`,
QQQ `rsi_revert(14,30/75)`. 21 unique unordered pairs (7 choose 2).

**Rules followed:** no strategies deleted, no strategy logic changed, no
parameters tuned. This is classification only, produced by comparing
already-computed OOS return/position series pairwise. Reuses the existing
unmodified `edge_hunting.walk_forward.run_walk_forward` engine (baseline
1bp cost) purely to obtain each candidate's OOS returns/positions — no new
backtest methodology, no sweep re-run.

## Metrics computed (per pair)

- **return_correlation** — Pearson correlation of daily OOS returns over
  the 1,134 overlapping trading days common to all 7 series.
- **position_correlation** — Pearson correlation of daily OOS position
  series over the same overlap.
- **trade_date_overlap** — Jaccard overlap (`|intersection| / |union|`) of
  each pair's "trade days" (days the position actually changed).
- **parameter_similarity** — 1.0 same family + identical params, 0.5 same
  family + different params, 0.0 different families.
- **asset_similarity** — 1.0 same underlying asset, 0.0 otherwise.

## Classification thresholds (per pair)

- **DUPLICATE_SIGNAL** — return_correlation >= 0.90 **and**
  position_correlation >= 0.90. This is the bar for a literal re-expression
  of the same computation (the kind of duplication already flagged
  elsewhere in this project, e.g. `XLK bollinger_revert` vs
  `XLK zscore_revert`, which were numerically identical).
- **NEAR_DUPLICATE** — return_correlation >= 0.60 **or**
  position_correlation >= 0.60, but not both >= 0.90.
- **INDEPENDENT** — neither threshold met.

Full pairwise results: `reports/edge_hunting/duplicate_signal_report.csv`.

---

## Results

| Pair | Asset A / B | Family A / B | ret_corr | pos_corr | trade_overlap | param_sim | asset_sim | Classification |
|---|---|---|---|---|---|---|---|---|
| MSFT keltner ↔ AMZN keltner | MSFT/AMZN | same family | +0.386 | +0.325 | 0.093 | 1.0 | 0.0 | INDEPENDENT |
| MSFT keltner ↔ EEM rsi(30/70) | MSFT/EEM | diff | +0.189 | +0.112 | 0.055 | 0.0 | 0.0 | INDEPENDENT |
| MSFT keltner ↔ EEM rsi(25/70) | MSFT/EEM | diff | +0.221 | +0.118 | 0.040 | 0.0 | 0.0 | INDEPENDENT |
| MSFT keltner ↔ SPY dual_mom | MSFT/SPY | diff | -0.046 | -0.172 | 0.038 | 0.0 | 0.0 | INDEPENDENT |
| MSFT keltner ↔ HYG dual_mom | MSFT/HYG | diff | +0.008 | -0.066 | 0.045 | 0.0 | 0.0 | INDEPENDENT |
| MSFT keltner ↔ QQQ rsi(30/75) | MSFT/QQQ | diff | +0.562 | +0.396 | 0.131 | 0.0 | 0.0 | INDEPENDENT |
| AMZN keltner ↔ EEM rsi(30/70) | AMZN/EEM | diff | +0.139 | +0.101 | 0.053 | 0.0 | 0.0 | INDEPENDENT |
| AMZN keltner ↔ EEM rsi(25/70) | AMZN/EEM | diff | +0.142 | +0.075 | 0.032 | 0.0 | 0.0 | INDEPENDENT |
| AMZN keltner ↔ SPY dual_mom | AMZN/SPY | diff | -0.075 | -0.125 | 0.060 | 0.0 | 0.0 | INDEPENDENT |
| AMZN keltner ↔ HYG dual_mom | AMZN/HYG | diff | -0.041 | +0.039 | 0.031 | 0.0 | 0.0 | INDEPENDENT |
| AMZN keltner ↔ QQQ rsi(30/75) | AMZN/QQQ | diff | +0.416 | +0.116 | 0.084 | 0.0 | 0.0 | INDEPENDENT |
| **EEM rsi(30/70) ↔ EEM rsi(25/70)** | **EEM/EEM (same asset)** | **same family** | **+0.846** | **+0.805** | **0.564** | **0.5** | **1.0** | **NEAR_DUPLICATE** |
| EEM rsi(30/70) ↔ SPY dual_mom | EEM/SPY | diff | -0.012 | -0.121 | 0.017 | 0.0 | 0.0 | INDEPENDENT |
| EEM rsi(30/70) ↔ HYG dual_mom | EEM/HYG | diff | +0.066 | -0.094 | 0.022 | 0.0 | 0.0 | INDEPENDENT |
| EEM rsi(30/70) ↔ QQQ rsi(30/75) | EEM/QQQ | same family | +0.391 | +0.203 | 0.056 | 0.5 | 0.0 | INDEPENDENT |
| EEM rsi(25/70) ↔ SPY dual_mom | EEM/SPY | diff | -0.033 | -0.094 | 0.000 | 0.0 | 0.0 | INDEPENDENT |
| EEM rsi(25/70) ↔ HYG dual_mom | EEM/HYG | diff | +0.011 | -0.100 | 0.000 | 0.0 | 0.0 | INDEPENDENT |
| EEM rsi(25/70) ↔ QQQ rsi(30/75) | EEM/QQQ | same family | +0.451 | +0.225 | 0.056 | 0.5 | 0.0 | INDEPENDENT |
| SPY dual_mom ↔ HYG dual_mom | SPY/HYG | same family | +0.547 | +0.444 | 0.038 | 0.5 | 0.0 | INDEPENDENT |
| SPY dual_mom ↔ QQQ rsi(30/75) | SPY/QQQ | diff | -0.028 | -0.198 | 0.028 | 0.0 | 0.0 | INDEPENDENT |
| HYG dual_mom ↔ QQQ rsi(30/75) | HYG/QQQ | diff | +0.071 | -0.092 | 0.012 | 0.0 | 0.0 | INDEPENDENT |

## Per-candidate rollup classification

| Candidate | Classification | Basis |
|---|---|---|
| MSFT `keltner_revert(20,2.0)` | **UNIQUE_SIGNAL** | No pairing >= NEAR_DUPLICATE threshold |
| AMZN `keltner_revert(20,2.0)` | **UNIQUE_SIGNAL** | No pairing >= NEAR_DUPLICATE threshold |
| EEM `rsi_revert(14,30/70)` | **NEAR_DUPLICATE** | Paired with EEM `rsi_revert(14,25/70)`: ret_corr +0.85, pos_corr +0.81 |
| EEM `rsi_revert(14,25/70)` | **NEAR_DUPLICATE** | Same pairing as above, symmetric |
| SPY `dual_momentum(60,126)` | **UNIQUE_SIGNAL** | Highest single correlation is with HYG dual_momentum (ret +0.55, pos +0.44), below the 0.60 NEAR_DUPLICATE bar on both metrics |
| HYG `dual_momentum(126,126)` | **UNIQUE_SIGNAL** | Same SPY pairing, same conclusion |
| QQQ `rsi_revert(14,30/75)` | **UNIQUE_SIGNAL** | Highest correlation is with MSFT keltner_revert (ret +0.56, pos +0.40) — below the 0.60 bar on pos_corr, and MSFT keltner just clears 0.56 < 0.60 on ret_corr too |

No pair meets the **DUPLICATE_SIGNAL** bar (both correlations >= 0.90) —
none of these 7 candidates is a literal re-expression of another, unlike
the previously-identified `XLK bollinger_revert` / `XLK zscore_revert` case
elsewhere in this document.

## Interpretation

**5 of 7 candidates are UNIQUE_SIGNAL** — MSFT keltner_revert, AMZN
keltner_revert, SPY dual_momentum, HYG dual_momentum, QQQ rsi_revert. Each
of these should be treated as an independent piece of evidence; their
correlations with every other candidate in the set are modest (mostly
|corr| < 0.5), even when they share the same strategy family (e.g. MSFT and
AMZN keltner_revert only correlate at +0.39/+0.33 despite identical
parameters, because the two underlying assets don't move together tightly
enough to force correlated signals).

**2 of 7 (both EEM rsi_revert variants) are NEAR_DUPLICATE of each other.**
This is expected and mechanically obvious: they are the *same* strategy
family, on the *same* asset, with only a 5-point difference in the oversold
threshold (30 vs 25). 56% of their trade days overlap and their OOS return
streams correlate at +0.85. **This should be read as roughly one independent
piece of evidence, not two**, when assessing how many genuinely distinct
edges have survived the funnel/bootstrap/slippage/regime gauntlet so far —
consistent with the earlier documented finding (Section "What should be
tested next," item 3) that near-identical parameter variants of the same
signal should not be double-counted as separate confirmations.

Practically: if only one EEM rsi_revert variant is carried into any future
paper-trading pilot, prefer `rsi_revert(14,30/70)` (the wider/more standard
30/70 threshold) since it has both the higher slippage-survival OOS Sharpe
of the two friction-surviving results and matches the more commonly used
RSI threshold convention, rather than running both and effectively doubling
up on the same underlying signal without doubling the evidence.

## Net effect on candidate count

No strategy has been deleted, modified, or reparametrized as a result of
this analysis. The 7 friction-surviving, regime-checked candidates remain
unchanged in the document's list. This report only adds a signal-uniqueness
annotation: **6 genuinely distinct signal "slots"** are represented among
the 7 candidates (5 UNIQUE_SIGNAL + 1 combined NEAR_DUPLICATE pair), which
should inform — but not by itself determine — any future portfolio
construction or position-sizing decision (e.g. running both EEM variants
simultaneously would not provide as much diversification benefit as their
raw count of "2 candidates" might suggest).
