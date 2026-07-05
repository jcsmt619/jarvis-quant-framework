"""
edge_hunting/duplicate_signal_detection.py
==============================================
Duplicate / near-duplicate signal detection among the 7 slippage-stress-
surviving ("friction-surviving") candidates from Section 12 of
docs/JARVIS_EDGE_HUNTING_ANALYSIS.md:

    MSFT keltner_revert, AMZN keltner_revert, EEM rsi_revert(14,30/70),
    EEM rsi_revert(14,25/70), SPY dual_momentum(60,126),
    HYG dual_momentum(126,126), QQQ rsi_revert(14,30/75)

Rules followed
--------------
- Does not delete any strategy, does not change strategy logic, does not
  tune parameters. This module only classifies signal uniqueness by
  comparing already-computed OOS return/position series pairwise.
- Reuses the existing unmodified edge_hunting.walk_forward.run_walk_forward
  engine (1bp baseline cost, same as the original sweep) purely to obtain
  each candidate's OOS returns and OOS position series -- no new backtest
  methodology.
- No sweep re-run; only the assets actually needed are loaded from the
  existing cache.

Pairwise metrics computed
--------------------------
For every pair of the 7 candidates:

- return_correlation: Pearson correlation of daily OOS returns, aligned on
  overlapping trading days (inner join on date index).
- position_correlation: Pearson correlation of the daily OOS position
  series (typically in {-1,0,+1} or similar), same alignment.
- trade_date_overlap: Jaccard-style overlap of "trade days" (days where the
  position CHANGED, i.e. a trade was actually executed) -- 
  |intersection| / |union| of the two candidates' trade-day sets, restricted
  to the overlapping date range.
- parameter_similarity: 1.0 if same strategy family AND identical params,
  0.5 if same family with different params, 0.0 if different families.
- asset_similarity: 1.0 if same asset, else 0.0.

Duplicate classification (per pair)
------------------------------------
- DUPLICATE_SIGNAL: return_correlation >= 0.90 AND position_correlation >=
  0.90 (near-identical trading behavior and near-identical payoff -- this is
  the bar that would be expected for a literal re-expression of the same
  underlying computation, e.g. bollinger_revert vs. zscore_revert on the
  same asset/window, as already identified elsewhere in this project).
- NEAR_DUPLICATE: return_correlation >= 0.60 OR position_correlation >= 0.60
  (meaningfully correlated but not a strict re-expression of the same
  signal -- e.g. two mean-reversion strategies on the same asset that tend
  to trade around the same turning points).
- INDEPENDENT: neither threshold is met.

Per-candidate rollup
--------------------
A candidate is:
- DUPLICATE_SIGNAL   if it has >=1 DUPLICATE_SIGNAL pairing with another
                     candidate in this set.
- NEAR_DUPLICATE     if it has >=1 NEAR_DUPLICATE pairing (and no
                     DUPLICATE_SIGNAL pairing).
- UNIQUE_SIGNAL      if every pairing involving it is INDEPENDENT.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from edge_hunting import data_loader
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/edge_hunting")

CANDIDATES = [
    ("MSFT", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "keltner_revert__window20_atr_mult2.0"),
    ("AMZN", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "keltner_revert__window20_atr_mult2.0"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 70}, "rsi_revert__window14_oversold30_overbought70"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 25, "overbought": 70}, "rsi_revert__window14_oversold25_overbought70"),
    ("SPY", "dual_momentum", {"window": 60, "rel_window": 126}, "dual_momentum__window60_rel_window126"),
    ("HYG", "dual_momentum", {"window": 126, "rel_window": 126}, "dual_momentum__window126_rel_window126"),
    ("QQQ", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 75}, "rsi_revert__window14_oversold30_overbought75"),
]

DUPLICATE_RETURN_THRESH = 0.90
DUPLICATE_POSITION_THRESH = 0.90
NEAR_DUP_RETURN_THRESH = 0.60
NEAR_DUP_POSITION_THRESH = 0.60


def _candidate_id(asset: str, family: str, params: dict) -> str:
    param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    return f"{asset}__{family}__{param_str}"


def _param_similarity(a_family, a_params, b_family, b_params) -> float:
    if a_family != b_family:
        return 0.0
    return 1.0 if a_params == b_params else 0.5


def _trade_days(position: pd.Series) -> set:
    changes = position.diff().fillna(position.abs())
    return set(position.index[changes != 0])


def _pair_classification(ret_corr: float, pos_corr: float) -> str:
    if ret_corr >= DUPLICATE_RETURN_THRESH and pos_corr >= DUPLICATE_POSITION_THRESH:
        return "DUPLICATE_SIGNAL"
    if ret_corr >= NEAR_DUP_RETURN_THRESH or pos_corr >= NEAR_DUP_POSITION_THRESH:
        return "NEAR_DUPLICATE"
    return "INDEPENDENT"


def main():
    assets_needed = sorted({a for a, _, _, _ in CANDIDATES})
    print(f"Loading assets from cache: {assets_needed}")
    universe = data_loader.load_universe(symbols=assets_needed)

    series = {}
    for asset, family, params, display_name in CANDIDATES:
        if asset not in universe:
            print(f"SKIP {asset} {display_name}: data unavailable")
            continue
        df = universe[asset]
        fn, _, _ = STRATEGY_REGISTRY[family]
        wf = run_walk_forward(df, fn, params, cost_bps=1.0)
        cid = _candidate_id(asset, family, params)
        series[cid] = {
            "asset": asset, "family": family, "params": params,
            "display_name": display_name,
            "returns": wf.oos_returns, "position": wf.oos_position,
        }

    ids = list(series.keys())
    rows = []
    for id_a, id_b in combinations(ids, 2):
        a, b = series[id_a], series[id_b]

        common_idx = a["returns"].index.intersection(b["returns"].index)
        n_common = len(common_idx)

        if n_common >= 10:
            ra = a["returns"].reindex(common_idx)
            rb = b["returns"].reindex(common_idx)
            pa = a["position"].reindex(common_idx)
            pb = b["position"].reindex(common_idx)

            ret_corr = float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else 0.0
            pos_corr = float(np.corrcoef(pa, pb)[0, 1]) if pa.std() > 0 and pb.std() > 0 else 0.0

            trades_a = _trade_days(a["position"]) & set(common_idx)
            trades_b = _trade_days(b["position"]) & set(common_idx)
            union = trades_a | trades_b
            trade_overlap = len(trades_a & trades_b) / len(union) if union else 0.0
        else:
            ret_corr, pos_corr, trade_overlap = 0.0, 0.0, 0.0

        param_sim = _param_similarity(a["family"], a["params"], b["family"], b["params"])
        asset_sim = 1.0 if a["asset"] == b["asset"] else 0.0

        pair_class = _pair_classification(ret_corr, pos_corr)
        if n_common < 10:
            pair_class = "INSUFFICIENT_OVERLAP"

        rows.append({
            "candidate_a": id_a,
            "candidate_b": id_b,
            "asset_a": a["asset"], "asset_b": b["asset"],
            "strategy_a": a["display_name"], "strategy_b": b["display_name"],
            "n_common_oos_days": n_common,
            "return_correlation": ret_corr,
            "position_correlation": pos_corr,
            "trade_date_overlap": trade_overlap,
            "parameter_similarity": param_sim,
            "asset_similarity": asset_sim,
            "pair_classification": pair_class,
        })

        print(f"{id_a:60s} vs {id_b:60s} "
              f"ret_corr={ret_corr:+.3f} pos_corr={pos_corr:+.3f} "
              f"trade_overlap={trade_overlap:.3f} param_sim={param_sim:.1f} "
              f"asset_sim={asset_sim:.1f} n_common={n_common} -> {pair_class}")

    pair_df = pd.DataFrame(rows)

    # Per-candidate rollup classification.
    rollup = {}
    for cid in ids:
        involved = pair_df[(pair_df["candidate_a"] == cid) | (pair_df["candidate_b"] == cid)]
        if (involved["pair_classification"] == "DUPLICATE_SIGNAL").any():
            rollup[cid] = "DUPLICATE_SIGNAL"
        elif (involved["pair_classification"] == "NEAR_DUPLICATE").any():
            rollup[cid] = "NEAR_DUPLICATE"
        else:
            rollup[cid] = "UNIQUE_SIGNAL"

    print("\nPer-candidate rollup classification:")
    for cid, cls in rollup.items():
        print(f"  {cid:60s} -> {cls}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "duplicate_signal_report.csv"
    pair_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(pair_df)} pairs)")

    return pair_df, rollup


if __name__ == "__main__":
    main()
