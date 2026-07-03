"""Intraday data sources.

Three ways to get bars into the system:

1. CSV. Point it at an exported intraday file with the usual OHLCV columns.
2. yfinance. Convenient for members who want to pull something like NQ=F to
   experiment, with the caveat that Yahoo only serves a couple of months of
   intraday history and the data is delayed. It is fine for a first look, not
   for production. The import is lazy so the package runs without it.
3. Synthetic. A regime-switching generator used by the test suite and by demo
   mode so the whole pipeline runs with no network and no broker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_OHLCV = ["open", "high", "low", "close", "volume"]


def load_csv(path: str | Path, tz: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    ts_col = cols.get("timestamp") or cols.get("date") or cols.get("datetime") or df.columns[0]
    df = df.rename(columns={ts_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df.columns = [c.lower() for c in df.columns]
    missing = set(_OHLCV) - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    if tz:
        df.index = df.index.tz_localize(tz) if df.index.tz is None else df.index.tz_convert(tz)
    return df[_OHLCV]


def load_yfinance(symbol: str = "NQ=F", interval: str = "5m",
                  period: str = "60d") -> pd.DataFrame:
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError(
            "yfinance is not installed. Run `pip install yfinance`. Note that "
            "Yahoo only serves ~60 days of intraday history and the feed is "
            "delayed, so use it for experiments only.") from exc
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    df = df.rename(columns={"adj close": "adj_close"})
    return df[_OHLCV]


def generate_synthetic_bars(
    n: int = 3000,
    start: str = "2024-01-02 00:00",
    freq: str = "5min",
    base_price: float = 18000.0,
    seed: int = 7,
    n_regimes: int = 3,
) -> pd.DataFrame:
    """Regime-switching OHLCV for tests and demo mode.

    The series alternates between calm, normal, and violent volatility states so
    the HMM has something real to cluster, and so strategies and risk rules get
    exercised across conditions.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq=freq)

    sigmas = np.linspace(0.0006, 0.0040, n_regimes)
    drifts = np.linspace(-0.00005, 0.00010, n_regimes)
    switch_p = 0.015

    state = 0
    rets = np.empty(n)
    states = np.empty(n, dtype=int)
    for i in range(n):
        if rng.random() < switch_p:
            state = int(rng.integers(0, n_regimes))
        states[i] = state
        rets[i] = rng.normal(drifts[state], sigmas[state])

    close = base_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[base_price], close[:-1]])
    intrabar = np.abs(rng.normal(0, sigmas[states])) * close
    high = np.maximum(open_, close) + intrabar
    low = np.minimum(open_, close) - intrabar
    volume = rng.integers(200, 1500, n) + states * 600

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx)
    # Snap to a quarter-point grid like NQ so tick math behaves.
    for c in ["open", "high", "low", "close"]:
        df[c] = (df[c] / 0.25).round() * 0.25
    return df


def load_bars(source: dict) -> pd.DataFrame:
    """Dispatch on a config block: {kind: csv|yfinance|synthetic, ...}."""
    kind = str(source.get("kind", "synthetic")).lower()
    if kind == "csv":
        return load_csv(source["path"], tz=source.get("tz"))
    if kind == "yfinance":
        return load_yfinance(source.get("symbol", "NQ=F"),
                             source.get("interval", "5m"),
                             source.get("period", "60d"))
    return generate_synthetic_bars(
        n=int(source.get("n", 3000)),
        base_price=float(source.get("base_price", 18000.0)),
        seed=int(source.get("seed", 7)),
        n_regimes=int(source.get("n_regimes", 3)),
    )
