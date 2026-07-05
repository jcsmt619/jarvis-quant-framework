"""
edge_hunting/run_sweep.py
============================
CLI entrypoint that orchestrates the full sweep:
  1. Load universe (data_loader)
  2. Build strategy configs (parameter_grid)
  3. Walk-forward backtest every asset x config (walk_forward)
  4. Apply the 6-filter funnel (funnel)
  5. Run parameter sensitivity + bootstrap stress test on survivors (robustness)
  6. Run standalone cross-sectional momentum test (cross_sectional)
  7. Write all reports (report_writer)

Usage:
    python -m edge_hunting.run_sweep [--quick] [--symbols SPY,QQQ,...] [--out-dir reports/edge_hunting]

No broker, no execution, no live trading -- pure research CLI.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from edge_hunting import data_loader
from edge_hunting.backtest_engine import DEFAULT_COST_BPS, CRYPTO_COST_BPS
from edge_hunting.cross_sectional import run_cross_sectional_momentum, walk_forward_cross_sectional
from edge_hunting.funnel import FunnelThresholds, evaluate_funnel, failure_detail
from edge_hunting.parameter_grid import build_strategy_configs, summarize
from edge_hunting.report_writer import (
    write_cross_sectional_report, write_funnel_report, write_sweep_results, write_top_survivors,
)
from edge_hunting.robustness import bootstrap_stress_test, parameter_sensitivity
from edge_hunting.walk_forward import run_walk_forward


def _cost_for(asset: str) -> float:
    return CRYPTO_COST_BPS if data_loader.is_crypto(asset) else DEFAULT_COST_BPS


def run_sweep(
    symbols: list[str] | None,
    out_dir: Path,
    quick: bool,
    start: str,
    end: str,
) -> pd.DataFrame:
    print("=== Step 1/6: Loading universe ===")
    universe = data_loader.load_universe(symbols=symbols, start=start, end=end)
    if not universe:
        print("ERROR: no assets loaded (network unavailable or all symbols failed). Aborting.")
        return pd.DataFrame()
    print(f"Loaded {len(universe)} assets: {sorted(universe.keys())}")

    print("\n=== Step 2/6: Building strategy configs ===")
    configs = build_strategy_configs()
    if quick:
        configs = configs[:20]
    print(summarize(configs, n_assets=len(universe)))

    print("\n=== Step 3/6: Running walk-forward backtests ===")
    thresholds = FunnelThresholds()
    rows = []
    t0 = time.time()
    total = len(universe) * len(configs)
    done = 0
    for asset, df in universe.items():
        cost_bps = _cost_for(asset)
        for cfg in configs:
            try:
                wf = run_walk_forward(df, cfg.function, cfg.params, cost_bps=cost_bps)
            except Exception as exc:
                done += 1
                continue

            verdict = evaluate_funnel(
                in_sample_sharpe=wf.in_sample_sharpe,
                oos_sharpe=wf.oos_sharpe,
                oos_max_drawdown=wf.oos_max_drawdown,
                trade_count=wf.oos_trade_count,
                thresholds=thresholds,
            )
            reason = ""
            if not verdict.survived:
                reason = failure_detail(
                    verdict.failure_reason, wf.in_sample_sharpe, wf.oos_sharpe,
                    wf.oos_max_drawdown, wf.oos_trade_count, thresholds,
                )

            rows.append({
                "asset": asset,
                "strategy_name": cfg.name,
                "family": cfg.family,
                "category": cfg.category,
                "params": str(cfg.params),
                "in_sample_sharpe": wf.in_sample_sharpe,
                "oos_sharpe": wf.oos_sharpe,
                "oos_max_drawdown": wf.oos_max_drawdown,
                "oos_total_return": wf.oos_total_return,
                "oos_cagr": wf.oos_cagr,
                "trade_count": wf.oos_trade_count,
                "win_rate": wf.oos_win_rate,
                "turnover": wf.oos_turnover,
                "exposure": wf.oos_exposure,
                "survived": verdict.survived,
                "failure_reason": verdict.failure_reason,
                "failure_detail": reason,
            })
            done += 1
            if done % 200 == 0:
                elapsed = time.time() - t0
                print(f"  {done}/{total} backtests complete ({elapsed:.1f}s elapsed)")

    results_df = pd.DataFrame(rows)
    print(f"\nCompleted {len(results_df)} backtests in {time.time() - t0:.1f}s")

    print("\n=== Step 4/6: Writing funnel + sweep reports ===")
    write_sweep_results(results_df, out_dir)
    write_top_survivors(results_df, out_dir)
    write_funnel_report(results_df, out_dir)

    print("\n=== Step 5/6: Robustness (parameter sensitivity + bootstrap stress test) ===")
    if not results_df.empty:
        sensitivity_df = parameter_sensitivity(results_df)
        sensitivity_df.to_csv(out_dir / "parameter_sensitivity.csv", index=False)
        print(sensitivity_df.to_string(index=False))

        survivors = results_df[results_df["survived"] == True]  # noqa: E712
        stress_rows = []
        for _, row in survivors.head(30).iterrows():
            asset_df = universe[row["asset"]]
            cfg = next((c for c in configs if c.name == row["strategy_name"]), None)
            if cfg is None:
                continue
            wf = run_walk_forward(asset_df, cfg.function, cfg.params, cost_bps=_cost_for(row["asset"]))
            stress = bootstrap_stress_test(wf.oos_returns, strategy_name=cfg.name, asset=row["asset"])
            stress_rows.append(stress.__dict__)
        if stress_rows:
            stress_df = pd.DataFrame(stress_rows)
            stress_df.to_csv(out_dir / "bootstrap_stress_test.csv", index=False)
            print(stress_df.to_string(index=False))

    print("\n=== Step 6/6: Cross-sectional momentum (standalone test) ===")
    cs_rows = []
    if len(universe) >= 3:
        for lookback in ["3m", "6m", "12_1"]:
            try:
                res = walk_forward_cross_sectional(universe, lookback=lookback)
                cs_rows.append(res)
            except Exception as exc:
                print(f"  cross-sectional {lookback} failed: {exc}")
    momentum_comparison = results_df[results_df["family"].isin(
        ["ts_momentum", "roc_momentum", "dual_momentum"]
    )] if not results_df.empty else pd.DataFrame()
    if cs_rows:
        write_cross_sectional_report(cs_rows, momentum_comparison, out_dir)

    return results_df


def main():
    parser = argparse.ArgumentParser(description="Run the edge-hunting strategy sweep.")
    parser.add_argument("--symbols", type=str, default=None,
                         help="Comma-separated symbol list; default is the built-in universe.")
    parser.add_argument("--out-dir", type=str, default="reports/edge_hunting")
    parser.add_argument("--quick", action="store_true", help="Run a small subset for a fast smoke test.")
    parser.add_argument("--start", type=str, default="2010-01-01")
    parser.add_argument("--end", type=str, default="2025-01-01")
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else None
    out_dir = Path(args.out_dir)

    run_sweep(symbols=symbols, out_dir=out_dir, quick=args.quick, start=args.start, end=args.end)


if __name__ == "__main__":
    main()
