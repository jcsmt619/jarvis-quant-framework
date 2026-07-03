"""Validation: the big three.

A single backtest number means little. These three checks are what separate a
system you can trust from a curve you fit by accident.

1. Walk-forward. The backtester already trades only out-of-sample data. This
   summarises how much edge survives out of sample versus in sample.
2. Monte Carlo. The order of trades is partly luck. Reshuffle and resample the
   trade sequence many times to get a distribution of outcomes and, for a funded
   account, the probability of breaching the trailing drawdown.
3. Sensitivity. A robust system does not fall apart when a parameter moves a
   little. Perturb the key knobs and check the result is stable rather than a
   sharp peak you happened to land on.

This module is also the backbone of the standalone backtesting guide, so the
functions are written to be called on any trade list, not just this system's.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from backtest.backtester import BacktestResult, WalkForwardBacktester
from backtest.performance import analyze


@dataclass
class MonteCarloResult:
    n_runs: int
    median_final_pnl: float
    p05_final_pnl: float
    p95_final_pnl: float
    median_max_drawdown: float
    worst_max_drawdown: float
    prob_breach_trailing: float
    samples: np.ndarray = field(default_factory=lambda: np.array([]))


def monte_carlo(trades: pd.DataFrame, initial_equity: float,
                trailing_max_drawdown: float = 0.0, n_runs: int = 2000,
                seed: int = 11) -> MonteCarloResult:
    """Bootstrap the trade sequence to a distribution of outcomes."""
    if trades is None or trades.empty:
        return MonteCarloResult(0, 0, 0, 0, 0, 0, 0.0)
    pnl = trades["pnl"].astype(float).to_numpy()
    rng = np.random.default_rng(seed)

    finals, dds, breaches = [], [], 0
    for _ in range(n_runs):
        sampled = rng.choice(pnl, size=len(pnl), replace=True)
        equity = initial_equity + np.cumsum(sampled)
        running_max = np.maximum.accumulate(np.concatenate([[initial_equity], equity]))
        dd = (np.concatenate([[initial_equity], equity]) - running_max).min()
        finals.append(equity[-1] - initial_equity)
        dds.append(dd)
        if trailing_max_drawdown > 0 and abs(dd) >= trailing_max_drawdown:
            breaches += 1

    finals = np.array(finals)
    dds = np.array(dds)
    return MonteCarloResult(
        n_runs=n_runs,
        median_final_pnl=float(np.median(finals)),
        p05_final_pnl=float(np.percentile(finals, 5)),
        p95_final_pnl=float(np.percentile(finals, 95)),
        median_max_drawdown=float(np.median(dds)),
        worst_max_drawdown=float(dds.min()),
        prob_breach_trailing=breaches / n_runs if n_runs else 0.0,
        samples=finals,
    )


@dataclass
class SensitivityResult:
    table: pd.DataFrame
    base_pnl: float
    stable: bool
    note: str


def sensitivity(bars: pd.DataFrame, symbol: str, base_config: dict,
                grid: Optional[dict[str, list]] = None) -> SensitivityResult:
    """Re-run the backtest while perturbing key parameters one at a time."""
    grid = grid or {
        "risk.risk_per_trade": [0.003, 0.005, 0.0075, 0.01],
        "strategy.stop_atr": [0.75, 1.0, 1.25, 1.5],
        "strategy.target_atr": [1.5, 2.0, 2.5, 3.0],
        "hmm.stability_bars": [1, 2, 3, 4],
    }
    rows = []
    base_pnl = _run_pnl(bars, symbol, base_config)
    for path, values in grid.items():
        for v in values:
            cfg = _set_path(copy.deepcopy(base_config), path, v)
            pnl = _run_pnl(bars, symbol, cfg)
            rows.append({"parameter": path, "value": v, "total_pnl": round(pnl, 0),
                         "delta_vs_base": round(pnl - base_pnl, 0)})
    table = pd.DataFrame(rows)
    # Stable if no single perturbation flips a profitable base to a large loss.
    stable = True
    note = "result is stable across the tested parameter ranges"
    if base_pnl > 0:
        worst = table["total_pnl"].min()
        if worst < -abs(base_pnl):
            stable = False
            note = "result is fragile: a parameter move turns the edge sharply negative"
    return SensitivityResult(table=table, base_pnl=base_pnl, stable=stable, note=note)


@dataclass
class WalkForwardSummary:
    windows: int
    oos_total_pnl: float
    oos_return_pct: float
    oos_sharpe: float
    prop_firm_pass: bool
    note: str


def walk_forward_summary(result: BacktestResult, config: dict) -> WalkForwardSummary:
    rep = analyze(result, config)
    return WalkForwardSummary(
        windows=result.windows,
        oos_total_pnl=rep.total_pnl,
        oos_return_pct=rep.return_pct,
        oos_sharpe=rep.sharpe,
        prop_firm_pass=rep.prop_firm_pass,
        note=rep.prop_firm_note,
    )


# -- helpers ---------------------------------------------------------------

def _run_pnl(bars: pd.DataFrame, symbol: str, config: dict) -> float:
    bt = WalkForwardBacktester(config)
    res = bt.run(bars, symbol)
    rep = analyze(res, config)
    return rep.total_pnl


def _set_path(config: dict, dotted: str, value) -> dict:
    keys = dotted.split(".")
    node = config
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    return config
