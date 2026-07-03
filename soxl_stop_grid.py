"""
soxl_stop_grid.py
=================
SOXL volatility-stop-multiplier grid search, governed by the course risk rules
ingested from skool_dump.txt:

  * Kill switch     -- a hard drawdown threshold halts everything (our RiskLimits
                       peak_dd_lock = 25%). Any multiplier whose walk-forward max
                       drawdown breaches it FAILS, regardless of return.
  * Survival first  -- "avoiding big losses beats chasing big wins"; recovery
                       math (-50% needs +100%) is reported per multiplier.
  * Robustness      -- per the dump's validation module: "A real edge is
                       surrounded by other parameter settings that also work.
                       A fluke is a lonely peak." We report plateau vs peak.

Experimental design: every multiplier uses the SAME random_state and window
schedule, so the HMM regime path is identical across runs -- performance
differences are attributable purely to the stop multiplier.

Run:
    python soxl_stop_grid.py [--fast]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TRADING_DAYS = 252
KILL_SWITCH_DD = 0.25          # course rule: hard drawdown threshold halts everything
PLATEAU_TOLERANCE = 0.30       # neighbors within 30% of winner's Calmar = plateau
MULTIPLIERS = [round(1.5 + 0.25 * i, 2) for i in range(11)]   # 1.50 .. 4.00
OUT_JSON = ROOT / "logs" / "soxl_stop_grid.json"


def _metrics(equity: np.ndarray, returns: np.ndarray) -> dict:
    total = float(equity[-1] / equity[0] - 1.0)
    years = len(equity) / TRADING_DAYS
    cagr = float((equity[-1] / equity[0]) ** (1 / years) - 1.0) if years > 0 and equity[-1] > 0 else -1.0
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    max_dd = float(dd.max())
    sd = returns.std(ddof=1)
    sharpe = float(returns.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0
    calmar = float(cagr / max_dd) if max_dd > 1e-9 else 0.0
    return {"total_return": total, "cagr": cagr, "max_dd": max_dd,
            "sharpe": sharpe, "calmar": calmar}


def run_one(mult: float, fast: bool) -> dict:
    """Walk-forward SOXL run at a single stop multiplier (worker process)."""
    import warnings as _w
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    _w.filterwarnings("ignore", message="Model is not converging")

    from backtest.backtester import WalkForwardBacktester

    df = pd.read_parquet(ROOT / "data" / "raw" / "soxl.parquet")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    bt = WalkForwardBacktester(
        n_init=2 if fast else 4,
        random_state=42,                    # identical HMM path for every multiplier
        letf_stop_multiplier=mult,
    )
    result = bt.run(df, symbol="SOXL")
    m = _metrics(result.equity, result.returns)
    m["multiplier"] = mult
    m["kill_switch_breached"] = m["max_dd"] > KILL_SWITCH_DD
    # course recovery math: gain required to recover the max drawdown
    m["recovery_required"] = float(m["max_dd"] / (1.0 - m["max_dd"])) if m["max_dd"] < 1 else float("inf")
    m["n_windows"] = result.n_windows
    return m


def plateau_analysis(rows: list[dict]) -> dict:
    """Winner + neighbor check per the dump's 'plateau vs lonely peak' rule."""
    passing = [r for r in rows if not r["kill_switch_breached"]]
    pool = passing if passing else rows
    winner = max(pool, key=lambda r: r["calmar"])
    idx = [r["multiplier"] for r in rows].index(winner["multiplier"])
    neighbors = [rows[i] for i in (idx - 1, idx + 1) if 0 <= i < len(rows)]
    if winner["calmar"] <= 0:
        shape = "no positive edge at any setting"
    else:
        near = [n for n in neighbors
                if n["calmar"] >= winner["calmar"] * (1.0 - PLATEAU_TOLERANCE)]
        shape = "plateau (neighbors hold up)" if len(near) == len(neighbors) else "LONELY PEAK (distrust)"
    return {"winner": winner, "passing_count": len(passing), "shape": shape}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="n_init=2 for a quicker pass")
    args = ap.parse_args()

    print(f"SOXL stop-multiplier grid: {MULTIPLIERS}")
    print(f"Gate (course kill-switch rule): max drawdown must stay under {KILL_SWITCH_DD:.0%}\n")

    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_one, m, args.fast): m for m in MULTIPLIERS}
        for fut in as_completed(futs):
            r = fut.result()
            rows.append(r)
            flag = "FAIL kill-switch" if r["kill_switch_breached"] else "pass"
            print(f"  mult {r['multiplier']:>4}:  ret {r['total_return']:>+9.1%}  "
                  f"CAGR {r['cagr']:>+7.1%}  maxDD {r['max_dd']:>6.1%}  "
                  f"sharpe {r['sharpe']:>5.2f}  calmar {r['calmar']:>5.2f}  [{flag}]")

    rows.sort(key=lambda r: r["multiplier"])
    verdict = plateau_analysis(rows)

    print("\n" + "=" * 78)
    print("GRID VERDICT (course rules applied)")
    print("=" * 78)
    w = verdict["winner"]
    print(f"  Multipliers passing the {KILL_SWITCH_DD:.0%} kill switch: "
          f"{verdict['passing_count']} / {len(rows)}")
    print(f"  Best by Calmar: mult {w['multiplier']}  "
          f"(ret {w['total_return']:+.1%}, maxDD {w['max_dd']:.1%}, calmar {w['calmar']:.2f})")
    print(f"  Recovery required from its max DD: {w['recovery_required']:+.1%}")
    print(f"  Robustness shape: {verdict['shape']}")
    if verdict["passing_count"] == 0:
        print("\n  CRO RULING: NO multiplier respects the kill switch. The course's own")
        print("  risk rules (survival first, hard DD halt) mean this parameter cannot be")
        print("  'optimized' into compliance on a 3x LETF. Do not deploy any of these.")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kill_switch_dd": KILL_SWITCH_DD,
        "grid": rows,
        "verdict": {"winner_multiplier": w["multiplier"], "shape": verdict["shape"],
                    "passing_count": verdict["passing_count"]},
    }, indent=2))
    print(f"\nResults -> {OUT_JSON}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore", message="Model is not converging")
    main()
