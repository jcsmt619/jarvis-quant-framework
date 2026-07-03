"""
analysis/industrial_hunter.py
=============================
Double-blind industrial-scale pair discovery:

    S&P 500 universe -> co-movement clusters (fit on 2018-2019 ONLY)
      -> Gauntlet A  (2020-2023, first out-of-sample)
      -> Gate B      (2023-2026, second untouched out-of-sample)
      -> deflated-Sharpe stamp on anything that survives both.

Corrections vs the draft this was adapted from:
  * `from pairs_backtest import run_gauntlet` -- no such function exists.
    Adapter wraps the verified engine (backtest_pair + fund_verdict,
    adaptive Kelly, institutional friction) into the draft's dict contract.
  * SELECTION LOOK-AHEAD inside Period 1: the draft clustered on ALL of
    2020-2023 and ran Gauntlet A on the SAME window -- Gate-1 "survivors"
    were selected on their own test answers (the exact bug fixed in
    cluster_hunter). Now clustering fits on a dedicated 2018-2019 formation
    window that is never traded; both gates are genuinely out-of-sample.
  * Rolling-OLS warmup: each gauntlet slice is prefixed with ols_window +
    z_window bars of PRIOR history so signals go live at the start of the
    intended trading window (prefix is consumed causally, never traded).
  * Factor-blob guard: OPTICS on ~500 names produces sector-sized clusters;
    C(50,2) = 1225 pairs from one blob is a luck factory. Oversized clusters
    contribute only their top pairs by formation correlation, plus a global
    candidate cap.
  * Multiple-comparisons accounting: every Gate-B survivor gets a deflated
    Sharpe with n_trials = TOTAL candidates searched (the whole pipeline
    selected from N, so N is the honest trial count).
  * SURVIVORSHIP BIAS disclosure: scraping the CURRENT S&P 500 membership
    and trading it back to 2020 excludes every name removed along the way.
  * Emojis stripped (cp1252 console), unused imports (DBSCAN, requests-only
    usage) removed, single-ticker yfinance batch handled.

Run:  python analysis/industrial_hunter.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.pairs_backtest import PairConfig, backtest_pair, fund_verdict

# --- The double-blind protocol -------------------------------------------
FORMATION_START = "2018-01-01"   # clustering fits here and ONLY here
GAUNTLET_A_START = "2020-01-01"  # first OOS window (includes covid regime)
PERIOD_2_START = "2023-01-02"    # second OOS window (different regime)
PERIOD_2_END = "2026-07-01"

MAX_CLUSTER = 12                 # bigger = factor blob, not a relationship
BLOB_TOP_PAIRS = 20              # oversized clusters contribute only these
MAX_CANDIDATES = 400             # global cap (runtime + honesty)
MIN_SAMPLES = 3                  # OPTICS density for a 500-name universe

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK_UNIVERSE = [
    "AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC",
    "WFC", "C", "XOM", "CVX", "COP", "SLB", "LLY", "UNH", "JNJ", "PG", "KO",
    "PEP", "COST", "WMT", "TGT", "HD", "LOW", "MCD", "SBUX", "NKE", "DIS",
    "NFLX", "CMCSA", "VZ", "T", "NEE", "DUK", "SO", "PLD", "AMT", "CCI",
    "SPY", "QQQ", "IWM", "GLD", "SLV", "TLT", "XLK", "XLE", "XLF", "XLV",
    "XLI",
]


# ---------------------------------------------------------------------------
def protocol_windows(index: pd.DatetimeIndex, warmup: int) -> dict:
    """Iloc slices for the three windows. Gauntlet slices carry a `warmup`
    prefix of prior history for the rolling OLS/z -- consumed causally,
    trades begin at the window boundary."""
    a_start = int(index.searchsorted(GAUNTLET_A_START))
    b_start = int(index.searchsorted(PERIOD_2_START))
    return {
        "formation": slice(0, a_start),
        "gate_a": slice(max(0, a_start - warmup), b_start),
        "gate_b": slice(max(0, b_start - warmup), len(index)),
        "a_trade_start": a_start,
        "b_trade_start": b_start,
    }


def candidates_from_clusters(labels: dict[str, int], form_rets: pd.DataFrame,
                             max_cluster: int = MAX_CLUSTER,
                             blob_top: int = BLOB_TOP_PAIRS,
                             cap: int = MAX_CANDIDATES) -> list[tuple[str, str]]:
    """All pairs within small clusters; oversized clusters (factor blobs)
    contribute only their top pairs by |formation correlation|. Global cap.
    Correlation ranking uses the FORMATION window only -- no selection on
    traded data."""
    by_cluster: dict[int, list[str]] = {}
    for t, l in labels.items():
        if l != -1:
            by_cluster.setdefault(l, []).append(t)
    corr = form_rets.corr()
    scored: list[tuple[float, str, str]] = []
    for members in by_cluster.values():
        members = sorted(members)
        pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
        pairs.sort(key=lambda p: -abs(corr.loc[p[0], p[1]]))
        if len(members) > max_cluster:
            pairs = pairs[:blob_top]
        scored.extend((abs(float(corr.loc[a, b])), a, b) for a, b in pairs)
    scored.sort(reverse=True)
    return [(a, b) for _, a, b in scored[:cap]]


def run_gauntlet(pa: pd.Series, pb: pd.Series) -> dict:
    """Adapter: verified pairs engine -> the draft's expected contract."""
    res = backtest_pair(pa.dropna(), pb.dropna(), PairConfig(kelly_sizing=True))
    v = fund_verdict(res)
    return {
        "verdict": v["status"],
        "cagr": float(res.metrics["cagr"]),
        "net_return": float(res.metrics["total_return"]),
        "max_dd": float(res.metrics["max_dd"]),
        "sharpe": float(res.metrics["sharpe"]),
        "n_trades": int(res.metrics["n_trades"]),
        "risk_of_ruin": float(v["risk_of_ruin"]),
        "fail_reason": "; ".join(v["fail_reasons"]),
        "equity": res.equity,
    }


