"""
analysis/structural_arb.py
==========================
Structural (dual-class) arbitrage: pairs linked by CORPORATE CHARTER, not
statistics. Class A and Class B/C of the same company own the same cash
flows -- a reversion force exists BY CONSTRUCTION, and the candidate list
is declared ex ante, so the honest trial count is tiny (N = list length).
This is the first hunt this session where selection involves no search.

Corrections vs the draft this was adapted from:
  * FULL-SAMPLE STATIC OLS hedge ratio -- fit on all 5 years including the
    future (the exact leak pairs_backtest exists to prevent). Replaced with
    the verified engine's rolling walk-forward OLS.
  * BROKEN EQUITY CURVE: `equity_curve.append(cash)` while positions are
    open -- equity plunges by the position value at every entry, fabricating
    drawdowns; `trade_pnl = cash - equity_curve[-1]` was noise. Replaced
    with the engine's mark-to-market accounting.
  * Same-bar fills (signal at t, executed at t) -> engine's t+1 fills.
  * The homemade "deflated Sharpe" (sharpe / sqrt(2 ln N), "target > 1.0")
    is not the Bailey-Lopez de Prado statistic: no trial-variance scaling,
    no PSR transform, and an annualized SR compared to a per-period ceiling.
    Replaced with backtest.deflated_sharpe (the real one), n_trials = N.
  * Borrow sensitivity instead of one blended guess: every pair runs at
    general-collateral (0.5%/yr) AND elevated (3%/yr) borrow. The verdict
    uses the ELEVATED run (pessimistic); GC is shown as reference.
  * Dual-class spreads are tight by construction -- the engine's degenerate-
    spread guard (spread vol >= 1bp of price A) is a feature here, not a
    bug: it refuses to trade float-noise where costs exceed the signal.
  * Emojis (cp1252), root-dir CSV dumps removed; results -> logs JSON.

Run:  python analysis/structural_arb.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.pairs_backtest import PairConfig, backtest_pair, fund_verdict
from utils.friction import FrictionConfig, InstitutionalFrictionEngine

# The "truth list": declared by corporate charter BEFORE looking at prices.
# (voting-ish class, non-voting-ish class, note)
STRUCTURAL_PAIRS: list[tuple[str, str, str]] = [
    ("GOOGL", "GOOG", "Alphabet A (voting) vs C (non-voting)"),
    ("FOXA", "FOX", "Fox Corp A vs B"),
    ("NWSA", "NWS", "News Corp A vs B"),
    ("UHAL", "UHAL-B", "U-Haul common vs series N"),
    ("HEI", "HEI-A", "Heico common vs A"),
    ("Z", "ZG", "Zillow C vs A"),
    ("LEN", "LEN-B", "Lennar A vs B"),
    ("BF-A", "BF-B", "Brown-Forman A vs B"),
    ("GEF", "GEF-B", "Greif A vs B"),
    ("MKC-V", "MKC", "McCormick voting vs non-voting"),
]

HISTORY_PERIOD = "5y"
GC_BORROW = 0.005      # general collateral -- realistic for mega-cap classes
ELEVATED_BORROW = 0.03 # pessimistic blended rate; the verdict uses this


# ---------------------------------------------------------------------------
def run_structural(pa: pd.Series, pb: pd.Series, borrow_annual: float) -> dict:
    """Verified engine (rolling OLS, t+1 fills, MTM equity, adaptive Kelly)
    with the borrow rate under test."""
    eng = InstitutionalFrictionEngine(FrictionConfig(htb_borrow_annual=borrow_annual))
    res = backtest_pair(pa.dropna(), pb.dropna(),
                        PairConfig(kelly_sizing=True), friction=eng)
    v = fund_verdict(res)
    return {
        "verdict": v["status"],
        "net_return": float(res.metrics["total_return"]),
        "max_dd": float(res.metrics["max_dd"]),
        "sharpe": float(res.metrics["sharpe"]),
        "n_trades": int(res.metrics["n_trades"]),
        "risk_of_ruin": float(v["risk_of_ruin"]),
        "fail_reason": "; ".join(v["fail_reasons"]),
        "equity": res.equity,
    }


def fetch_prices(pairs: list[tuple[str, str, str]] = STRUCTURAL_PAIRS
                 ) -> pd.DataFrame:
    import yfinance as yf
    tickers = sorted({t for a, b, _ in pairs for t in (a, b)})
    px = yf.download(tickers, period=HISTORY_PERIOD, auto_adjust=True,
                     progress=False)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(tickers[0])
    return px.ffill()


def run_pipeline(prices: pd.DataFrame | None = None,
                 pairs: list[tuple[str, str, str]] | None = None) -> dict:
    pairs = pairs or STRUCTURAL_PAIRS
    px = prices if prices is not None else fetch_prices(pairs)
    n_trials = len(pairs)                      # ex-ante, declared list = honest N

    rows, skipped = [], []
    for a, b, note in pairs:
        if a not in px.columns or b not in px.columns \
                or px[a].dropna().empty or px[b].dropna().empty:
            skipped.append(f"{a}/{b}")
            continue
        gc = run_structural(px[a], px[b], GC_BORROW)
        hi = run_structural(px[a], px[b], ELEVATED_BORROW)
        row = {"pair": f"{a}/{b}", "note": note,
               "gc_net_return": gc["net_return"], "gc_verdict": gc["verdict"],
               **{k: hi[k] for k in ("verdict", "net_return", "max_dd",
                                     "sharpe", "n_trades", "risk_of_ruin",
                                     "fail_reason")}}
        if hi["verdict"] == "FUNDABLE":        # pessimistic borrow must pass
            from backtest.deflated_sharpe import deflated_sharpe
            rets = hi["equity"].pct_change().dropna()
            d = deflated_sharpe(rets.to_numpy(), n_trials=n_trials)
            row.update(psr=d["psr"], dsr=d["dsr"], dsr_verdict=d["verdict"])
        rows.append(row)

    return {"n_trials": n_trials, "results": rows, "skipped": skipped,
            "confirmed": [r for r in rows if r["verdict"] == "FUNDABLE"]}


# ---------------------------------------------------------------------------
def main() -> None:
    out = run_pipeline()

    print("STRUCTURAL ARB -- charter-linked pairs (ex-ante list, no search)")
    print(f"  N = {out['n_trials']} pairs declared before any price was seen")
    print(f"  verdict borrow {ELEVATED_BORROW:.1%}/yr (pessimistic); "
          f"GC {GC_BORROW:.1%}/yr shown for reference")
    if out["skipped"]:
        print(f"  skipped (no price data): {', '.join(out['skipped'])}")

    print(f"\n  {'pair':<12}{'net(3%)':>9}{'net(GC)':>9}{'maxDD':>8}"
          f"{'sharpe':>8}{'trades':>8}  verdict")
    for r in sorted(out["results"], key=lambda x: -x["net_return"]):
        print(f"  {r['pair']:<12}{r['net_return']:>+9.1%}"
              f"{r['gc_net_return']:>+9.1%}{r['max_dd']:>8.1%}"
              f"{r['sharpe']:>8.2f}{r['n_trades']:>8}  {r['verdict']}"
              + (f"  DSR {r['dsr']:.1%} ({r['dsr_verdict']})"
                 if r["verdict"] == "FUNDABLE"
                 else (f" ({r['fail_reason']})" if r["fail_reason"] else "")))

    print(f"\n  FUNDABLE under pessimistic borrow: {len(out['confirmed'])} "
          f"of {out['n_trials']}")
    if not out["confirmed"]:
        print("  Honest verdict: charter-linked reversion exists but does not "
              "pay net of friction.")

    log = ROOT / "logs" / "structural_arb.json"
    log.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n  results -> {log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
