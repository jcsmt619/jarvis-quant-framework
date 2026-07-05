"""
edge_hunting/walk_forward.py
==============================
5-window walk-forward validation: each window is split 70% in-sample /
30% out-of-sample (sequential, no shuffling). The OOS tails from all 5
windows are stitched into a single combined OOS series, which is the
primary out-of-sample score because the strategy was never tuned on it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from edge_hunting.backtest_engine import (
    TRADING_DAYS, _max_drawdown, _sharpe, _trade_count, _win_rate,
    compute_position, compute_returns,
)

N_WINDOWS = 5
IN_SAMPLE_FRAC = 0.70


@dataclass
class WalkForwardResult:
    in_sample_sharpe: float
    oos_sharpe: float
    oos_max_drawdown: float
    oos_returns: pd.Series
    oos_position: pd.Series
    oos_trade_count: int
    oos_win_rate: float
    oos_total_return: float
    oos_cagr: float
    oos_turnover: float
    oos_exposure: float
    n_windows: int


def _window_bounds(n: int, n_windows: int = N_WINDOWS) -> list[tuple[int, int]]:
    """Split [0, n) into n_windows sequential, non-overlapping windows."""
    edges = np.linspace(0, n, n_windows + 1, dtype=int)
    return [(edges[i], edges[i + 1]) for i in range(n_windows)]


def run_walk_forward(
    df: pd.DataFrame,
    strategy_fn,
    params: dict,
    cost_bps: float = 1.0,
    n_windows: int = N_WINDOWS,
    in_sample_frac: float = IN_SAMPLE_FRAC,
) -> WalkForwardResult:
    n = len(df)
    windows = _window_bounds(n, n_windows)

    oos_returns_parts: list[pd.Series] = []
    oos_position_parts: list[pd.Series] = []
    in_sample_returns_parts: list[pd.Series] = []

    for start, end in windows:
        if end - start < 10:
            continue
        window_df = df.iloc[start:end]
        split = start + int(round((end - start) * in_sample_frac))
        split = max(split, start + 1)
        split = min(split, end - 1) if end - start > 1 else end

        # Signal is computed on the FULL window (so rolling indicators have
        # enough trailing history) but only the OOS tail's signal/returns
        # are kept -- the in-sample portion of the window is discarded from
        # the final score, per the walk-forward spec.
        signal = strategy_fn(window_df, params)
        position = compute_position(signal)
        returns = compute_returns(window_df["Close"], position, cost_bps=cost_bps)

        in_sample_returns_parts.append(returns.iloc[: split - start])
        oos_returns_parts.append(returns.iloc[split - start:])
        oos_position_parts.append(position.iloc[split - start:])

    if not oos_returns_parts:
        empty = pd.Series(dtype=float)
        return WalkForwardResult(0.0, 0.0, 0.0, empty, empty, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

    oos_returns = pd.concat(oos_returns_parts)
    oos_position = pd.concat(oos_position_parts)
    in_sample_returns = pd.concat(in_sample_returns_parts)

    equity = (1.0 + oos_returns).cumprod()
    n_oos = len(equity)
    years = n_oos / TRADING_DAYS if n_oos else 0.0
    total_return = float(equity.iloc[-1] - 1.0) if n_oos else 0.0
    cagr = float(equity.iloc[-1] ** (1 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else 0.0

    return WalkForwardResult(
        in_sample_sharpe=_sharpe(in_sample_returns.to_numpy()),
        oos_sharpe=_sharpe(oos_returns.to_numpy()),
        oos_max_drawdown=_max_drawdown(equity.to_numpy()),
        oos_returns=oos_returns,
        oos_position=oos_position,
        oos_trade_count=_trade_count(oos_position),
        oos_win_rate=_win_rate(oos_returns, oos_position),
        oos_total_return=total_return,
        oos_cagr=cagr,
        oos_turnover=float(oos_position.diff().abs().fillna(0.0).sum()),
        oos_exposure=float((oos_position != 0).mean()) if n_oos else 0.0,
        n_windows=len(oos_returns_parts),
    )
