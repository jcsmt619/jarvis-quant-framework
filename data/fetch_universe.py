"""
data/fetch_universe.py
======================
Downloads the Meridian-Lite equity universe from Yahoo Finance: ~100 liquid
large-cap US names across all 11 GICS sectors + SPY benchmark. Daily adjusted
closes since 2014, saved to data/universe/prices.parquet (+ sectors.json).

HONEST CAVEAT (stated up front): this is a CURRENT-DAY large-cap list, so the
long book carries survivorship bias -- absolute long-side returns are inflated.
The property under test in Phase 2 (does beta-neutral construction hold its
equity through 2022?) is a HEDGING property and far less sensitive to that
bias, but do not quote this backtest's absolute alpha as deployable.

Run:  python data/fetch_universe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "universe"
START = "2014-01-01"

# ticker -> GICS sector (all listed pre-2014 to guarantee history)
UNIVERSE: dict[str, str] = {
    # Information Technology
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AVGO": "Tech", "ORCL": "Tech",
    "CRM": "Tech", "ADBE": "Tech", "AMD": "Tech", "INTC": "Tech", "CSCO": "Tech",
    "TXN": "Tech", "QCOM": "Tech", "MU": "Tech", "AMAT": "Tech",
    # Communication Services
    "GOOGL": "Comm", "META": "Comm", "NFLX": "Comm", "DIS": "Comm", "CMCSA": "Comm",
    "T": "Comm", "VZ": "Comm", "EA": "Comm",
    # Consumer Discretionary
    "AMZN": "ConsDisc", "TSLA": "ConsDisc", "HD": "ConsDisc", "MCD": "ConsDisc",
    "NKE": "ConsDisc", "SBUX": "ConsDisc", "LOW": "ConsDisc", "TJX": "ConsDisc",
    "GM": "ConsDisc", "F": "ConsDisc",
    # Consumer Staples
    "PG": "Staples", "KO": "Staples", "PEP": "Staples", "COST": "Staples",
    "WMT": "Staples", "MDLZ": "Staples", "CL": "Staples", "KMB": "Staples",
    # Health Care
    "UNH": "Health", "JNJ": "Health", "PFE": "Health", "MRK": "Health",
    "ABBV": "Health", "LLY": "Health", "TMO": "Health", "ABT": "Health",
    "BMY": "Health", "AMGN": "Health", "GILD": "Health", "MDT": "Health",
    # Financials
    "JPM": "Fin", "BAC": "Fin", "WFC": "Fin", "GS": "Fin", "MS": "Fin",
    "C": "Fin", "BLK": "Fin", "SCHW": "Fin", "AXP": "Fin", "USB": "Fin",
    # Industrials
    "CAT": "Indus", "DE": "Indus", "UNP": "Indus", "HON": "Indus", "BA": "Indus",
    "GE": "Indus", "MMM": "Indus", "LMT": "Indus", "UPS": "Indus", "FDX": "Indus",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "EOG": "Energy", "PSX": "Energy", "VLO": "Energy", "OXY": "Energy",
    # Materials
    "LIN": "Materials", "FCX": "Materials", "NEM": "Materials", "NUE": "Materials",
    "DOW": "Materials", "APD": "Materials",
    # Utilities
    "NEE": "Util", "DUK": "Util", "SO": "Util", "D": "Util", "AEP": "Util", "EXC": "Util",
    # Real Estate
    "AMT": "REIT", "PLD": "REIT", "SPG": "REIT", "O": "REIT", "PSA": "REIT", "EQIX": "REIT",
}
BENCHMARKS = ["SPY"]


def main() -> None:
    tickers = sorted(UNIVERSE) + BENCHMARKS
    print(f"Fetching {len(tickers)} tickers since {START} (batched)...")
    raw = yf.download(tickers, start=START, auto_adjust=True, progress=False,
                      group_by="column", threads=True)
    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    close = close.dropna(axis=1, how="all")

    missing = [t for t in tickers if t not in close.columns]
    if missing:
        print(f"  WARNING dropped (no data): {missing}")

    # Require near-complete history so factor lookbacks are honest.
    coverage = close.notna().mean()
    keep = coverage[coverage > 0.95].index.tolist()
    dropped = sorted(set(close.columns) - set(keep))
    if dropped:
        print(f"  WARNING dropped (<95% coverage): {dropped}")
    close = close[keep].ffill(limit=5)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    close.to_parquet(OUT_DIR / "prices.parquet")
    sectors = {t: s for t, s in UNIVERSE.items() if t in close.columns}
    (OUT_DIR / "sectors.json").write_text(json.dumps(sectors, indent=2))

    print(f"Saved {close.shape[1]} tickers x {close.shape[0]} bars "
          f"({close.index.min():%Y-%m-%d} -> {close.index.max():%Y-%m-%d})")
    print(f"-> {OUT_DIR / 'prices.parquet'}")


if __name__ == "__main__":
    main()
