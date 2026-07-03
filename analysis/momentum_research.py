"""
analysis/momentum_research.py
=============================
Cross-sectional momentum probe -- the first hunt in a NEW signal family
after the z-reversion chain was closed at every horizon. Momentum is a
documented, persistent factor (Jegadeesh-Titman 1993); the question is
whether a naive top-N monthly rotation on a small universe carries it.

ONE pre-declared config (6-1 momentum, top 3, monthly, 10y). No grid --
n_trials = 1, and it stays 1 unless a search is declared as one.

Corrections vs the draft this was adapted from:
  * BENCHMARK BUG: `monthly_prices.iloc[-1].mean() / iloc[0].mean()`
    averages PRICES across tickers -- a $900 stock dominates a $40 one.
    The benchmark is now the equal-weight average of per-ticker RETURNS
    on the SAME universe (sharing its bias, so the comparison is fair).
  * SKIP-MONTH: 6-month momentum including the latest month mixes in
    short-term REVERSAL (the academic convention is 12-1 / 6-1). Default
    is now 6-1: price[t-1] / price[t-6] - 1.
  * SURVIVORSHIP DISCLOSED: the universe is hand-picked 2026 winners
    (NVDA, LLY, ...). Absolute numbers are inflated by construction; only
    the ACTIVE return vs the same-universe benchmark means anything.
  * FRICTION: turnover-based cost per rebalance (default 10bp per side)
    -- the draft rotated for free.
  * 2y (~18 decisions) -> 10y (~113 decisions); metrics now include
    Sharpe, max DD, and the PSR of the ACTIVE return stream (P(true
    active SR > 0)) instead of a bare total-return number.
  * Unused matplotlib import, emojis removed.

Run:  python analysis/momentum_research.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",   # tech
    "JPM", "BAC", "GS",                                         # banks
    "XOM", "CVX",                                               # energy
    "LLY", "JNJ", "PFE",                                        # pharma
    "KO", "PEP", "MCD", "WMT", "COST",                          # consumer
]
# Gate #1 universe: the 9 original sector SPDRs (1998-). Survivorship is
# STRUCTURALLY impossible -- sectors don't get delisted for losing.
ETF_UNIVERSE = ["XLK", "XLE", "XLF", "XLV", "XLI",
                "XLB", "XLY", "XLP", "XLU"]
LOOKBACK = 6          # months
SKIP = 1              # skip the latest month (short-term reversal)
TOP_N = 3
COST_BPS_PER_SIDE = 10.0
HISTORY_YEARS = 10


def momentum_backtest(monthly: pd.DataFrame, lookback: int = LOOKBACK,
                      skip: int = SKIP, top_n: int = TOP_N,
                      cost_bps: float = COST_BPS_PER_SIDE) -> dict:
    """Monthly top-N rotation on skip-month momentum, equal weight,
    turnover-costed. Benchmark = equal-weight of the SAME universe."""
    mom = monthly.shift(skip) / monthly.shift(lookback) - 1.0
    rets = monthly.pct_change()

    strat, bench, picks_log = [], [], []
    prev: set[str] = set()
    for i in range(lookback, len(monthly) - 1):
        scores = mom.iloc[i].dropna()
        if len(scores) < top_n:
            continue
        winners = list(scores.sort_values(ascending=False).head(top_n).index)
        nxt = rets.iloc[i + 1]
        gross = float(nxt[winners].mean())
        turnover = len(set(winners) - prev) / top_n     # fraction replaced
        cost = turnover * 2 * cost_bps / 1e4            # sell old + buy new
        strat.append(gross - cost)
        bench.append(float(nxt[monthly.columns].dropna().mean()))
        picks_log.append((monthly.index[i], winners, gross - cost))
        prev = set(winners)

    strat_a, bench_a = np.array(strat), np.array(bench)
    active = strat_a - bench_a

    def stats(r: np.ndarray) -> dict:
        eq = np.cumprod(1 + r)
        peak = np.maximum.accumulate(eq)
        years = len(r) / 12
        return {
            "total": float(eq[-1] - 1),
            "cagr": float(eq[-1] ** (1 / years) - 1) if years > 0 else 0.0,
            "sharpe": float(r.mean() / r.std() * np.sqrt(12))
                      if r.std() > 0 else 0.0,
            "max_dd": float(((peak - eq) / peak).max()),
        }

    from backtest.deflated_sharpe import probabilistic_sharpe, sharpe_stats
    s = sharpe_stats(active)
    psr_active = probabilistic_sharpe(s["sr"], s["T"], s["skew"], s["kurt"],
                                      sr_benchmark=0.0)

    return {"n_decisions": len(strat), "strategy": stats(strat_a),
            "benchmark": stats(bench_a),
            "active_annual": float(active.mean() * 12),
            "psr_active": float(psr_active),
            "picks": picks_log}


# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    import yfinance as yf
    p = argparse.ArgumentParser()
    p.add_argument("--universe", choices=("stocks", "etf"), default="stocks",
                   help="etf = gate #1: survivorship-clean sector SPDRs, "
                        "IDENTICAL pre-declared config")
    args = p.parse_args()
    universe = ETF_UNIVERSE if args.universe == "etf" else UNIVERSE

    print(f"fetching {HISTORY_YEARS}y of daily data for "
          f"{len(universe)} names...")
    data = yf.download(universe, period=f"{HISTORY_YEARS}y", interval="1d",
                       auto_adjust=True, progress=False)["Close"]
    monthly = data.resample("ME").last().dropna(axis=1)

    res = momentum_backtest(monthly)

    print(f"\nMOMENTUM PROBE -- 6-1 momentum, top {TOP_N} of "
          f"{monthly.shape[1]}, monthly, {COST_BPS_PER_SIDE:.0f}bp/side")
    if args.universe == "etf":
        print("  GATE #1: survivorship-clean universe (9 original sector "
              "SPDRs -- sectors\n  cannot be hand-picked winners). Config and "
              "code IDENTICAL to the probe:\n  this is a pre-registered "
              "confirmation, not a new trial.")
        print(f"  {res['n_decisions']} monthly decisions.")
    else:
        print("  DISCLOSURES: universe = hand-picked 2026 survivors, so ABSOLUTE")
        print("  numbers are inflated by construction -- only the ACTIVE return vs")
        print("  the same-universe benchmark is meaningful. One pre-declared")
        print(f"  config, n_trials=1. {res['n_decisions']} monthly decisions.")

    st, bm = res["strategy"], res["benchmark"]
    print(f"\n  {'':<12}{'total':>10}{'CAGR':>8}{'sharpe':>8}{'maxDD':>8}")
    print(f"  {'strategy':<12}{st['total']:>+10.1%}{st['cagr']:>8.1%}"
          f"{st['sharpe']:>8.2f}{st['max_dd']:>8.1%}")
    print(f"  {'benchmark':<12}{bm['total']:>+10.1%}{bm['cagr']:>8.1%}"
          f"{bm['sharpe']:>8.2f}{bm['max_dd']:>8.1%}")
    print(f"\n  ACTIVE return: {res['active_annual']:+.1%}/yr | "
          f"PSR(active > 0): {res['psr_active']:.1%}")

    recent = res["picks"][-3:]
    print("\n  recent picks:")
    for dt, winners, r in recent:
        print(f"    {dt:%Y-%m}  {', '.join(winners):<22} {r:+.2%}")

    if res["psr_active"] >= 0.95:
        print("\n  VERDICT: active edge is statistically credible on THIS "
              "biased universe.\n  Next gates: survivorship-clean universe, "
              "CPCV path distribution, DSR if any\n  variant search begins.")
    elif res["psr_active"] >= 0.60:
        print("\n  VERDICT: suggestive but unproven -- the active stream "
              "does not clear the\n  95% bar. Extend the universe/history "
              "before spending more effort.")
    else:
        print("\n  VERDICT: no credible active edge over equal-weighting "
              "the same names.\n  Naive top-N rotation adds turnover, "
              "concentration risk, and drawdown --\n  not alpha. The factor "
              "may live elsewhere (12-1, larger universe, vol-scaled).")


if __name__ == "__main__":
    main()
