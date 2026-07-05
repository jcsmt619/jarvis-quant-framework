# Missing Bootstrap Stress Test — Follow-Up Run

**Scope note:** This is a follow-up to `reports/edge_hunting/bootstrap_stress_test.csv`
(the original sweep's robustness layer), which covered only 30 of the 35 funnel
survivors. This run fills in the 5 configs that were genuinely absent from that
file, using the exact same methodology, unmodified code
(`edge_hunting/robustness.py::bootstrap_stress_test`), and the exact same params
recorded for each config in `reports/edge_hunting/top_survivors.csv`. No parameters
were tuned, no strategy logic was changed, and no funnel thresholds were touched.
The full sweep was not re-run — only the 4 assets needed (NVDA, AMZN, MSFT, GOOGL)
were loaded from the existing on-disk parquet cache
(`data/raw/edge_hunting_cache/`), and only these 5 configs were backtested.

**Methodology (identical to the original sweep):**
- OOS daily returns come from the same walk-forward engine (`edge_hunting.walk_forward.run_walk_forward`).
- 200 reshuffles of the OOS daily-return **order only** (values never resampled/altered).
- Fixed random seed = 42 (deterministic, reproducible).
- Reports p5 / p50 / p95 Sharpe of the reshuffled distribution.
- Reports worst-case reshuffled drawdown across all 200 reshuffles.
- Classification: **SOLID** if worst-case drawdown > -35%, else **FRAGILE**.

**Reconciliation note on "9" vs "5":** `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`'s
survivor table tags 8 rows "NEEDS MORE ROBUSTNESS TESTING" (its summary line says
9, a pre-existing count discrepancy in that document). Of those 8, 3 already had
bootstrap data in `bootstrap_stress_test.csv` (TLT `pivot_bounce`, QQQ
`rsi_revert(14,30/75)`, EEM `rsi_revert(14,25/70)`) — flagged there for reasons
*other* than missing data (proximity to the -35% floor, or low priority). Per the
instruction to run bootstrap stress testing only on configs genuinely **missing**
from the robustness layer, this run covers exactly the 5 configs identified in
`docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` Q11 as absent ("30 of the 35 survivors"
tested → 5 missing).

---

## Results

| Asset | Strategy | Original OOS Sharpe | p5 Sharpe | p50 Sharpe | p95 Sharpe | Worst-case DD | Flag |
|---|---|---|---|---|---|---|---|
| NVDA | dual_momentum(60,126) | 0.977 | 0.977 | 0.977 | 0.977 | **-61.3%** | **FRAGILE** |
| AMZN | dual_momentum(60,126) | 0.977 | 0.977 | 0.977 | 0.977 | **-48.0%** | **FRAGILE** |
| AMZN | keltner_revert(20, 2.0) | 0.661 | 0.661 | 0.661 | 0.661 | -31.3% | SOLID |
| MSFT | percent_b_revert(20, 0.05/0.95) | 0.627 | 0.627 | 0.627 | 0.627 | -26.3% | SOLID |
| GOOGL | rsi_revert(7, 30/75) | 0.526 | 0.526 | 0.526 | 0.526 | **-36.4%** | **FRAGILE** |

(Note: p5/p50/p95 are numerically identical here because reordering a fixed
set of daily returns does not change the mean/variance-derived Sharpe ratio at
all — Sharpe is invariant to permutation. Only the drawdown path, which is
order-dependent, changes across reshuffles. This matches the identical-Sharpe
pattern already visible in the original `bootstrap_stress_test.csv`.)

---

## Interpretation

- **NVDA `dual_momentum(60,126)` — FRAGILE, -61.3% worst-case drawdown.** This is
  now the single worst bootstrap result of *any* survivor in the entire sweep
  (worse than BTC-USD `atr_breakout`'s -60.1%, the previous record holder). This
  confirms, rather than resolves, the concern already raised in
  `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` Q4/Q11: every sibling `dual_momentum`
  config tested so far (AAPL, MSFT ×2, XLF ×2, XLY, and now NVDA and AMZN) has
  come back FRAGILE except the two on bond/credit-adjacent names (SPY, HYG). The
  #1-ranked survivor by raw OOS Sharpe in the entire sweep is FRAGILE.
- **AMZN `dual_momentum(60,126)` — FRAGILE, -48.0% worst-case drawdown.** Same
  pattern as NVDA — the #2-ranked survivor by raw OOS Sharpe is also FRAGILE.
  Combined with NVDA, this closes out the open question in Q11: **neither of the
  two highest-raw-Sharpe survivors in the whole sweep survives the bootstrap
  stress test.**
- **GOOGL `rsi_revert(7,30/75)` — FRAGILE, -36.4% worst-case drawdown.** Narrowly
  past the -35% floor. This is a mean-reversion family that is otherwise robust
  (ROBUST flag, most other `rsi_revert` survivors SOLID), so this looks like an
  asset-specific fragility rather than a family-wide problem — but it still
  fails the same bar every other survivor was held to.
- **AMZN `keltner_revert(20,2.0)` — SOLID, -31.3%.** Consistent with its sibling
  MSFT `keltner_revert` result (also SOLID, -23.6%) — this strengthens the
  mean-reversion cluster's evidence base as intended.
- **MSFT `percent_b_revert(20,0.05/0.95)` — SOLID, -26.3%.** Consistent with its
  sibling XLK `percent_b_revert` result (also SOLID, -25.1%) — same effect.

## Net effect on the survivor set

- **3 of 5 previously-untested configs are now FRAGILE** (NVDA dual_momentum,
  AMZN dual_momentum, GOOGL rsi_revert) and should move from "NEEDS MORE
  ROBUSTNESS TESTING" to **REJECT**.
- **2 of 5 are now SOLID** (AMZN keltner_revert, MSFT percent_b_revert) and
  should move to **PAPER-TEST CANDIDATE**, consistent with their SOLID siblings.
- The equity-side `dual_momentum` cluster's FRAGILE record is now unanimous:
  every equity/equity-ETF `dual_momentum` survivor tested to date (AAPL ×2, MSFT
  ×2, XLF ×2, XLY, NVDA, AMZN) is FRAGILE. Only the two bond/credit-ETF
  `dual_momentum` survivors (SPY, HYG ×2) are SOLID. This is a strong, now
  fully-confirmed signal that the single-asset momentum edge on individual
  mega-cap tech names is not resilient to return-sequencing — do not paper-test
  any equity-side `dual_momentum` config, including NVDA and AMZN.

No strategy should be promoted to paper-testing based on results in this file
alone without also reviewing `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md`'s updated
classification table.
