"""
edge_hunting/benchmark_comparison.py
=======================================
Benchmark comparison for the 7 friction-surviving candidates against:
  1. buy-and-hold of their own traded asset
  2. SPY buy-and-hold
  3. QQQ buy-and-hold
  4. an equal-weight universe buy-and-hold (all assets in the existing
     universe cache, equally weighted, rebalanced daily to target weight --
     a simple descriptive benchmark, not a strategy)

Rules followed
--------------
- No strategy tuning, no strategy-logic changes, no entry/exit rule changes.
- Reuses the existing unmodified edge_hunting.walk_forward.run_walk_forward
  engine (1bp baseline cost) to get each candidate's OOS returns -- same
  methodology as every other section of this analysis.
- Benchmarks are buy-and-hold (position == 1.0 always, no signal, no
  trading logic) evaluated over the SAME OOS date range as each candidate,
  so the comparison is apples-to-apples on out-of-sample days only.
- Nothing here is promoted to paper or live trading.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edge_hunting import data_loader
from edge_hunting.backtest_engine import TRADING_DAYS, _max_drawdown, _sharpe
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/edge_hunting")

CANDIDATES = [
    ("MSFT", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "MSFT keltner_revert(20,2.0)"),
    ("AMZN", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "AMZN keltner_revert(20,2.0)"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 70}, "EEM rsi_revert(14,30/70)"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 25, "overbought": 70}, "EEM rsi_revert(14,25/70)"),
    ("SPY", "dual_momentum", {"window": 60, "rel_window": 126}, "SPY dual_momentum(60,126)"),
    ("HYG", "dual_momentum", {"window": 126, "rel_window": 126}, "HYG dual_momentum(126,126)"),
    ("QQQ", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 75}, "QQQ rsi_revert(14,30/75)"),
]

BENCH_ASSETS = ["SPY", "QQQ"]


def _buy_hold_metrics(close: pd.Series, idx: pd.Index) -> dict:
    """Buy-and-hold return series over the given OOS index (subset of close.index)."""
    ret = close.pct_change().fillna(0.0).reindex(idx).fillna(0.0)
    equity = (1.0 + ret).cumprod()
    n = len(equity)
    total_return = float(equity.iloc[-1] - 1.0) if n else 0.0
    sharpe = _sharpe(ret.to_numpy())
    max_dd = _max_drawdown(equity.to_numpy())
    return {"returns": ret, "sharpe": sharpe, "total_return": total_return, "max_drawdown": max_dd}


def _equal_weight_universe_returns(universe: dict, idx: pd.Index) -> pd.Series:
    """Equal-weight daily-rebalanced buy-and-hold across all cached assets, on idx."""
    rets = []
    for asset, df in universe.items():
        r = df["Close"].pct_change().fillna(0.0).reindex(idx).fillna(0.0)
        rets.append(r)
    if not rets:
        return pd.Series(0.0, index=idx)
    mat = pd.concat(rets, axis=1)
    return mat.mean(axis=1)


def _beta_warning(strategy_ret: pd.Series, asset_ret: pd.Series, corr: float,
                   excess_sharpe: float) -> str:
    if corr >= 0.70 and excess_sharpe <= 0.10:
        return "HIGH — strategy return closely tracks asset buy-and-hold with little/no risk-adjusted edge"
    if corr >= 0.50:
        return "MODERATE — meaningful co-movement with the underlying asset"
    return "LOW"


def _classify(strat_sharpe, bh_sharpe, strat_dd, bh_dd, strat_ret, bh_ret,
              excess_sharpe, excess_return, corr) -> str:
    beats_sharpe = strat_sharpe > bh_sharpe
    beats_return = strat_ret > bh_ret
    smaller_dd = strat_dd > bh_dd  # drawdowns are negative; less negative = smaller

    if corr >= 0.70 and excess_sharpe <= 0.10:
        return "BETA_DISGUISED"
    if beats_sharpe and beats_return and smaller_dd:
        return "ROBUST_CANDIDATE"
    if beats_sharpe and not beats_return:
        return "DEFENSIVE_CANDIDATE"
    if smaller_dd and not beats_return and excess_sharpe <= 0:
        return "DEFENSIVE_CANDIDATE"
    if not beats_sharpe and not beats_return:
        return "REJECT"
    if beats_sharpe and beats_return and not smaller_dd:
        return "ROBUST_CANDIDATE"
    return "REJECT"


def main():
    assets_needed = sorted({a for a, _, _, _ in CANDIDATES} | set(BENCH_ASSETS))
    print(f"Loading assets from cache: {assets_needed}")
    core_universe = data_loader.load_universe(symbols=assets_needed)

    # Try to load the full available universe for the equal-weight benchmark;
    # fall back to just the assets we already have if that manifest isn't
    # available in this environment.
    try:
        full_universe = data_loader.load_universe()
    except Exception as exc:
        print(f"Could not load full universe for equal-weight benchmark ({exc}); "
              f"falling back to the {len(core_universe)} core assets only.")
        full_universe = core_universe

    rows = []
    for asset, family, params, display_name in CANDIDATES:
        if asset not in core_universe:
            print(f"SKIP {display_name}: data unavailable")
            continue
        df = core_universe[asset]
        fn, _, _ = STRATEGY_REGISTRY[family]
        wf = run_walk_forward(df, fn, params, cost_bps=1.0)

        oos_idx = wf.oos_returns.index
        asset_bh = _buy_hold_metrics(df["Close"], oos_idx)

        spy_bh = _buy_hold_metrics(core_universe["SPY"]["Close"], oos_idx) if "SPY" in core_universe else None
        qqq_bh = _buy_hold_metrics(core_universe["QQQ"]["Close"], oos_idx) if "QQQ" in core_universe else None

        ew_ret = _equal_weight_universe_returns(full_universe, oos_idx)
        ew_equity = (1.0 + ew_ret).cumprod()
        ew_sharpe = _sharpe(ew_ret.to_numpy())
        ew_total_return = float(ew_equity.iloc[-1] - 1.0) if len(ew_equity) else 0.0
        ew_max_dd = _max_drawdown(ew_equity.to_numpy())

        common = wf.oos_returns.index.intersection(asset_bh["returns"].index)
        if len(common) >= 10 and wf.oos_returns.reindex(common).std() > 0 and asset_bh["returns"].reindex(common).std() > 0:
            corr = float(np.corrcoef(wf.oos_returns.reindex(common), asset_bh["returns"].reindex(common))[0, 1])
        else:
            corr = 0.0

        excess_return = wf.oos_total_return - asset_bh["total_return"]
        excess_sharpe = wf.oos_sharpe - asset_bh["sharpe"]

        beta_warn = _beta_warning(wf.oos_returns, asset_bh["returns"], corr, excess_sharpe)
        classification = _classify(
            wf.oos_sharpe, asset_bh["sharpe"], wf.oos_max_drawdown, asset_bh["max_drawdown"],
            wf.oos_total_return, asset_bh["total_return"], excess_sharpe, excess_return, corr,
        )

        row = {
            "candidate": display_name,
            "asset": asset,
            "strategy_oos_sharpe": wf.oos_sharpe,
            "asset_bh_oos_sharpe": asset_bh["sharpe"],
            "spy_oos_sharpe": spy_bh["sharpe"] if spy_bh else np.nan,
            "qqq_oos_sharpe": qqq_bh["sharpe"] if qqq_bh else np.nan,
            "equal_weight_universe_oos_sharpe": ew_sharpe,
            "strategy_max_drawdown": wf.oos_max_drawdown,
            "asset_bh_max_drawdown": asset_bh["max_drawdown"],
            "equal_weight_universe_max_drawdown": ew_max_dd,
            "strategy_total_return": wf.oos_total_return,
            "asset_bh_total_return": asset_bh["total_return"],
            "spy_total_return": spy_bh["total_return"] if spy_bh else np.nan,
            "qqq_total_return": qqq_bh["total_return"] if qqq_bh else np.nan,
            "equal_weight_universe_total_return": ew_total_return,
            "excess_return_over_asset_bh": excess_return,
            "excess_sharpe_over_asset_bh": excess_sharpe,
            "correlation_to_asset_returns": corr,
            "beta_disguised_warning": beta_warn,
            "classification": classification,
            "n_oos_days": len(oos_idx),
        }
        rows.append(row)

        print(f"{display_name:35s} strat_sharpe={wf.oos_sharpe:+.2f} bh_sharpe={asset_bh['sharpe']:+.2f} "
              f"excess_sharpe={excess_sharpe:+.2f} excess_ret={excess_return:+.2%} corr={corr:+.2f} "
              f"-> {classification}")

    result_df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "benchmark_comparison.csv"
    result_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(result_df)} candidates)")

    return result_df


if __name__ == "__main__":
    main()
