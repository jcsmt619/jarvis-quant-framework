from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "raw"
STRATEGIES_DIR = ROOT / "strategies"
LOGS_DIR = ROOT / "logs"
CONFIG_DIR = ROOT / "config"

for directory in (DATA_DIR, STRATEGIES_DIR, LOGS_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

TICKERS = ["SPY", "BTC-USD", "TLT"]
STRESS_DROP = 0.20
STRESS_NOISE = 0.03


def download_history(ticker: str) -> pd.DataFrame:
    data = yf.download(
        ticker,
        period="15y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if data.empty:
        raise RuntimeError(f"No data returned for {ticker}")

    frame = data.reset_index()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [col[1] if col[0] == "" else col[0] for col in frame.columns]

    if "Date" in frame.columns:
        frame = frame.rename(columns={"Date": "date"})
    elif frame.index.name:
        frame = frame.reset_index()
        frame = frame.rename(columns={"index": "date"})

    frame = frame.rename(columns={"Close": "Close", "close": "Close"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["ticker"] = ticker
    return frame


def build_stress_dataset(frame: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    stress_frame = frame.copy()
    if "Close" not in stress_frame.columns:
        raise KeyError("The source frame must contain a Close column")

    close_values = pd.to_numeric(stress_frame["Close"], errors="coerce").to_numpy(dtype=float)
    drop_index = max(20, int(len(close_values) * 0.70))

    rng = np.random.default_rng(seed)
    tail = close_values[drop_index:].astype(float)
    stress_tail = tail * (1 - STRESS_DROP)
    stress_tail = stress_tail * (1 + rng.normal(0, STRESS_NOISE, size=len(stress_tail)))

    stress_values = close_values.copy()
    stress_values[drop_index:] = stress_tail

    stress_frame["stress_close"] = stress_values
    stress_frame["stress_label"] = "stress"
    stress_frame["stress_scenario"] = "20pct_drop_and_volatility_spike"
    return stress_frame


def save_frame(frame: pd.DataFrame, stem: str) -> None:
    csv_path = DATA_DIR / f"{stem}.csv"
    parquet_path = DATA_DIR / f"{stem}.parquet"
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False)


def main() -> None:
    manifest: dict[str, object] = {"generated_at": datetime.now(UTC).isoformat(), "tickers": [], "rows": {}}

    for ticker in TICKERS:
        frame = download_history(ticker)
        stem = ticker.lower().replace("-", "_")
        save_frame(frame, stem)

        stress_frame = build_stress_dataset(frame, seed=42 + TICKERS.index(ticker))
        save_frame(stress_frame, f"{stem}_stress")

        manifest["tickers"].append(ticker)
        manifest["rows"][ticker] = {"raw_rows": int(len(frame)), "stress_rows": int(len(stress_frame))}

    (CONFIG_DIR / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (LOGS_DIR / "data_generator.log").write_text(
        f"Generated {len(TICKERS)} datasets at {datetime.now(UTC).isoformat()}\n",
        encoding="utf-8",
    )

    print("Data generation complete.")
    print(f"Saved files under {DATA_DIR}")
    for path in sorted(DATA_DIR.glob("*")):
        print(path.name)


if __name__ == "__main__":
    main()
