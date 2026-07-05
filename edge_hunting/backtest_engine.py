"""
edge_hunting/backtest_engine.py
=================================
Single source of truth for the anti-lookahead boundary and daily return
calculation. No broker, no execution, no live trading -- this is a pure
research/backtest computation module.

Contract:
    position[t] = signal[t-1]     (the signal computed using data through
                                    day t-1 is what's HELD during day t)
    daily_return[t] = position[t] * asset_return[t] - transaction_cost[t]
    transaction_cost[t] = cost_per_side * |position[t] - position[t-1]|

This means a signal computed using data available through day T-1 is
applied to earn day T's return -- i.e. "position for day T must only use
data available through day T-1 or earlier", exactly as specified.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS = 252
DEFAULT_COST_BPS = 1.0          # 1 bp per side, equities/ETFs
CRYPTO_COST_BPS = 10.0          # configurable higher cost for crypto


@dataclass
class BacktestResult:
    asset: str
    strategy_name: str
    position: pd.Series
    returns: pd.Series
    equity: pd.Series
    sharpe: float
    max_drawdown: float
    total_return: float
    cagr: float
    trade_count: int
    win_rate: float
    exposure: float
    turnover: float
    meta: dict = field(default_factory=dict)


def compute_position(signal: pd.Series) -> pd.Series:
    """Shift signal by 1 bar -> the position HELD (and traded) for day t.

    This is the single place the anti-lookahead boundary is enforced:
    signal[t-1] (computed using data through t-1) becomes position[t].
    """
    return signal.shift(1).fillna(0.0)


def compute_returns(
    close: pd.Series,
    position: pd.Series,
    cost_bps: float = DEFAULT_COST_BPS,
) -> pd.Series:
    """daily_return[t] = position[t] * asset_return[t] - cost * turnover[t]"""
    asset_return = close.pct_change().fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    cost = (cost_bps / 10000.0) * turnover
    return position * asset_return - cost


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, 1, peak)
    return float(dd.min())


def _sharpe(returns: np.ndarray) -> float:
    if returns.size < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _trade_count(position: pd.Series) -> int:
    changes = position.diff().fillna(0.0)
    # A "trade" occurs whenever position moves through/away from zero into
    # a new state (entry or flip); count nonzero transitions in position.
    return int((changes != 0).sum())


def _win_rate(returns: pd.Series, position: pd.Series) -> float:
    """Win rate over discrete trade segments (contiguous nonzero position runs)."""
    pos = position.fillna(0.0)
    segment_id = (pos != pos.shift(1)).cumsum()
    active = pos != 0
    if not active.any():
        return 0.0
    df = pd.DataFrame({"ret": returns, "seg": segment_id, "active": active})
    df = df[df["active"]]
    if df.empty:
        return 0.0
    seg_pnl = df.groupby("seg")["ret"].sum()
    if len(seg_pnl) == 0:
        return 0.0
    return float((seg_pnl > 0).sum() / len(seg_pnl))


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    asset: str = "",
    strategy_name: str = "",
    cost_bps: float = DEFAULT_COST_BPS,
    initial_capital: float = 100_000.0,
) -> BacktestResult:
    """Run one asset x strategy backtest. `signal` must be aligned to df.index."""
    signal = signal.reindex(df.index).fillna(0.0)
    position = compute_position(signal)
    returns = compute_returns(df["Close"], position, cost_bps=cost_bps)

    equity = initial_capital * (1.0 + returns).cumprod()
    n = len(equity)
    years = n / TRADING_DAYS if n else 0.0
    total_return = float(equity.iloc[-1] / initial_capital - 1.0) if n else 0.0
    cagr = float((equity.iloc[-1] / initial_capital) ** (1 / years) - 1.0) if years > 0 else 0.0

    exposure = float((position != 0).mean()) if n else 0.0
    turnover = float(position.diff().abs().fillna(0.0).sum())

    return BacktestResult(
        asset=asset,
        strategy_name=strategy_name,
        position=position,
        returns=returns,
        equity=equity,
        sharpe=_sharpe(returns.to_numpy()),
        max_drawdown=_max_drawdown(equity.to_numpy()),
        total_return=total_return,
        cagr=cagr,
        trade_count=_trade_count(position),
        win_rate=_win_rate(returns, position),
        exposure=exposure,
        turnover=turnover,
    )
