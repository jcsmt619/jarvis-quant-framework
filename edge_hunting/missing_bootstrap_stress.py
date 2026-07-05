"""
edge_hunting/missing_bootstrap_stress.py
===========================================
Standalone follow-up script: runs the SAME bootstrap stress test methodology
already used in the sweep (edge_hunting.robustness.bootstrap_stress_test --
200 reshuffles, fixed seed=42, reorder-only OOS daily returns, report
p5/p50/p95 Sharpe + worst-case drawdown + SOLID/FRAGILE classification) on
the survivor configs that are genuinely MISSING from
reports/edge_hunting/bootstrap_stress_test.csv.

Reconciliation note
--------------------
docs/JARVIS_EDGE_HUNTING_ANALYSIS.md's survivor classification table (section
"Classification of every survivor") tags 8 rows as "NEEDS MORE ROBUSTNESS
TESTING" (its summary line says 9 -- a pre-existing off-by-one in that
document that this script does not attempt to silently correct). Of those 8
rows, cross-referencing reports/edge_hunting/bootstrap_stress_test.csv shows:

  - 3 rows ALREADY have bootstrap data in bootstrap_stress_test.csv:
      TLT   pivot_bounce(5, 0.01)              -> SOLID, -31.0% (near floor)
      QQQ   rsi_revert(14, 30/75)              -> SOLID, -13.1%
      EEM   rsi_revert(14, 25/70)               -> SOLID, -11.7%
    These were flagged "NEEDS MORE ROBUSTNESS TESTING" for reasons OTHER than
    missing data (proximity to the -35% floor / low priority per the doc's
    own footnotes), so per the task instruction "Only run bootstrap stress
    testing on the missing survivor configs," they are intentionally NOT
    re-run here.

  - 5 rows are genuinely ABSENT from bootstrap_stress_test.csv. This matches
    docs/JARVIS_EDGE_HUNTING_ANALYSIS.md Q11 verbatim ("Missing: NVDA
    dual_momentum and AMZN dual_momentum ... AMZN keltner_revert, MSFT
    percent_b_revert, and GOOGL rsi_revert" -- "30 of the 35 survivors" =
    5 missing). These 5 are what this script actually runs:

      1. NVDA   dual_momentum(window=60, rel_window=126)
      2. AMZN   dual_momentum(window=60, rel_window=126)
      3. AMZN   keltner_revert(window=20, atr_mult=2.0)
      4. MSFT   percent_b_revert(window=20, lower=0.05, upper=0.95)
      5. GOOGL  rsi_revert(window=7, oversold=30, overbought=75)

Rules followed
--------------
- No parameter tuning: params are copied verbatim from top_survivors.csv.
- No strategy logic changes: uses the existing STRATEGY_REGISTRY functions
  and existing run_walk_forward / bootstrap_stress_test implementations,
  unmodified.
- No funnel threshold changes: this script does not touch funnel.py.
- Does not rerun the full sweep: only loads the 4 assets needed (NVDA, AMZN,
  MSFT, GOOGL) from the existing on-disk parquet cache and runs exactly the
  5 missing configs above.
- Same bootstrap methodology as the original run (robustness.py, unmodified):
  200 reshuffles, seed=42, OOS daily returns, p5/p50/p95 Sharpe, worst-case
  drawdown, SOLID/FRAGILE flag at -35% floor.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from edge_hunting import data_loader
from edge_hunting.backtest_engine import DEFAULT_COST_BPS, CRYPTO_COST_BPS
from edge_hunting.robustness import bootstrap_stress_test
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/edge_hunting")

# Exact (asset, family, params, display_name) tuples for the 5 survivor
# configs that are genuinely absent from bootstrap_stress_test.csv, taken
# verbatim from reports/edge_hunting/top_survivors.csv.
MISSING_CONFIGS = [
    ("NVDA", "dual_momentum", {"window": 60, "rel_window": 126},
     "dual_momentum__window60_rel_window126"),
    ("AMZN", "dual_momentum", {"window": 60, "rel_window": 126},
     "dual_momentum__window60_rel_window126"),
    ("AMZN", "keltner_revert", {"window": 20, "atr_mult": 2.0},
     "keltner_revert__window20_atr_mult2.0"),
    ("MSFT", "percent_b_revert", {"window": 20, "lower": 0.05, "upper": 0.95},
     "percent_b_revert__window20_lower0.05_upper0.95"),
    ("GOOGL", "rsi_revert", {"window": 7, "oversold": 30, "overbought": 75},
     "rsi_revert__window7_oversold30_overbought75"),
]


def _cost_for(asset: str) -> float:
    return CRYPTO_COST_BPS if data_loader.is_crypto(asset) else DEFAULT_COST_BPS


def main():
    assets_needed = sorted({a for a, _, _, _ in MISSING_CONFIGS})
    print(f"Loading assets from cache: {assets_needed}")
    universe = data_loader.load_universe(symbols=assets_needed)
    missing_assets = [a for a in assets_needed if a not in universe]
    if missing_assets:
        print(f"WARNING: could not load (no cache/network): {missing_assets}")

    rows = []
    for asset, family, params, display_name in MISSING_CONFIGS:
        if asset not in universe:
            print(f"SKIP {asset} {display_name}: data unavailable")
            continue
        fn, category, description = STRATEGY_REGISTRY[family]
        df = universe[asset]
        wf = run_walk_forward(df, fn, params, cost_bps=_cost_for(asset))
        stress = bootstrap_stress_test(
            wf.oos_returns, strategy_name=display_name, asset=asset,
        )
        rows.append({
            "strategy_name": stress.strategy_name,
            "asset": stress.asset,
            "p5_sharpe": stress.p5_sharpe,
            "p50_sharpe": stress.p50_sharpe,
            "p95_sharpe": stress.p95_sharpe,
            "worst_case_drawdown": stress.worst_case_drawdown,
            "flag": stress.flag,
            "oos_sharpe_original": wf.oos_sharpe,
            "oos_max_drawdown_original": wf.oos_max_drawdown,
            "trade_count": wf.oos_trade_count,
        })
        print(f"{asset:8s} {display_name:55s} p50={stress.p50_sharpe:+.3f} "
              f"worst_dd={stress.worst_case_drawdown:+.3f} -> {stress.flag}")

    out_df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "missing_bootstrap_stress.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(out_df)} rows)")
    return out_df


if __name__ == "__main__":
    main()
