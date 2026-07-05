"""
edge_hunting/robustness.py
=============================
Two robustness layers:

1. Parameter sensitivity: group sweep results by strategy family, report
   mean/std of OOS Sharpe and the fraction of configs with positive OOS
   Sharpe. Flags families that only work at one exact setting as
   likely-curve-fit; tight spread + high positive fraction = more robust.

2. Bootstrap stress test: reshuffle a survivor's OOS daily-return ORDER
   (not resample values -- pure reordering) N times, recompute equity
   path & Sharpe per reshuffle, report the percentile distribution and
   flag SOLID vs FRAGILE based on worst-case drawdown survivability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252
DEFAULT_N_RESHUFFLES = 200
FRAGILE_DD_THRESHOLD = -0.35  # worst-case DD worse than this => FRAGILE


@dataclass
class FamilySensitivity:
    family: str
    n_configs: int
    mean_oos_sharpe: float
    std_oos_sharpe: float
    positive_fraction: float
    flag: str  # "ROBUST", "MIXED", "LIKELY_CURVE_FIT"


def parameter_sensitivity(results_df: pd.DataFrame) -> pd.DataFrame:
    """results_df must have columns: family, oos_sharpe."""
    rows = []
    for family, grp in results_df.groupby("family"):
        n = len(grp)
        mean_s = float(grp["oos_sharpe"].mean())
        std_s = float(grp["oos_sharpe"].std(ddof=1)) if n > 1 else 0.0
        pos_frac = float((grp["oos_sharpe"] > 0).mean())

        if n == 1:
            flag = "INSUFFICIENT_CONFIGS"
        elif pos_frac >= 0.6 and std_s < 0.75:
            flag = "ROBUST"
        elif pos_frac <= 0.25 and mean_s > 0:
            flag = "LIKELY_CURVE_FIT"
        else:
            flag = "MIXED"

        rows.append(FamilySensitivity(
            family=family, n_configs=n, mean_oos_sharpe=mean_s,
            std_oos_sharpe=std_s, positive_fraction=pos_frac, flag=flag,
        ))

    return pd.DataFrame([r.__dict__ for r in rows]).sort_values(
        "mean_oos_sharpe", ascending=False
    ).reset_index(drop=True)


@dataclass
class BootstrapStressResult:
    strategy_name: str
    asset: str
    p5_sharpe: float
    p50_sharpe: float
    p95_sharpe: float
    worst_case_drawdown: float
    flag: str  # "SOLID" or "FRAGILE"


def _sharpe(returns: np.ndarray) -> float:
    if returns.size < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, 1, peak)
    return float(dd.min())


def bootstrap_stress_test(
    oos_returns: pd.Series,
    strategy_name: str = "",
    asset: str = "",
    n_reshuffles: int = DEFAULT_N_RESHUFFLES,
    seed: int = 42,
) -> BootstrapStressResult:
    """Reshuffle the ORDER of realized OOS daily returns n_reshuffles times.
    Deterministic given a fixed seed (required for test_edge_hunting_no_lookahead
    determinism test)."""
    rng = np.random.default_rng(seed)
    values = oos_returns.dropna().to_numpy()

    sharpes = np.empty(n_reshuffles)
    worst_dd = 0.0
    for i in range(n_reshuffles):
        shuffled = rng.permutation(values)
        equity = np.cumprod(1.0 + shuffled)
        sharpes[i] = _sharpe(shuffled)
        dd = _max_drawdown(equity)
        worst_dd = min(worst_dd, dd)

    p5, p50, p95 = np.percentile(sharpes, [5, 50, 95])
    flag = "SOLID" if worst_dd > FRAGILE_DD_THRESHOLD else "FRAGILE"

    return BootstrapStressResult(
        strategy_name=strategy_name, asset=asset,
        p5_sharpe=float(p5), p50_sharpe=float(p50), p95_sharpe=float(p95),
        worst_case_drawdown=float(worst_dd), flag=flag,
    )
