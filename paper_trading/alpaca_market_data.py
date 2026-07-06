"""Read-only Alpaca market data loader.

Phase 6A safety layer.

This module fetches recent market bars from Alpaca using paper-only config.

It does not submit orders.
It does not cancel orders.
It does not enable live trading.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from paper_trading.alpaca_config import AlpacaPaperConfig, validate_alpaca_paper_config
from paper_trading.alpaca_health import create_alpaca_paper_client


@dataclass(frozen=True)
class AlpacaMarketDataResult:
    timestamp_utc: str
    symbol: str
    timeframe: str
    bars_count: int
    latest_timestamp_utc: str | None
    latest_close: float | None
    csv_path: str | None
    read_only: bool = True
    order_submission_enabled: bool = False
    live_trading_enabled: bool = False
    broker_order_call_performed: bool = False
    note: str = "READ ONLY: market data fetched; no order was submitted."

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _load_timeframe_day():
    try:
        from alpaca_trade_api.rest import TimeFrame

        return TimeFrame.Day
    except Exception:
        return "1Day"


def _extract_dataframe_from_bars(bars: object, symbol: str) -> pd.DataFrame:
    """Convert Alpaca bar response variants into a Date/Close dataframe."""
    if hasattr(bars, "df"):
        df = bars.df.copy()

        if isinstance(df.index, pd.MultiIndex):
            if "symbol" in df.index.names:
                try:
                    df = df.xs(symbol, level="symbol")
                except KeyError:
                    pass
            else:
                df = df.reset_index()

        if "timestamp" in df.columns:
            dates = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        else:
            dates = pd.to_datetime(df.index, utc=True, errors="coerce")

        close_col = "close" if "close" in df.columns else "Close"
        if close_col not in df.columns:
            raise ValueError("Alpaca bars dataframe does not contain a close column.")

        close = pd.to_numeric(df[close_col], errors="coerce")

        out = pd.DataFrame({"Date": dates, "Close": close})
        out = out.dropna().sort_values("Date").reset_index(drop=True)
        return out

    records = []

    for bar in bars:
        timestamp = (
            getattr(bar, "t", None)
            or getattr(bar, "timestamp", None)
            or getattr(bar, "time", None)
        )
        close = getattr(bar, "c", None)
        if close is None:
            close = getattr(bar, "close", None)

        records.append(
            {
                "Date": pd.to_datetime(timestamp, utc=True, errors="coerce"),
                "Close": pd.to_numeric(close, errors="coerce"),
            }
        )

    out = pd.DataFrame(records).dropna().sort_values("Date").reset_index(drop=True)
    return out


def fetch_alpaca_daily_bars(
    *,
    config: AlpacaPaperConfig,
    symbol: str = "EEM",
    limit: int = 120,
    adjustment: str = "all",
    feed: str | None = "iex",
    client_factory: Callable[..., object] | None = None,
) -> pd.DataFrame:
    """Fetch recent daily bars from Alpaca using a paper-only config.

    This function is read-only.
    """
    validate_alpaca_paper_config(config)

    if limit <= 0:
        raise ValueError("limit must be positive")

    client = create_alpaca_paper_client(config, client_factory=client_factory)
    timeframe = _load_timeframe_day()

    try:
        if feed is None:
            bars = client.get_bars(
                symbol,
                timeframe,
                limit=limit,
                adjustment=adjustment,
            )
        else:
            bars = client.get_bars(
                symbol,
                timeframe,
                limit=limit,
                adjustment=adjustment,
                feed=feed,
            )
    except TypeError:
        bars = client.get_bars(
            symbol,
            timeframe,
            limit=limit,
            adjustment=adjustment,
        )

    df = _extract_dataframe_from_bars(bars, symbol=symbol)

    if df.empty:
        raise ValueError(f"No market bars returned for {symbol}")

    return df.tail(limit).reset_index(drop=True)


def write_market_data_csv(
    *,
    bars: pd.DataFrame,
    symbol: str = "EEM",
    output_dir: Path | str = "reports/paper_trading",
) -> tuple[Path, AlpacaMarketDataResult]:
    """Write read-only market bars to CSV and return metadata."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    clean = bars.copy()
    clean["Date"] = pd.to_datetime(clean["Date"], utc=True, errors="coerce")
    clean["Close"] = pd.to_numeric(clean["Close"], errors="coerce")
    clean = clean.dropna().sort_values("Date").reset_index(drop=True)

    if clean.empty:
        raise ValueError("No valid bars to write.")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_path / f"{symbol.lower()}_alpaca_daily_bars_{stamp}.csv"
    json_path = output_path / f"{symbol.lower()}_alpaca_market_data_{stamp}.json"

    clean.to_csv(csv_path, index=False)

    latest_timestamp = clean["Date"].iloc[-1]
    latest_close = float(clean["Close"].iloc[-1])

    result = AlpacaMarketDataResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=symbol,
        timeframe="1Day",
        bars_count=len(clean),
        latest_timestamp_utc=latest_timestamp.isoformat(),
        latest_close=latest_close,
        csv_path=str(csv_path),
    )

    json_path.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return csv_path, result
