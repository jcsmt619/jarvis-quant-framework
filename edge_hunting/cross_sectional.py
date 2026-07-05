"""
edge_hunting/cross_sectional.py
==================================
Standalone cross-sectional momentum test. Ranks assets against EACH OTHER
(not against their own history in isolation) using only trailing/past
data, rebalances every 21 trading days, goes long the top third and short
the bottom third, equal-weighted, held to next rebalance.

No lookahead: on each rebalance date t, ranks are computed using return
data through t (close-to-close), and the resulting long/short weights are
held starting the NEXT trading day (t+1) -- same shift-by-one-bar
discipline as the single-asset engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252
REBALANCE_FREQ = 21

LOOKBACKS = {
    "3m": 63,
    "6m": 126,
    "12_1": None,  # special-cased: 252-day lookback, skip most recent 21 days
}


def _trailing_return(prices: pd.Series, window: int, skip_recent: int = 0) -> float | None:
    if skip_recent > 0:
        if len(prices) < window + skip_recent:
            return None
        end = prices.iloc[-(skip_recent + 1)]
        start = prices.iloc[-(window + skip_recent + 1)]
    else:
        if len(prices) < window + 1:
            return None
        end = prices.iloc[-1]
        start = prices.iloc[-(window + 1)]
    if start == 0 or np.isnan(start) or np.isnan(end):
        return None
    return float(end / start - 1.0)


def _rank_universe(
    closes: dict[str, pd.Series],
    as_of_idx: int,
    lookback_key: str,
) -> dict[str, float]:
    """Compute trailing return per asset using ONLY data up to and
    including as_of_idx (positional index into each asset's own series,
    already aligned to a common calendar upstream)."""
    scores = {}
    for asset, series in closes.items():
        window_data = series.iloc[: as_of_idx + 1]
        if lookback_key == "12_1":
            r = _trailing_return(window_data, window=252 - 21, skip_recent=21)
        else:
            r = _trailing_return(window_data, window=LOOKBACKS[lookback_key])
        if r is not None:
            scores[asset] = r
    return scores


@dataclass
class CrossSectionalResult:
    lookback: str
    weights_history: pd.DataFrame       # rebalance_date x asset -> weight
    portfolio_returns: pd.Series
    sharpe: float
    max_drawdown: float
    turnover: float
    trade_count: int


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


def run_cross_sectional_momentum(
    price_data: dict[str, pd.DataFrame],
    lookback: str = "6m",
    rebalance_freq: int = REBALANCE_FREQ,
    cost_bps: float = 1.0,
) -> CrossSectionalResult:
    """price_data: {asset: OHLCV df}. Uses Close only. All assets are
    reindexed to a common trading calendar (union of indices, forward-
    filled -- but ranking always uses only data through the rebalance
    date, so no lookahead is introduced by the reindex itself)."""
    closes = {a: df["Close"] for a, df in price_data.items()}
    common_index = sorted(set().union(*[set(s.index) for s in closes.values()]))
    common_index = pd.DatetimeIndex(common_index)

    aligned = {a: s.reindex(common_index).ffill() for a, s in closes.items()}
    n = len(common_index)

    rebalance_positions = list(range(0, n, rebalance_freq))

    weights_rows = []
    weights_dates = []
    daily_weights = pd.DataFrame(0.0, index=common_index, columns=list(aligned.keys()))

    for i, pos in enumerate(rebalance_positions):
        scores = _rank_universe(aligned, pos, lookback)
        if len(scores) < 3:
            continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1])
        n_assets = len(ranked)
        third = max(1, n_assets // 3)
        shorts = [a for a, _ in ranked[:third]]
        longs = [a for a, _ in ranked[-third:]]

        w = pd.Series(0.0, index=aligned.keys())
        if longs:
            w[longs] = 1.0 / len(longs)
        if shorts:
            w[shorts] = -1.0 / len(shorts)

        # Apply starting the NEXT trading day after the rebalance decision
        # (rank computed using data through `pos`; weight held from pos+1
        # up to the next rebalance) -- same anti-lookahead shift-by-one.
        start = pos + 1
        end = rebalance_positions[i + 1] if i + 1 < len(rebalance_positions) else n
        if start >= n:
            continue
        end = min(end, n)
        daily_weights.iloc[start:end] = w.values
        weights_rows.append(w)
        weights_dates.append(common_index[pos])

    weights_history = pd.DataFrame(weights_rows, index=weights_dates) if weights_rows else pd.DataFrame()

    asset_returns = pd.DataFrame({a: s.pct_change().fillna(0.0) for a, s in aligned.items()})
    portfolio_gross_returns = (daily_weights.shift(0) * asset_returns).sum(axis=1)
    # NOTE: daily_weights was constructed to already only take effect at
    # pos+1 or later, so no additional shift is applied here -- doing so
    # would double-shift and misalign the intended holding period.

    turnover_series = daily_weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = (cost_bps / 10000.0) * turnover_series
    portfolio_returns = portfolio_gross_returns - cost

    equity = (1.0 + portfolio_returns).cumprod()
    trade_count = int((turnover_series > 0).sum())

    return CrossSectionalResult(
        lookback=lookback,
        weights_history=weights_history,
        portfolio_returns=portfolio_returns,
        sharpe=_sharpe(portfolio_returns.to_numpy()),
        max_drawdown=_max_drawdown(equity.to_numpy()),
        turnover=float(turnover_series.sum()),
        trade_count=trade_count,
    )


def walk_forward_cross_sectional(
    price_data: dict[str, pd.DataFrame],
    lookback: str = "6m",
    rebalance_freq: int = REBALANCE_FREQ,
    cost_bps: float = 1.0,
    n_windows: int = 5,
    in_sample_frac: float = 0.70,
) -> dict:
    """Same 5-window 70/30 walk-forward discipline as the single-asset
    engine, applied to the cross-sectional portfolio return series."""
    full_result = run_cross_sectional_momentum(price_data, lookback, rebalance_freq, cost_bps)
    returns = full_result.portfolio_returns
    n = len(returns)
    edges = np.linspace(0, n, n_windows + 1, dtype=int)

    oos_parts = []
    is_parts = []
    for i in range(n_windows):
        start, end = edges[i], edges[i + 1]
        if end - start < 10:
            continue
        split = start + int(round((end - start) * in_sample_frac))
        split = max(split, start + 1)
        is_parts.append(returns.iloc[start:split])
        oos_parts.append(returns.iloc[split:end])

    is_returns = pd.concat(is_parts) if is_parts else pd.Series(dtype=float)
    oos_returns = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    oos_equity = (1.0 + oos_returns).cumprod()

    return {
        "lookback": lookback,
        "full_sharpe": full_result.sharpe,
        "full_max_drawdown": full_result.max_drawdown,
        "in_sample_sharpe": _sharpe(is_returns.to_numpy()),
        "oos_sharpe": _sharpe(oos_returns.to_numpy()),
        "oos_max_drawdown": _max_drawdown(oos_equity.to_numpy()),
        "turnover": full_result.turnover,
        "trade_count": full_result.trade_count,
    }
