# Slippage / Transaction-Cost Stress Test

**Scope:** Every survivor currently classified **PAPER-TEST CANDIDATE** (18
rows) or **NEEDS MORE ROBUSTNESS TESTING** (3 rows still in that bucket after
the prior bootstrap follow-up) in `docs/JARVIS_EDGE_HUNTING_ANALYSIS.md` — 21
unique configs. This is the superset of "all paper-test candidates and all
missing-bootstrap candidates" referenced in the task; see the count
reconciliation note in `edge_hunting/slippage_stress.py`'s module docstring
for why the doc's own bucket sizes (14/9) differ slightly from what's
currently in the table (18/3) — a pre-existing documentation drift, not
introduced by this run.

**Rules followed:** no parameter tuning, no strategy-logic changes, no
entry/exit rule changes, no optimization to survive costs. The exact same
unmodified `edge_hunting.walk_forward.run_walk_forward` engine and the exact
same `params` from `top_survivors.csv` were used for every config — the ONLY
thing varied across the 5 runs per config is the `cost_bps` input, which the
engine already supported (`edge_hunting.backtest_engine.compute_returns`
applies `cost = (cost_bps/10000) * turnover` — unmodified). No sweep re-run;
only the 10 assets actually needed were loaded from the existing parquet
cache.

**Cost levels tested (per side):** 1bp, 5bp, 10bp, 25bp, 50bp.

**Classification rule:**
- **FRAGILE** — dies at 5-10bp (OOS Sharpe <= 0 by 5bp or 10bp).
- **STRONGER** — survives 10-25bp (OOS Sharpe > 0 at both 10bp AND 25bp).
- **MARGINAL_NO_PAPER_TEST** — survives 5bp/10bp but dies by 25bp. Not one of
  the three named buckets in the task, but treated identically to
  "only works at 1bp" for promotion purposes (blocked from paper-trading),
  since realistic all-in retail/small-fund friction (spread + slippage +
  commission) on daily-rebalanced ETF/equity mean-reversion strategies
  routinely reaches or exceeds 10-25bp, especially during the volatility
  spikes when these strategies actually try to trade.
- **DOES_NOT_WORK_EVEN_AT_1BP** — negative even at the lowest cost tested
  (none observed in this run).

Per the task's explicit rule ("if it only works at 1bp, do not allow
paper-trading promotion"), **only STRONGER-classified configs are eligible
for promotion.**

---

## Results (full detail in `reports/edge_hunting/slippage_stress.csv`)

| Asset | Strategy | 1bp | 5bp | 10bp | 25bp | 50bp | Break-even (bp) | Classification |
|---|---|---|---|---|---|---|---|---|
| MSFT | keltner_revert(20,2.0) | +0.71 | +0.61 | +0.48 | **+0.08** | -0.57 | 28.1 | **STRONGER** |
| AMZN | keltner_revert(20,2.0) | +0.66 | +0.58 | +0.48 | **+0.17** | -0.34 | 33.2 | **STRONGER** |
| EEM | rsi_revert(14,30/70) | +0.65 | +0.56 | +0.45 | **+0.11** | -0.44 | 30.0 | **STRONGER** |
| SPY | dual_momentum(60,126) | +0.64 | +0.58 | +0.51 | **+0.31** | -0.03 | 48.0 | **STRONGER** |
| HYG | dual_momentum(126,126) | +0.54 | +0.46 | +0.36 | **+0.07** | -0.39 | 28.7 | **STRONGER** |
| QQQ | rsi_revert(14,30/75) | +0.57 | +0.50 | +0.42 | **+0.17** | -0.22 | 36.0 | **STRONGER** |
| EEM | rsi_revert(14,25/70) | +0.54 | +0.47 | +0.38 | **+0.12** | -0.31 | 31.8 | **STRONGER** |
| XLK | percent_b_revert(20,.05/.95) | +0.84 | +0.68 | +0.48 | -0.13 | -1.09 | 21.9 | MARGINAL_NO_PAPER_TEST |
| QQQ | cci_revert(20,150) | +0.73 | +0.58 | +0.39 | -0.16 | -1.04 | 20.6 | MARGINAL_NO_PAPER_TEST |
| TLT | rsi_revert(7,25/70) | +0.70 | +0.44 | +0.13 | -0.80 | -2.15 | 12.1 | MARGINAL_NO_PAPER_TEST |
| EFA | rsi_revert(7,25/70) | +0.69 | +0.45 | +0.15 | -0.75 | -2.09 | 12.5 | MARGINAL_NO_PAPER_TEST |
| EFA | rsi_revert(7,30/70) | +0.64 | +0.40 | +0.10 | -0.77 | -2.10 | 11.7 | MARGINAL_NO_PAPER_TEST |
| MSFT | percent_b_revert(20,.05/.95) | +0.63 | +0.50 | +0.34 | -0.13 | -0.89 | 21.0 | MARGINAL_NO_PAPER_TEST |
| EEM | ultimate_oscillator_revert(7,14,28) | +0.62 | +0.51 | +0.38 | -0.03 | -0.67 | 24.1 | MARGINAL_NO_PAPER_TEST |
| XLK | rsi_revert(7,30/75) | +0.62 | +0.47 | +0.28 | -0.28 | -1.17 | 17.6 | MARGINAL_NO_PAPER_TEST |
| XLK | bollinger_revert(20,2.0) | +0.60 | +0.46 | +0.29 | -0.23 | -1.06 | 18.3 | MARGINAL_NO_PAPER_TEST |
| XLP | rsi_revert(14,25/70) | +0.54 | +0.41 | +0.25 | -0.23 | -0.93 | 17.9 | MARGINAL_NO_PAPER_TEST |
| SPY | rsi_revert(7,30/75) | +0.54 | +0.36 | +0.13 | -0.54 | -1.58 | 12.9 | MARGINAL_NO_PAPER_TEST |
| EFA | rsi_revert(7,25/75) | +0.53 | +0.33 | +0.08 | -0.66 | -1.79 | 11.7 | MARGINAL_NO_PAPER_TEST |
| HYG | dual_momentum(60,126) | +0.52 | +0.37 | +0.18 | -0.36 | -1.17 | 15.0 | MARGINAL_NO_PAPER_TEST |
| TLT | pivot_bounce(5,0.01) | +0.64 | +0.24 | **-0.26** | -1.71 | -3.85 | 7.4 | **FRAGILE** |

