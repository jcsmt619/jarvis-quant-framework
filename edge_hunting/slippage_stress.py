"""
edge_hunting/slippage_stress.py
===================================
Slippage / transaction-cost stress test for every survivor currently
classified PAPER-TEST CANDIDATE or NEEDS MORE ROBUSTNESS TESTING in
docs/JARVIS_EDGE_HUNTING_ANALYSIS.md.

Reconciliation note (counts): the task refers to "14 paper-test candidates
and 9 missing-bootstrap candidates." The doc's own classification table
currently has 18 rows tagged PAPER-TEST CANDIDATE (after the prior
missing-bootstrap follow-up promoted 2 configs into that bucket) and 3 rows
still tagged NEEDS MORE ROBUSTNESS TESTING (the ones that already had
bootstrap data but were flagged for other reasons -- TLT pivot_bounce, QQQ
rsi_revert(14,30/75), EEM rsi_revert(14,25/70)). This script covers the
union of those two buckets as they exist in the doc TODAY (21 unique
configs), which is the superset of "all paper-test candidates and all
missing-bootstrap candidates" -- nothing in either bucket is skipped.

Rules followed
--------------
- No parameter tuning: every (asset, family, params) tuple below is copied
  verbatim from reports/edge_hunting/top_survivors.csv.
- No strategy logic changes: uses the existing STRATEGY_REGISTRY functions,
  unmodified.
- No entry/exit rule changes: same signal -> compute_position shift-by-one
  contract as the original sweep (edge_hunting.backtest_engine, unmodified).
- No optimization to survive costs: cost_bps is purely an input sweep over
  the SAME strategy/params; nothing is re-fit or adjusted per cost level.
- Does not rerun the full sweep: only loads the assets actually needed, from
  the existing on-disk parquet cache.

Methodology
-----------
For each config, run the existing walk-forward engine
(edge_hunting.walk_forward.run_walk_forward, unmodified) once per cost level
in {1, 5, 10, 25, 50} bps per side. This is the exact same mechanism the
original sweep used for its single 1bp (or 10bp crypto) cost assumption --
we are simply re-invoking it at higher assumed cost levels, not altering how
cost is applied.

Break-even cost estimate: since Sharpe is a linear-ish function of cost only
through the turnover-scaled cost drag on returns (not exactly linear, but the
mean-return decay from cost is exactly linear in cost_bps given a fixed
turnover), estimate the break-even cost_bps by linear interpolation across
the 5 tested cost levels to find where OOS Sharpe crosses 0. If Sharpe never
crosses 0 within [1,50] bps, report ">50" (survives all tested levels) or
"<1" (already negative at the lowest tested level).

Classification rule (per task spec, plus one necessary addition):
- FRAGILE: dies at 5-10bp -- OOS Sharpe <= 0 at 5bp or 10bp.
- STRONGER: survives 10-25bp -- OOS Sharpe > 0 at BOTH 10bp and 25bp.
- MARGINAL: survives 5bp and 10bp but does NOT survive 25bp (a case the task's
  three named buckets don't explicitly cover -- it is not "dies at 5-10bp" and
  it does not "survive 10-25bp" either). Treated the same as "only works at
  1bp" for promotion purposes: NOT allowed to be promoted to paper-trading,
  since realistic all-in friction (spread + slippage + fees) on daily-rebalanced
  ETF/equity strategies commonly exceeds 10bp, especially in stressed markets.
- ONLY_AT_1BP / NO_PAPER_TEST: OOS Sharpe > 0 only at 1bp, <=0 by 5bp (and not
  already FRAGILE by the 5-10bp test above).

Per the task's explicit promotion rule ("if it only works at 1bp, do not allow
paper-trading promotion"), only strategies classified STRONGER are eligible
for paper-trading promotion. FRAGILE, MARGINAL, and ONLY_AT_1BP are all
blocked from promotion.

"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from edge_hunting import data_loader
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/edge_hunting")
COST_LEVELS_BPS = [1.0, 5.0, 10.0, 25.0, 50.0]

# (asset, family, params, display_name, bucket) -- bucket is informational
# only (which classification bucket this config currently sits in, per
# docs/JARVIS_EDGE_HUNTING_ANALYSIS.md at the time this script was written).
CANDIDATES = [
    # --- PAPER-TEST CANDIDATE (18 rows currently in the doc) ---
    ("XLK", "percent_b_revert", {"window": 20, "lower": 0.05, "upper": 0.95},
     "percent_b_revert__window20_lower0.05_upper0.95", "PAPER-TEST CANDIDATE"),
    ("QQQ", "cci_revert", {"window": 20, "threshold": 150},
     "cci_revert__window20_threshold150", "PAPER-TEST CANDIDATE"),
    ("MSFT", "keltner_revert", {"window": 20, "atr_mult": 2.0},
     "keltner_revert__window20_atr_mult2.0", "PAPER-TEST CANDIDATE"),
    ("TLT", "rsi_revert", {"window": 7, "oversold": 25, "overbought": 70},
     "rsi_revert__window7_oversold25_overbought70", "PAPER-TEST CANDIDATE"),
    ("EFA", "rsi_revert", {"window": 7, "oversold": 25, "overbought": 70},
     "rsi_revert__window7_oversold25_overbought70", "PAPER-TEST CANDIDATE"),
    ("AMZN", "keltner_revert", {"window": 20, "atr_mult": 2.0},
     "keltner_revert__window20_atr_mult2.0", "PAPER-TEST CANDIDATE"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 70},
     "rsi_revert__window14_oversold30_overbought70", "PAPER-TEST CANDIDATE"),
    ("SPY", "dual_momentum", {"window": 60, "rel_window": 126},
     "dual_momentum__window60_rel_window126", "PAPER-TEST CANDIDATE"),
    ("EFA", "rsi_revert", {"window": 7, "oversold": 30, "overbought": 70},
     "rsi_revert__window7_oversold30_overbought70", "PAPER-TEST CANDIDATE"),
    ("MSFT", "percent_b_revert", {"window": 20, "lower": 0.05, "upper": 0.95},
     "percent_b_revert__window20_lower0.05_upper0.95", "PAPER-TEST CANDIDATE"),
    ("EEM", "ultimate_oscillator_revert", {"w1": 7, "w2": 14, "w3": 28},
     "ultimate_oscillator_revert__w17_w214_w328", "PAPER-TEST CANDIDATE"),
    ("XLK", "rsi_revert", {"window": 7, "oversold": 30, "overbought": 75},
     "rsi_revert__window7_oversold30_overbought75", "PAPER-TEST CANDIDATE"),
    ("XLK", "bollinger_revert", {"window": 20, "num_std": 2.0},
     "bollinger_revert__window20_num_std2.0", "PAPER-TEST CANDIDATE"),
    ("XLP", "rsi_revert", {"window": 14, "oversold": 25, "overbought": 70},
     "rsi_revert__window14_oversold25_overbought70", "PAPER-TEST CANDIDATE"),
    ("HYG", "dual_momentum", {"window": 126, "rel_window": 126},
     "dual_momentum__window126_rel_window126", "PAPER-TEST CANDIDATE"),
    ("SPY", "rsi_revert", {"window": 7, "oversold": 30, "overbought": 75},
     "rsi_revert__window7_oversold30_overbought75", "PAPER-TEST CANDIDATE"),
    ("EFA", "rsi_revert", {"window": 7, "oversold": 25, "overbought": 75},
     "rsi_revert__window7_oversold25_overbought75", "PAPER-TEST CANDIDATE"),
    ("HYG", "dual_momentum", {"window": 60, "rel_window": 126},
     "dual_momentum__window60_rel_window126", "PAPER-TEST CANDIDATE"),
    # --- NEEDS MORE ROBUSTNESS TESTING (3 rows still in this bucket) ---
    ("TLT", "pivot_bounce", {"window": 5, "tolerance": 0.01},
     "pivot_bounce__window5_tolerance0.01", "NEEDS MORE ROBUSTNESS TESTING"),
    ("QQQ", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 75},
     "rsi_revert__window14_oversold30_overbought75", "NEEDS MORE ROBUSTNESS TESTING"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 25, "overbought": 70},
     "rsi_revert__window14_oversold25_overbought70", "NEEDS MORE ROBUSTNESS TESTING"),
]


def _breakeven_bps(cost_levels: list[float], sharpes: list[float]) -> str:
    """Linear-interpolate the cost_bps at which OOS Sharpe crosses 0."""
    if sharpes[0] <= 0:
        return f"<{cost_levels[0]:.0f}"
    for i in range(1, len(sharpes)):
        if sharpes[i] <= 0:
            x0, x1 = cost_levels[i - 1], cost_levels[i]
            y0, y1 = sharpes[i - 1], sharpes[i]
            if y1 == y0:
                return f"~{x1:.0f}"
            frac = y0 / (y0 - y1)
            be = x0 + frac * (x1 - x0)
            return f"{be:.1f}"
    return f">{cost_levels[-1]:.0f}"


def _classify(cost_levels: list[float], sharpes: list[float]) -> str:
    by_level = dict(zip(cost_levels, sharpes))
    s1 = by_level.get(1.0, sharpes[0])
    s5 = by_level.get(5.0)
    s10 = by_level.get(10.0)
    s25 = by_level.get(25.0)

    if s1 <= 0:
        return "DOES_NOT_WORK_EVEN_AT_1BP"
    if (s5 is not None and s5 <= 0) or (s10 is not None and s10 <= 0):
        return "FRAGILE"
    if s25 is not None and s25 > 0:
        return "STRONGER"
    # Survives 5bp and 10bp but not 25bp -- not covered by the task's three
    # named buckets; blocked from promotion, same as ONLY_AT_1BP.
    return "MARGINAL_NO_PAPER_TEST"



def main():
    assets_needed = sorted({a for a, _, _, _, _ in CANDIDATES})
    print(f"Loading assets from cache: {assets_needed}")
    universe = data_loader.load_universe(symbols=assets_needed)
    missing_assets = [a for a in assets_needed if a not in universe]
    if missing_assets:
        print(f"WARNING: could not load: {missing_assets}")

    rows = []
    for asset, family, params, display_name, bucket in CANDIDATES:
        if asset not in universe:
            print(f"SKIP {asset} {display_name}: data unavailable")
            continue
        fn, category, description = STRATEGY_REGISTRY[family]
        df = universe[asset]

        sharpes = []
        for cost_bps in COST_LEVELS_BPS:
            wf = run_walk_forward(df, fn, params, cost_bps=cost_bps)
            sharpes.append(wf.oos_sharpe)
            rows.append({
                "asset": asset,
                "strategy_name": display_name,
                "bucket": bucket,
                "cost_bps": cost_bps,
                "oos_sharpe": wf.oos_sharpe,
                "oos_max_drawdown": wf.oos_max_drawdown,
                "oos_total_return": wf.oos_total_return,
                "trade_count": wf.oos_trade_count,
                "turnover": wf.oos_turnover,
            })

        breakeven = _breakeven_bps(COST_LEVELS_BPS, sharpes)
        classification = _classify(COST_LEVELS_BPS, sharpes)
        survives_25bp = sharpes[COST_LEVELS_BPS.index(25.0)] > 0
        for r in rows[-len(COST_LEVELS_BPS):]:
            r["breakeven_cost_bps"] = breakeven
            r["classification"] = classification
            r["survives_realistic_friction_25bp"] = survives_25bp

        print(f"{asset:8s} {display_name:55s} "
              f"1bp={sharpes[0]:+.3f} 5bp={sharpes[1]:+.3f} 10bp={sharpes[2]:+.3f} "
              f"25bp={sharpes[3]:+.3f} 50bp={sharpes[4]:+.3f} "
              f"breakeven={breakeven}bp -> {classification}")

    out_df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "slippage_stress.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(out_df)} rows, {len(CANDIDATES)} configs x {len(COST_LEVELS_BPS)} cost levels)")
    return out_df


if __name__ == "__main__":
    main()