# ---------------------------------------------------------------------------
class IndustrialHunter:
    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or []
        self.prices: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    def fetch_universe(self) -> list[str]:
        """Current S&P 500 constituents (SURVIVORSHIP BIAS: names removed
        since 2018 are absent -- disclosed in the report)."""
        if self.tickers:
            return self.tickers
        try:
            import requests
            resp = requests.get(WIKI_URL, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            table = pd.read_html(io.StringIO(resp.text))[0]
            self.tickers = sorted({str(s).replace(".", "-")
                                   for s in table["Symbol"].tolist()})
            print(f"  S&P 500 universe loaded: {len(self.tickers)} names "
                  f"(CURRENT membership -> survivorship bias, disclosed)")
        except Exception as e:  # noqa: BLE001 - network boundary
            print(f"  WARNING: S&P scrape failed ({e}); "
                  f"falling back to {len(FALLBACK_UNIVERSE)}-name liquid universe")
            self.tickers = list(FALLBACK_UNIVERSE)
        return self.tickers

    def ingest(self, batch_size: int = 50) -> pd.DataFrame:
        import yfinance as yf
        frames = []
        for i in range(0, len(self.tickers), batch_size):
            batch = self.tickers[i:i + batch_size]
            try:
                df = yf.download(batch, start=FORMATION_START, end=PERIOD_2_END,
                                 auto_adjust=True, progress=False)["Close"]
                if isinstance(df, pd.Series):          # single-ticker batch
                    df = df.to_frame(batch[0])
                frames.append(df)
            except Exception as e:  # noqa: BLE001 - network boundary
                print(f"  batch {i // batch_size + 1} failed: {e}")
        if not frames:
            raise RuntimeError("data ingestion failed for every batch")
        full = pd.concat(frames, axis=1)
        # >3% missing = IPO/delisting/bad feed -> drop the column, keep the rows
        full = full.dropna(axis=1, thresh=int(len(full) * 0.97)).ffill().dropna()
        self.prices = full
        print(f"  clean dataset: {full.shape[1]} assets x {full.shape[0]} bars "
              f"({full.index[0]:%Y-%m-%d} -> {full.index[-1]:%Y-%m-%d})")
        return full

    # ------------------------------------------------------------------
    def run(self) -> dict:
        from analysis.cluster_hunter import ClusterHunter

        prices = self.prices if self.prices is not None else self.ingest()
        cfg = PairConfig()
        warmup = cfg.ols_window + cfg.z_window
        w = protocol_windows(prices.index, warmup)

        formation = prices.iloc[w["formation"]]
        form_rets = np.log(formation / formation.shift(1)).dropna()
        labels = ClusterHunter.cluster_assets(form_rets, min_samples=MIN_SAMPLES)
        clusters: dict[int, list[str]] = {}
        for t, l in labels.items():
            if l != -1:
                clusters.setdefault(l, []).append(t)
        candidates = candidates_from_clusters(labels, form_rets)
        n = len(candidates)

        ga, gb = prices.iloc[w["gate_a"]], prices.iloc[w["gate_b"]]

        gate_a_rows, survivors = [], []
        for a, b in candidates:
            r = run_gauntlet(ga[a], ga[b])
            gate_a_rows.append({"pair": f"{a}/{b}", **{k: r[k] for k in
                                ("verdict", "net_return", "max_dd", "sharpe",
                                 "n_trades", "risk_of_ruin", "fail_reason")}})
            if r["verdict"] == "FUNDABLE":
                survivors.append((a, b))

        gate_b_rows, confirmed = [], []
        for a, b in survivors:
            r = run_gauntlet(gb[a], gb[b])
            row = {"pair": f"{a}/{b}", **{k: r[k] for k in
                   ("verdict", "net_return", "max_dd", "sharpe",
                    "n_trades", "risk_of_ruin", "fail_reason")}}
            if r["verdict"] == "FUNDABLE":
                # Deflate against the WHOLE search, not just Gate B.
                from backtest.deflated_sharpe import deflated_sharpe
                rets = r["equity"].pct_change().dropna()
                d = deflated_sharpe(rets.to_numpy(), n_trials=max(n, 1))
                row.update(psr=d["psr"], dsr=d["dsr"], dsr_verdict=d["verdict"])
                confirmed.append(row)
            gate_b_rows.append(row)

        return {
            "universe_size": prices.shape[1],
            "clusters": {int(k): sorted(v) for k, v in clusters.items()},
            "n_candidates": n,
            "gate_a": gate_a_rows,
            "gate_b": gate_b_rows,
            "confirmed": confirmed,
            "windows": {
                "formation": f"{formation.index[0]:%Y-%m-%d} -> "
                             f"{formation.index[-1]:%Y-%m-%d}",
                "gate_a": f"{prices.index[w['a_trade_start']]:%Y-%m-%d} -> "
                          f"{prices.index[w['b_trade_start'] - 1]:%Y-%m-%d}",
                "gate_b": f"{prices.index[w['b_trade_start']]:%Y-%m-%d} -> "
                          f"{prices.index[-1]:%Y-%m-%d}",
            },
        }


# ---------------------------------------------------------------------------
def main() -> None:
    hunter = IndustrialHunter()
    hunter.fetch_universe()
    hunter.ingest()
    out = hunter.run()

    print(f"\nINDUSTRIAL HUNTER -- double-blind protocol")
    print(f"  formation (cluster fit only): {out['windows']['formation']}")
    print(f"  Gate A (first OOS)          : {out['windows']['gate_a']}")
    print(f"  Gate B (second OOS)         : {out['windows']['gate_b']}")
    print(f"  DISCLOSURE: universe = CURRENT S&P membership (survivorship bias)")

    print(f"\n  clusters found: {len(out['clusters'])} | "
          f"candidates after blob guard: {out['n_candidates']}")

    surv_a = [r for r in out["gate_a"] if r["verdict"] == "FUNDABLE"]
    print(f"\n  Gate A: {len(surv_a)} of {out['n_candidates']} FUNDABLE "
          f"(expected false positives at 5%: ~{out['n_candidates'] * 0.05:.1f})")
    for r in sorted(surv_a, key=lambda x: -x["net_return"]):
        print(f"    {r['pair']:<12}{r['net_return']:>+8.1%}  maxDD {r['max_dd']:.1%}"
              f"  sharpe {r['sharpe']:.2f}  trades {r['n_trades']}")

    print(f"\n  Gate B (second OOS, different regime):")
    for r in sorted(out["gate_b"], key=lambda x: -x["net_return"]):
        tag = "CONFIRMED" if r["verdict"] == "FUNDABLE" else "DEAD"
        extra = (f"  DSR {r['dsr']:.1%} ({r['dsr_verdict']})"
                 if r["verdict"] == "FUNDABLE"
                 else f"  ({r['fail_reason']})")
        print(f"    {r['pair']:<12}{r['net_return']:>+8.1%}  {tag}{extra}")

    print(f"\n  FINAL: {len(out['confirmed'])} pair(s) survived BOTH gates "
          f"out of {out['n_candidates']} searched.")
    if not out["confirmed"]:
        print("  Honest verdict: the double-blind protocol found nothing fundable.")

    log = ROOT / "logs" / "industrial_hunter.json"
    log.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n  results -> {log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