(Max drawdown / total return / trade count / turnover per cost level are in
the full CSV — omitted here for readability. Every config's trade count and
turnover are, as expected, identical across all 5 cost levels: cost changes
the return magnitude per trade, not the number or timing of trades, since
signal/position logic is completely untouched.)

---

## Interpretation

**Only 7 of 21 configs (33%) are actually robust to realistic friction** —
they keep a positive OOS Sharpe through 25bp per side (STRONGER). These are:
`MSFT keltner_revert`, `AMZN keltner_revert`, `EEM rsi_revert(14,30/70)`,
`SPY dual_momentum`, `HYG dual_momentum(126,126)`, `QQQ rsi_revert(14,30/75)`,
`EEM rsi_revert(14,25/70)`. Their break-even costs range from 28bp to 48bp —
comfortably above what a retail or small-fund trader is likely to pay on
liquid large-caps/ETFs (typical all-in cost estimates run roughly 2-15bp for
this universe), giving genuine margin of safety.

**13 of 21 (62%) are MARGINAL — they look fine at the sweep's original 1bp
assumption but their edge evaporates well before 25bp**, with break-even
costs clustered in the 11-24bp range. Every `rsi_revert` variant on TLT/EFA/
SPY/XLP (7 configs) breaks even below 13bp — meaning even a modest, realistic
increase in assumed friction (e.g. wider bid/ask on a volatility spike day,
a market order instead of a limit order, or a small broker commission) is
enough to erase the entire edge. **This directly matches the task's warning:
these were profitable-looking survivors in the original 1bp sweep, but "only
work at 1bp" and must not be promoted to paper-trading** under the stated
rule, regardless of how good their bootstrap/robustness numbers looked. Note
this includes 4 configs that were bootstrap-SOLID (MSFT/XLK percent_b_revert,
XLK bollinger_revert, XLK rsi_revert) — bootstrap-SOLID and cost-robust are
different, non-redundant tests, and this run shows a strategy can pass one
and fail the other.

**1 of 21 (`TLT pivot_bounce`) is FRAGILE by the task's strict definition** —
it dies (Sharpe goes negative) already at 10bp, with a break-even around
7.4bp. This strategy was already flagged in the doc as "SOLID but near the
-35% floor" from the bootstrap test; this slippage result adds an independent
reason to keep it out of paper-trading, and is consistent with its earlier
flag.

**Notable pattern:** the 7 STRONGER survivors are disproportionately
`dual_momentum` (3 of 7) and `keltner_revert`/wider-window `rsi_revert`
configs (14-day, not 7-day) — these tend to have lower turnover per unit of
OOS return, so a given bp of cost eats a smaller share of the edge. The
MARGINAL bucket is dominated by short-window (`window=7`) `rsi_revert`
configs and the various `percent_b_revert`/`bollinger_revert`/`cci_revert`
mean-reversion strategies, which trade more frequently for a similar-sized
edge and are therefore proportionally more cost-sensitive.

## Net effect on paper-trading eligibility

Of the 21 configs tested, **only these 7 remain eligible for paper-trading
promotion** under the task's rule (must survive realistic friction, not just
1bp):

1. MSFT `keltner_revert(20,2.0)`
2. AMZN `keltner_revert(20,2.0)`
3. EEM `rsi_revert(14,30/70)`
4. SPY `dual_momentum(60,126)`
5. HYG `dual_momentum(126,126)`
6. QQQ `rsi_revert(14,30/75)`
7. EEM `rsi_revert(14,25/70)`

The other **14 configs are blocked from paper-trading promotion** pending
either a materially better realistic-cost estimate for the specific
venue/broker being used, or further work reducing turnover — they are NOT
rejected outright (their raw funnel/bootstrap results still stand), but they
must not be promoted to paper-trading as-is.
