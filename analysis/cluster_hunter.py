"""
analysis/cluster_hunter.py
==========================
Cluster-first pair discovery -> the funding gauntlet.

Unsupervised co-movement clustering (PCA + OPTICS, cosine) generates pair
candidates ONLY within dense clusters, then every candidate runs through the
verified pairs gauntlet (backtest_pair + fund_verdict) with adaptive Kelly.

Corrections vs the draft this was adapted from:
  * `returns.T['cluster'] = ...` assigned a column to a TEMPORARY transpose
    (evaporates; next access raises KeyError). Cluster labels now live in a
    proper ticker -> label mapping.
  * yfinance 'Adj Close' no longer exists under auto_adjust defaults -> Close.
  * SELECTION LOOK-AHEAD fixed: clustering fits on a FORMATION window only;
    the gauntlet backtests the pairs on the SUBSEQUENT trading window. The
    draft clustered and backtested the same period, so pair selection had
    already seen the test answers.
  * Multiple-comparisons disclosure: any FUNDABLE verdict is reported as
    1-of-N-searched -- at a 5% false-positive rate, N candidates are expected
    to produce N/20 false FUNDABLEs by luck alone.

Run:  python analysis/cluster_hunter.py
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
    "XLK", "SOXL", "NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "TXN",   # semis
    "XLE", "XOM", "CVX", "COP", "EOG", "SLB", "MPC",                      # energy
    "XLF", "JPM", "BAC", "WFC", "C", "GS", "MS",                          # financials
    "QQQ", "SPY", "IWM", "DIA", "TLT", "GLD", "SLV",                      # macro
]
LOOKBACK_YEARS = 6          # draft's 2y is too short: 252d rolling OLS + real OOS
FORMATION_FRAC = 0.40       # cluster on the first 40%, gauntlet on the rest


class ClusterHunter:
    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or UNIVERSE
        self.prices: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    def fetch_data(self) -> pd.DataFrame:
        import yfinance as yf
        raw = yf.download(self.tickers, period=f"{LOOKBACK_YEARS}y",
                          interval="1d", auto_adjust=True, progress=False)["Close"]
        raw = raw.dropna(axis=1, thresh=int(len(raw) * 0.95)).ffill().dropna()
        self.prices = raw
        return raw

    # ------------------------------------------------------------------
    @staticmethod
    def cluster_assets(returns: pd.DataFrame, min_samples: int = 2) -> dict[str, int]:
        """Ticker -> cluster label (-1 = noise). Fit ONLY on the window passed in."""
        from sklearn.cluster import OPTICS
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        X = StandardScaler().fit_transform(returns.T.to_numpy())   # assets as rows
        # PCA denoising (95% variance) when there is room to reduce; tiny
        # synthetic inputs skip it.
        Xp = PCA(n_components=0.95).fit_transform(X) if min(X.shape) > 4 else X
        labels = OPTICS(min_samples=min_samples, metric="cosine",
                        xi=0.05).fit_predict(Xp)
        return dict(zip(returns.columns, (int(l) for l in labels)))

    @staticmethod
    def pairs_within_clusters(labels: dict[str, int]) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        by_cluster: dict[int, list[str]] = {}
        for t, l in labels.items():
            if l != -1:
                by_cluster.setdefault(l, []).append(t)
        for members in by_cluster.values():
            members = sorted(members)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    out.append((members[i], members[j]))
        return out

    # ------------------------------------------------------------------
    def run_pipeline(self) -> dict:
        from backtest.pairs_backtest import PairConfig, backtest_pair, fund_verdict

        prices = self.prices if self.prices is not None else self.fetch_data()
        split = int(len(prices) * FORMATION_FRAC)
        formation = prices.iloc[:split]
        trading = prices.iloc[split:]                     # STRICTLY out-of-sample

        form_rets = np.log(formation / formation.shift(1)).dropna()
        labels = self.cluster_assets(form_rets)
        candidates = self.pairs_within_clusters(labels)

        results = []
        for a, b in candidates:
            cfg = PairConfig(kelly_sizing=True)
            res = backtest_pair(trading[a], trading[b], cfg)
            v = fund_verdict(res)
            results.append({"pair": f"{a}/{b}",
                            "net_return": res.metrics["total_return"],
                            "max_dd": res.metrics["max_dd"],
                            "sharpe": res.metrics["sharpe"],
                            "n_trades": res.metrics["n_trades"],
                            "status": v["status"],
                            "fail_reasons": v["fail_reasons"],
                            "risk_of_ruin": v["risk_of_ruin"]})
        clusters = {}
        for t, l in labels.items():
            if l != -1:
                clusters.setdefault(l, []).append(t)
        return {"clusters": clusters, "n_candidates": len(candidates),
                "results": results,
                "formation": f"{formation.index[0]:%Y-%m-%d} -> {formation.index[-1]:%Y-%m-%d}",
                "trading": f"{trading.index[0]:%Y-%m-%d} -> {trading.index[-1]:%Y-%m-%d}"}


# ---------------------------------------------------------------------------
def main() -> None:
    hunter = ClusterHunter()
    out = hunter.run_pipeline()

    print(f"CLUSTER HUNTER -> GAUNTLET   formation {out['formation']} | "
          f"trading (OOS) {out['trading']}")
    print(f"\n  co-movement clusters (formation window only):")
    for cid, members in out["clusters"].items():
        print(f"    cluster {cid}: {', '.join(members)}")
    print(f"\n  {out['n_candidates']} candidate pairs -> gauntlet "
          f"(adaptive Kelly, full friction, 3 gates):\n")
    print(f"  {'pair':<12}{'net ret':>9}{'maxDD':>8}{'sharpe':>8}{'trades':>8}{'RoR':>7}  verdict")
    fundable = []
    for r in sorted(out["results"], key=lambda x: -x["net_return"]):
        print(f"  {r['pair']:<12}{r['net_return']:>+9.1%}{r['max_dd']:>8.1%}"
              f"{r['sharpe']:>8.2f}{r['n_trades']:>8}{r['risk_of_ruin']:>7.1%}"
              f"  {r['status']}"
              + (f" ({r['fail_reasons'][0]})" if r["fail_reasons"] else ""))
        if r["status"] == "FUNDABLE":
            fundable.append(r["pair"])

    n = out["n_candidates"]
    print(f"\n  FUNDABLE: {len(fundable)} of {n} searched "
          f"(expected false positives at 5% gate: ~{n * 0.05:.1f})")
    if fundable:
        print(f"  {fundable}")
        print("  WARNING: each survivor is 1-of-N-searched. Demand an economic linkage")
        print("  and a second out-of-sample period before any capital discussion.")


if __name__ == "__main__":
    main()
