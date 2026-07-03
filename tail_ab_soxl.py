"""
tail_ab_soxl.py
===============
The Ultimate Test: SOXL standard walk-forward WITH vs WITHOUT the proactive
TailRiskMonitor (VIX>25 -> 80% gross, >35 -> 50%, >50 -> cash). Same seed and
windows, so the ONLY difference is the tail overlay. The 25% kill switch judges
both arms; 2020/2022 sub-periods are reported to test the hypothesis directly.

Run:  python tail_ab_soxl.py
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TRADING_DAYS = 252
KILL_DD = 0.25
OUT = ROOT / "logs" / "tail_ab_soxl.json"

CRISIS_WINDOWS = {
    "2020_covid": ("2020-02-01", "2020-04-30"),
    "2022_rate_hikes": ("2022-01-01", "2022-10-31"),
}


def _metrics(equity: np.ndarray) -> dict:
    rets = np.concatenate([[0.0], np.diff(equity) / equity[:-1]])
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    sd = rets.std(ddof=1)
    years = len(equity) / TRADING_DAYS
    cagr = float((equity[-1] / equity[0]) ** (1 / years) - 1.0) if equity[-1] > 0 else -1.0
    return {"total_return": float(equity[-1] / equity[0] - 1.0), "cagr": cagr,
            "max_dd": float(dd.max()),
            "sharpe": float(rets.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
            "calmar": float(cagr / dd.max()) if dd.max() > 1e-9 else 0.0,
            "kill_switch_ok": bool(dd.max() <= KILL_DD)}


def _window_dd(index: pd.DatetimeIndex, equity: np.ndarray, start: str, end: str) -> float | None:
    mask = (index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))
    if mask.sum() < 5:
        return None
    eq = equity[mask]
    peak = np.maximum.accumulate(eq)
    return float(((peak - eq) / peak).max())


def run_arm(with_tail: bool) -> dict:
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    logging.getLogger("tail_monitor").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")

    from backtest.backtester import WalkForwardBacktester
    from risk.tail_monitor import TailRiskMonitor

    df = pd.read_parquet(ROOT / "data" / "raw" / "soxl.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    vix = pd.read_parquet(ROOT / "data" / "raw" / "vix.parquet")
    vix["date"] = pd.to_datetime(vix["date"])
    vix = vix.set_index("date").sort_index()["close"]

    monitor = TailRiskMonitor() if with_tail else None
    bt = WalkForwardBacktester(
        n_init=2, random_state=42, satellite_cap=10.0,   # cap disabled per standing user order
        tail_monitor=monitor, tail_vix=vix if with_tail else None,
    )
    res = bt.run(df, symbol="SOXL")

    m = _metrics(res.equity)
    m["mode"] = "tail_monitor" if with_tail else "standard"
    for name, (s, e) in CRISIS_WINDOWS.items():
        m[f"dd_{name}"] = _window_dd(res.index, res.equity, s, e)
    if with_tail:
        caps = [h.get("tail_cap") for h in res.regime_history if h.get("tail_cap") is not None]
        m["bars_capped"] = int(sum(1 for c in caps if np.isfinite(c)))
        m["bars_cash"] = int(sum(1 for c in caps if c == 0.0))
        m["level_events"] = len(monitor.events)
    return m


def main() -> None:
    print("THE ULTIMATE TEST: SOXL standard walk-forward, tail monitor OFF vs ON")
    print("(same seed/windows; VIX>25->80% gross, >35->50%, >50->cash)\n")
    with ProcessPoolExecutor(max_workers=2) as ex:
        f_std, f_tail = ex.submit(run_arm, False), ex.submit(run_arm, True)
        std, tail = f_std.result(), f_tail.result()

    def row(m: dict) -> str:
        extra = (f"  capped bars {m.get('bars_capped', 0):>4}  cash bars {m.get('bars_cash', 0):>3}"
                 if m["mode"] == "tail_monitor" else "")
        return (f"  {m['mode']:<13} ret {m['total_return']:>+9.1%}  CAGR {m['cagr']:>+7.1%}  "
                f"maxDD {m['max_dd']:>6.1%}  sharpe {m['sharpe']:>5.2f}  calmar {m['calmar']:>5.2f}  "
                f"DD'20 {m['dd_2020_covid'] if m['dd_2020_covid'] is not None else float('nan'):>6.1%}  "
                f"DD'22 {m['dd_2022_rate_hikes'] if m['dd_2022_rate_hikes'] is not None else float('nan'):>6.1%}  "
                f"kill25% {'PASS' if m['kill_switch_ok'] else 'FAIL'}{extra}")

    print(row(std))
    print(row(tail))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"standard": std, "tail_monitor": tail}, indent=2))
    print(f"\nResults -> {OUT}")


if __name__ == "__main__":
    main()
