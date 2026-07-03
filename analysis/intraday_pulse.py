"""
analysis/intraday_pulse.py
==========================
The intraday pulse check: does dual-class z-score reversion have a pulse
at 1-minute bars, where the structural-arb postmortem said the edge (if
any) must live?

The decisive quantity is NOT the 5-day return sign (noise). It is:

    gross edge per round trip (bps)   vs   friction per round trip (bps)

reported across a HALF-SPREAD SENSITIVITY LADDER, because free 1-minute
data cannot observe the true bid-ask spread -- pretending one number is
right would be manufacturing a verdict.

Corrections vs the draft this was adapted from:
  * FANTASY FRICTION: $1/leg commission and ZERO spread cost. At 1-min
    horizons on GOOG/GOOGL a 2-sigma spread excursion is a few bps and a
    round trip crosses the spread FOUR times -- the spread IS the cost.
    Friction = 4 x (half-spread on the leg notional) + 4 x commission
    (min ticket), evaluated at 1 / 2 / 5 bp half-spreads.
  * SAME-BAR FILLS: signal at close[i] was filled at close[i]. Fills are
    now at OPEN[i+1] -- decide, then trade the next bar.
  * NO DEGENERATE-SPREAD GUARD: the pair's 1-min spread sigma is tiny;
    z = noise/noise mints fake 2-sigma signals. Sigma floor applied
    (the pairs engine's guard, scaled to log-spread space).
  * "return > 0 over 5 days" verdict -> per-trade bps comparison, plus
    band-snap exit (|z| > 3.5), realized-cash max DD, and the disclosure
    that 5 days x 1 pair is a pulse check, not evidence.
  * Unused matplotlib import, emojis removed.

Run:  python analysis/intraday_pulse.py [--a GOOG --b GOOGL]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOOKBACK = 30
Z_ENTRY = 2.0
Z_EXIT = 0.5
Z_STOP = 3.5
PER_LEG = 2_000.0
COMMISSION_PER_SHARE = 0.005
MIN_TICKET = 1.00
SIGMA_FLOOR = 1e-5              # log-spread sigma floor (~0.1bp)
HALF_SPREAD_LADDER_BPS = (1.0, 2.0, 5.0)


def round_trip_friction(price_a: float, price_b: float,
                        half_spread_bps: float) -> float:
    """Dollar friction for one full pair round trip: 4 spread crossings
    + 4 commission tickets."""
    spread_cost = 4 * PER_LEG * half_spread_bps / 1e4
    commissions = sum(
        2 * max(MIN_TICKET, COMMISSION_PER_SHARE * (PER_LEG / px))
        for px in (price_a, price_b))
    return spread_cost + commissions


def simulate(bars_a: pd.DataFrame, bars_b: pd.DataFrame,
             lookback: int = LOOKBACK, z_entry: float = Z_ENTRY,
             z_exit: float = Z_EXIT, z_stop: float = Z_STOP) -> dict:
    """T+1-open-fill simulation on 1-minute bars (columns: open, close).
    Returns gross per-trade stats and the friction sensitivity ladder."""
    idx = bars_a.index.intersection(bars_b.index)
    a, b = bars_a.loc[idx], bars_b.loc[idx]
    spread = np.log(a["close"]) - np.log(b["close"])
    mu = spread.rolling(lookback).mean()
    sd = spread.rolling(lookback).std().where(lambda s: s > SIGMA_FLOOR)
    z = ((spread - mu) / sd).to_numpy()

    position = 0
    entry_spread = 0.0
    trades: list[dict] = []

    for i in range(lookback, len(idx) - 1):        # -1: need bar i+1 to fill
        zi = z[i]
        if not np.isfinite(zi):
            continue
        fill_a, fill_b = a["open"].iloc[i + 1], b["open"].iloc[i + 1]
        fill_spread = float(np.log(fill_a) - np.log(fill_b))

        if position == 0 and z_entry < abs(zi) <= z_stop:
            position = 1 if zi < 0 else -1
            entry_spread = fill_spread
            entry_prices = (float(fill_a), float(fill_b))
        elif position != 0 and (abs(zi) < z_exit or abs(zi) > z_stop):
            gross = PER_LEG * position * (fill_spread - entry_spread)
            trades.append({
                "gross": gross,
                "gross_bps": gross / (2 * PER_LEG) * 1e4,
                "prices": entry_prices,
                "why": "band_snap" if abs(zi) > z_stop else "reverted",
            })
            position = 0

    out = {"n_trades": len(trades), "ladder": {}}
    if not trades:
        return out
    gross = np.array([t["gross"] for t in trades])
    out["gross_total"] = float(gross.sum())
    out["gross_per_trade_bps"] = float(np.mean([t["gross_bps"] for t in trades]))
    out["trades_bps"] = [float(t["gross_bps"]) for t in trades]
    out["band_snaps"] = sum(t["why"] == "band_snap" for t in trades)

    for hs in HALF_SPREAD_LADDER_BPS:
        frictions = np.array([round_trip_friction(*t["prices"], hs)
                              for t in trades])
        net = gross - frictions
        eq = 10_000.0 + np.cumsum(net)
        peak = np.maximum.accumulate(eq)
        out["ladder"][hs] = {
            "friction_per_trade_bps": float(
                frictions.mean() / (2 * PER_LEG) * 1e4),
            "net_total": float(net.sum()),
            "win_rate": float((net > 0).mean()),
            "max_dd_realized": float(((peak - eq) / peak).max()),
        }
    return out


# ---------------------------------------------------------------------------
def threshold_grid(bars_a: pd.DataFrame, bars_b: pd.DataFrame,
                   z_grid=None, half_spread_bps: float = 2.0) -> dict:
    """The 'coach', made honest: a z-entry grid IS a multiple-comparisons
    search, so the winner is stamped with the deflated Sharpe at
    n_trials = grid size, plus a plateau check (neighbors of the peak).
    A recommendation is only a recommendation if it survives BOTH -- and
    even then, re-tuning a running paper loop RESETS the 30-day clock."""
    from backtest.deflated_sharpe import deflated_sharpe, sharpe_stats

    z_grid = np.round(np.arange(1.5, 3.6, 0.1), 1) if z_grid is None else z_grid
    rows = []
    for zt in z_grid:
        r = simulate(bars_a, bars_b, z_entry=float(zt), z_stop=float(zt) + 1.5)
        if r["n_trades"] == 0:
            rows.append({"z": float(zt), "n_trades": 0, "net_total": 0.0,
                         "net_bps": None})
            continue
        fr_bps = r["ladder"][half_spread_bps]["friction_per_trade_bps"]
        net_bps = [g - fr_bps for g in r["trades_bps"]]
        rows.append({"z": float(zt), "n_trades": r["n_trades"],
                     "net_total": r["ladder"][half_spread_bps]["net_total"],
                     "net_bps": net_bps})

    traded = [r for r in rows if r["n_trades"] >= 5]
    out = {"rows": rows, "n_configs": len(z_grid)}
    if not traded:
        out["verdict"] = "no config produced enough trades to evaluate"
        return out

    best = max(traded, key=lambda r: r["net_total"])
    trial_sharpes = [sharpe_stats(np.array(r["net_bps"]) / 1e4)["sr"]
                     for r in traded if len(r["net_bps"]) >= 5]
    d = deflated_sharpe(np.array(best["net_bps"]) / 1e4,
                        n_trials=len(z_grid),
                        trial_sharpes=trial_sharpes or None)
    # Plateau check: the peak's grid neighbors must agree in sign.
    zs = [r["z"] for r in rows]
    i = zs.index(best["z"])
    neighbors = [rows[j] for j in (i - 1, i + 1) if 0 <= j < len(rows)]
    plateau = all(n["net_total"] > 0 for n in neighbors) if best["net_total"] > 0 \
        else False
    out.update(best=best, psr=d["psr"], dsr=d["dsr"], dsr_verdict=d["verdict"],
               plateau=plateau)
    return out


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--a", default="GOOG")
    p.add_argument("--b", default="GOOGL")
    p.add_argument("--grid", action="store_true",
                   help="honest z-threshold grid audit (DSR-stamped)")
    args = p.parse_args()

    import yfinance as yf
    raw = yf.download([args.a, args.b], period="5d", interval="1m",
                      auto_adjust=True, progress=False)
    bars_a = raw[["Open", "Close"]].xs(args.a, axis=1, level=1) \
        .rename(columns=str.lower).dropna()
    bars_b = raw[["Open", "Close"]].xs(args.b, axis=1, level=1) \
        .rename(columns=str.lower).dropna()

    if args.grid:
        g = threshold_grid(bars_a, bars_b)
        print(f"HONEST COACH -- z-entry grid on {args.a}/{args.b}, "
              f"{g['n_configs']} configs, 5d of 1-min bars")
        print("  WARNING: a grid is a search. n_trials = grid size. And "
              "re-tuning the paper\n  loop RESETS the 30-day clock.")
        if "best" not in g:
            print(f"  {g['verdict']}")
            return
        for r in sorted((r for r in g["rows"] if r["n_trades"]),
                        key=lambda x: -x["net_total"])[:5]:
            print(f"    z={r['z']:.1f}  trades {r['n_trades']:>3}  "
                  f"net ${r['net_total']:>+8.2f}")
        b = g["best"]
        print(f"\n  'optimal' config: z={b['z']:.1f} "
              f"(net ${b['net_total']:+,.2f}, {b['n_trades']} trades)")
        print(f"  honesty stamp:   PSR {g['psr']:.1%} | DSR {g['dsr']:.1%} "
              f"at n_trials={g['n_configs']} | plateau: "
              f"{'yes' if g['plateau'] else 'NO -- isolated peak'}")
        print(f"  ({g['dsr_verdict']})")
        if b["net_total"] <= 0:
            print("\n  VERDICT: even the LUCKIEST of "
                  f"{g['n_configs']} configs loses net. There is nothing "
                  "to tune --\n  a threshold cannot manufacture an edge "
                  "from a signal with no gross edge.")
        elif g["dsr"] < 0.95 or not g["plateau"]:
            print("\n  VERDICT: the 'optimal' setting is a product of the "
                  "search. DO NOT retune\n  the paper loop on this.")
        else:
            print("\n  VERDICT: survives the stamp -- but confirm on a "
                  "second window before\n  touching the paper loop (and "
                  "accept the 30-day clock reset).")
        return

    res = simulate(bars_a, bars_b)

    print(f"INTRADAY PULSE CHECK -- {args.a}/{args.b}, 1-min bars, 5 days")
    print("  DISCLOSURE: 1 pair x 5 days = pulse check, not evidence; "
          "yfinance 1m is\n  delayed consolidated data; fills at next-bar "
          "open with a sigma-floored z.")
    print(f"\n  round trips: {res['n_trades']}"
          + (f" ({res['band_snaps']} band snaps)" if res["n_trades"] else ""))
    if not res["n_trades"]:
        print("  no trades -- nothing to conclude")
        return
    print(f"  GROSS edge per round trip: {res['gross_per_trade_bps']:+.2f} bps "
          f"(total ${res['gross_total']:+,.2f})")
    print(f"\n  friction sensitivity ladder (the verdict lives here):")
    print(f"  {'half-spread':>12}{'friction/trade':>16}{'net total':>12}"
          f"{'win rate':>10}{'maxDD':>8}")
    for hs, row in res["ladder"].items():
        print(f"  {hs:>10.1f}bp{row['friction_per_trade_bps']:>14.2f}bp"
              f"{row['net_total']:>+12.2f}{row['win_rate']:>10.1%}"
              f"{row['max_dd_realized']:>8.2%}")

    edge = res["gross_per_trade_bps"]
    cheapest = res["ladder"][min(HALF_SPREAD_LADDER_BPS)]
    if edge <= cheapest["friction_per_trade_bps"]:
        print("\n  VERDICT: gross edge per trade does not clear even the "
              "CHEAPEST friction\n  assumption -- the postmortem prediction "
              "holds at 1-minute bars too.")
    else:
        survivors = [hs for hs, r in res["ladder"].items()
                     if r["net_total"] > 0]
        print(f"\n  VERDICT: pulse detected at half-spreads <= "
              f"{max(survivors) if survivors else 0}bp. This is 5 days of "
              f"one pair --\n  demand a longer window + more pairs before "
              f"any further conclusion.")


if __name__ == "__main__":
    main()
