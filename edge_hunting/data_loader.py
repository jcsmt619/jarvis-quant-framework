"""
edge_hunting/data_loader.py
===========================
Daily OHLCV loader for the strategy sweep engine. yfinance only, auto_adjust=True.
Read-only research data path -- no broker, no execution, no live trading.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_UNIVERSE = [
    # Broad ETFs
    "SPY", "QQQ", "IWM", "DIA",
    # Sector ETFs
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLU", "XLY", "XLP",
    # Commodities / rates / international
    "GLD", "USO", "TLT", "HYG", "EFA", "EEM", "EWZ",
    # Crypto
    "BTC-USD", "ETH-USD",
    # Large caps
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "JPM",
]

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
MIN_VALID_BARS = 500

CRYPTO_SUFFIX = "-USD"


def is_crypto(symbol: str) -> bool:
    return symbol.upper().endswith(CRYPTO_SUFFIX)


def _validate_columns(df: pd.DataFrame) -> bool:
    return all(col in df.columns for col in REQUIRED_COLUMNS)


def fetch_symbol(
    symbol: str,
    start: str = "2010-01-01",
    end: str = "2025-01-01",
    cache_dir: Path | None = None,
) -> pd.DataFrame | None:
    """Fetch one symbol's daily OHLCV via yfinance. Returns None if unusable."""
    import yfinance as yf

    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{symbol.replace('/', '_')}_{start}_{end}.parquet"
        if cache_path.exists():
            try:
                df = pd.read_parquet(cache_path)
                if _validate_columns(df) and len(df) >= MIN_VALID_BARS:
                    return df
            except Exception:
                pass

    try:
        df = yf.download(
            symbol, start=start, end=end, auto_adjust=True, progress=False,
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    # yfinance sometimes returns MultiIndex columns for single-symbol downloads
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[[c for c in REQUIRED_COLUMNS if c in df.columns]].dropna()

    if not _validate_columns(df) or len(df) < MIN_VALID_BARS:
        return None

    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    if cache_path is not None:
        try:
            df.to_parquet(cache_path)
        except Exception:
            pass

    return df


def load_universe(
    symbols: list[str] | None = None,
    start: str = "2010-01-01",
    end: str = "2025-01-01",
    cache_dir: str | Path | None = "data/raw/edge_hunting_cache",
) -> dict[str, pd.DataFrame]:
    """Load and filter the sweep universe. Skips symbols with < MIN_VALID_BARS bars."""
    symbols = symbols or DEFAULT_UNIVERSE
    cache_path = Path(cache_dir) if cache_dir else None

    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = fetch_symbol(sym, start=start, end=end, cache_dir=cache_path)
        if df is not None:
            out[sym] = df
    return out
