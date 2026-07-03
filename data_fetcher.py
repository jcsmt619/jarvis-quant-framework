from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "raw"
ENV_PATH = ROOT / ".env"

load_dotenv(ENV_PATH)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://alpaca.markets").strip()
# Market-data host (separate from the trading host). Overridable via .env.
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets").strip()
ALPACA_FEED = os.getenv("ALPACA_FEED", "iex").strip()  # 'iex' (free) or 'sip'

# Symbol mappings: Alpaca uses different format for crypto (no slash).
# SOXL/TQQQ are 3x LETFs (inception 2010) -> daily history back to inception.
SYMBOLS_ALPACA = ["SPY", "BTCUSD", "TLT", "SOXL", "TQQQ"]
SYMBOLS_YFINANCE = ["SPY", "BTC-USD", "TLT", "SOXL", "TQQQ"]
SYMBOL_MAPPING = {
    "SPY": ("SPY", "spy"),
    "BTCUSD": ("BTC-USD", "btc_usd"),
    "TLT": ("TLT", "tlt"),
    "SOXL": ("SOXL", "soxl"),
    "TQQQ": ("TQQQ", "tqqq"),
}

TIMEFRAME = "1Day"
# Absolute-maximum history: reach back well before any symbol's inception so the
# provider returns everything it has. yfinance fallback uses period='max'.
START_DATE = "2004-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")


def fetch_alpaca_data(symbol: str) -> pd.DataFrame | None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print(f"  Warning: Alpaca credentials not set. Skipping {symbol}.")
        return None

    url = f"{ALPACA_DATA_URL}/v2/stocks/{symbol}/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }

    all_bars: list[dict] = []
    page_token: str | None = None
    try:
        for _ in range(1000):  # safety cap; paginate to the absolute max history
            params = {
                "timeframe": TIMEFRAME,
                "start": START_DATE,
                "end": END_DATE,
                "limit": 10000,
                "feed": ALPACA_FEED,
                "adjustment": "all",
            }
            if page_token:
                params["page_token"] = page_token
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"  Alpaca API error for {symbol}: Status {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return None
            data = response.json()
            bars = data.get("bars") or []
            all_bars.extend(bars)
            page_token = data.get("next_page_token")
            if not page_token:
                break

        if not all_bars:
            print(f"  No bars returned for {symbol} from Alpaca")
            return None

        df = pd.DataFrame(all_bars).rename(columns={
            "t": "date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = (df[["date", "Open", "High", "Low", "Close", "Volume"]]
              .sort_values("date").drop_duplicates("date").reset_index(drop=True))
        return df
    except requests.exceptions.RequestException as e:
        print(f"  HTTP error for {symbol}: {e}")
        return None
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return None


def fallback_yfinance(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(
        symbol,
        period="max",          # absolute maximum available history (to inception)
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if data.empty:
        raise RuntimeError(f"No data returned for {symbol}")

    frame = data.reset_index()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [col[1] if col[0] == "" else col[0] for col in frame.columns]
    if "Date" in frame.columns:
        frame = frame.rename(columns={"Date": "date"})
    frame = frame.rename(columns={"Close": "Close", "close": "Close"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    frame = frame.sort_values("date").reset_index(drop=True)
    return frame[["date", "Open", "High", "Low", "Close", "Volume"]]


def main() -> None:
    print("================================================================================")
    print("FETCHING MAXIMUM-HISTORY DATA (deepest of Alpaca / yfinance per symbol)")
    print("================================================================================\n")

    if ALPACA_API_KEY and ALPACA_SECRET_KEY:
        print("\u2713 Alpaca credentials loaded from .env")
        print(f"\u2713 Alpaca data host: {ALPACA_DATA_URL} (feed={ALPACA_FEED})\n")
    else:
        print("! Alpaca credentials not set \u2014 using yfinance for maximum history\n")

    for alpaca_symbol in SYMBOLS_ALPACA:
        yfinance_symbol, stem = SYMBOL_MAPPING[alpaca_symbol]
        print(f"Processing {alpaca_symbol}...")

        df_alpaca = fetch_alpaca_data(alpaca_symbol)
        df_yf = None
        try:
            df_yf = fallback_yfinance(yfinance_symbol)
        except Exception as e:
            print(f"  yfinance error: {e}")

        # Keep the source with the DEEPEST history (most bars) so we get the
        # absolute maximum length. Alpaca's free IEX feed is shallow (~6y); the
        # yfinance 'max' history reaches each symbol's inception.
        options = [
            (len(d), name, d) for name, d in (("Alpaca", df_alpaca), ("yfinance", df_yf))
            if d is not None and not d.empty
        ]
        if not options:
            print(f"  ERROR: no data available for {alpaca_symbol}\n")
            continue
        options.sort(key=lambda x: x[0])
        n_bars, source, df = options[-1]
        start = pd.to_datetime(df["date"]).min().date()
        end = pd.to_datetime(df["date"]).max().date()
        summary = ", ".join(f"{nm}:{ln}" for ln, nm, _ in options)
        print(f"  \u2713 {source}: {n_bars} bars ({start} \u2192 {end})  [deepest of {summary}]")

        df.to_csv(DATA_DIR / f"{stem}.csv", index=False)
        df.to_parquet(DATA_DIR / f"{stem}.parquet", index=False)
        print(f"  \u2713 Saved: {stem}\n")


if __name__ == "__main__":
    main()
