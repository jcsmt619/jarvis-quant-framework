"""
runner_vs_standard.py
=====================
Walk-forward A/B on SOXL: Standard exits vs Runner Mode (+1.5R bank 50%,
breakeven, 2x ATR trail). Identical HMM seed and window schedule so the ONLY
difference between arms is the exit logic. Kill-switch compliance (25% peak DD)
is reported for both.

Run:  python runner_vs_standard.py
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
OUT = ROOT / "logs" / "runner_vs_standard.json"


def _metrics(equity: np.ndarray, returns: np.ndarray, trades: list) -> dict:
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    sd = returns.std(ddof=1)
    years = len(equity) / TRADING_DAYS
    cagr = float((equity[-1] / equity[0]) ** (1 / years) - 1.0) if equity[-1] > 0 else -1.0
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "total_return": float(equity[-1] / equity[0] - 1.0),
        "cagr": cagr,
        "max_dd": float(dd.max()),
        "sharpe": float(returns.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
        "calmar": float(cagr / dd.max()) if dd.max() > 1e-9 else 0.0,
        "n_trades": len(trades),
        "win_rate": float(len(wins) / len(trades)) if trades else 0.0,
        "avg_win_pct": float(np.mean([t["return_pct"] for t in wins])) if wins else 0.0,
        "best_trade_pct": float(max((t["return_pct"] for t in trades), default=0.0)),
        "kill_switch_ok": bool(dd.max() <= KILL_DD),
    }


def run_arm(runner_mode: bool) -> dict:
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")
    from backtest.backtester import WalkForwardBacktester

    df = pd.read_parquet(ROOT / "data" / "raw" / "soxl.parquet")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    # satellite_cap disabled for this experiment PER EXPLICIT USER ORDER (cap
    # rejected); the 25% kill-switch gate below still judges the outcome.
    bt = WalkForwardBacktester(n_init=2, random_state=42, runner_mode=runner_mode,
                               satellite_cap=10.0)
    res = bt.run(df, symbol="SOXL")
    m = _metrics(res.equity, res.returns, res.trades)
    m["mode"] = "runner" if runner_mode else "standard"
    m["banked_events"] = sum(1 for h in res.regime_history if h.get("runner_banked"))
    return m


def main() -> None:
    print("SOXL walk-forward A/B: Standard vs Runner Mode (same seed/windows)\n")
    with ProcessPoolExecutor(max_workers=2) as ex:
        std_f = ex.submit(run_arm, False)
        run_f = ex.submit(run_arm, True)
        std, run = std_f.result(), run_f.result()

    def row(m: dict) -> str:
        return (f"  {m['mode']:<9} ret {m['total_return']:>+9.1%}  CAGR {m['cagr']:>+7.1%}  "
                f"maxDD {m['max_dd']:>6.1%}  sharpe {m['sharpe']:>5.2f}  calmar {m['calmar']:>5.2f}  "
                f"trades {m['n_trades']:>3}  win {m['win_rate']:>4.0%}  "
                f"avgWin {m['avg_win_pct']:>+6.1%}  best {m['best_trade_pct']:>+7.1%}  "
                f"kill25% {'PASS' if m['kill_switch_ok'] else 'FAIL'}")

    print(row(std))
    print(row(run))
    print(f"\n  runner banked-50% events: {run['banked_events']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"standard": std, "runner": run}, indent=2))
    print(f"\nResults -> {OUT}")


if __name__ == "__main__":
    main()
