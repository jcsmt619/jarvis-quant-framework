"""
Intraday High-Velocity Data Fetcher
===================================
Downloads intraday bars for high-beta assets (crypto + 3x leveraged tech ETFs)
to capture massive intraday swings for the HyperAlpha engine.

IMPORTANT DATA-AVAILABILITY CONSTRAINT (free yfinance feed):
    - 1h interval  -> max ~730 calendar days of history
    - 15m interval -> max ~60 calendar days of history
    - 30m interval -> max ~60 calendar days of history
So "15 years of intraday" is NOT physically available from this feed. This script
pulls the maximum real window per interval and records the true depth in a
manifest so downstream results are not mistaken for 15-year intraday history.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "intraday"
CONFIG_DIR = ROOT / "config"

# High-velocity, high-beta universe.
# yfinance tickers: crypto pairs + 3x leveraged tech ETFs.
UNIVERSE = {
    "BTC-USD": "btc_usd",
    "ETH-USD": "eth_usd",
    "SOXL": "soxl",
    "TQQQ": "tqqq",
}

# Interval -> max period yfinance permits for that interval.
INTERVAL_MAX_PERIOD = {
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "1h": "730d",
}


def fetch_intraday(symbol: str, interval: str) -> pd.DataFrame:
    import yfinance as yf

    period = INTERVAL_MAX_PERIOD.get(interval, "60d")
    data = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if data.empty:
        raise RuntimeError(f"No intraday data returned for {symbol} @ {interval}")

    frame = data.reset_index()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [col[1] if col[0] == "" else col[0] for col in frame.columns]

    # Normalize the datetime column name
    dt_col = None
    for candidate in ("Datetime", "Date", "index", "Timestamp"):
        if candidate in frame.columns:
            dt_col = candidate
            break
    if dt_col is None:
        dt_col = frame.columns[0]
    frame = frame.rename(columns={dt_col: "date"})

    frame["date"] = pd.to_datetime(frame["date"])
    # Strip timezone for backtrader compatibility
    if hasattr(frame["date"].dtype, "tz") and frame["date"].dt.tz is not None:
        frame["date"] = frame["date"].dt.tz_localize(None)

    frame = frame.sort_values("date").reset_index(drop=True)
    return frame[["date", "Open", "High", "Low", "Close", "Volume"]]


def main(interval: str = "60m") -> None:
    print("=" * 80)
    print(f"FETCHING INTRADAY HIGH-VELOCITY DATA  (interval={interval})")
    print("=" * 80)
    print(f"NOTE: yfinance caps {interval} history to "
          f"{INTERVAL_MAX_PERIOD.get(interval, '60d')} — this is the real window.\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated": datetime.now().isoformat(),
        "interval": interval,
        "max_period": INTERVAL_MAX_PERIOD.get(interval, "60d"),
        "assets": {},
    }

    for symbol, stem in UNIVERSE.items():
        print(f"Processing {symbol} @ {interval}...")
        try:
            df = fetch_intraday(symbol, interval)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        csv_path = DATA_DIR / f"{stem}_{interval}.csv"
        parquet_path = DATA_DIR / f"{stem}_{interval}.parquet"
        df.to_csv(csv_path, index=False)
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            pass

        span_days = (df["date"].max() - df["date"].min()).days
        manifest["assets"][symbol] = {
            "stem": stem,
            "bars": int(len(df)),
            "start": str(df["date"].min()),
            "end": str(df["date"].max()),
            "span_days": span_days,
            "csv": str(csv_path),
        }
        print(f"  OK: {len(df)} bars | {df['date'].min()} -> {df['date'].max()} "
              f"({span_days} days)\n")

    manifest_path = CONFIG_DIR / f"intraday_manifest_{interval}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest saved to {manifest_path}")


if __name__ == "__main__":
    import sys
    iv = sys.argv[1] if len(sys.argv) > 1 else "60m"
    main(iv)
