"""
analysis/fundamental_arb.py
===========================
Fundamental-twin pair discovery ("business physics") -> the price gauntlet.

Cluster companies on balance-sheet / income-statement DNA, generate pairs
only between fundamental twins, then demand the twins' PRICES mean-revert
profitably net of institutional friction.

Corrections vs the draft this was adapted from -- the big one first:
  * FATAL LOOK-AHEAD: the draft clustered on `yf.Ticker(t).info` -- TODAY'S
    fundamentals (July-2026 trailing PE, current debt/equity) -- then
    backtested the selected pairs over the PAST five years. Pair selection
    used information that did not exist during the test window, and firms
    that are "twins today" may be twins BECAUSE their prices converged over
    exactly the window being scored. Fixed by POINT-IN-TIME reconstruction:
    ratios are rebuilt from FY-2022-vintage annual statements (newest fiscal
    year ending <= 2023-03-31, prior year for growth), priced at 2023-06-30
    (a filing-lag embargo: Dec-FY 10-Ks are filed by ~March), and the
    gauntlet trades STRICTLY AFTERWARD (2023-07 -> 2026-07).
  * `from pairs_backtest import run_gauntlet` -- doesn't exist; reuses the
    verified adapter from analysis.industrial_hunter (backtest_pair +
    fund_verdict: adaptive Kelly, institutional friction).
  * Ratio outliers: near-zero earnings produce PE in the thousands; raw
    StandardScaler + euclidean would cluster on outliers. Features are
    winsorized at the 1st/99th percentile before scaling.
  * Strict all-metrics-required filter silently deleted whole sectors
    (banks report no Current Assets). Columns missing for >40% of firms are
    dropped first; only then are incomplete rows dropped -- disclosed.
  * Twin blob guard + global candidate cap (industrial_hunter lesson):
    oversized clusters contribute only their closest pairs by fundamental
    distance; every FUNDABLE gets a deflated-Sharpe stamp at n_trials = N.
  * Remaining biases DISCLOSED, not hidden: current-membership universe
    (survivorship) and vendor restatement risk (statements as currently
    reported, not necessarily as originally filed).
  * Bare `except:` clauses, emojis (cp1252 console), root-dir CSV dumps
    removed; results -> logs/fundamental_arb.json.

Run:  python analysis/fundamental_arb.py
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.industrial_hunter import IndustrialHunter, run_gauntlet

# --- Point-in-time protocol ------------------------------------------------
STATEMENT_CUTOFF = "2023-03-31"   # newest fiscal year end usable at formation
FORMATION_PRICE_DATE = "2023-06-30"  # filing-lag embargo for the price inputs
PRICE_START = "2022-06-01"        # warmup prefix for the 252d rolling OLS
PRICE_END = "2026-07-01"
TRADE_START = "2023-07-01"        # gauntlet trades from here -- after embargo

MAX_WORKERS = 8                   # statement scraping (gentle on the vendor)
MAX_COL_MISSING = 0.40            # drop a metric missing for >40% of firms
MAX_CLUSTER = 12                  # bigger = a style factor, not twins
BLOB_TOP_PAIRS = 20
MAX_CANDIDATES = 300


# ---------------------------------------------------------------------------
def pick_vintage(stmt: pd.DataFrame, cutoff: str = STATEMENT_CUTOFF
                 ) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """(formation fiscal year end, prior year end) -- newest column at or
    before the cutoff plus the column before it. None if unavailable."""
    if stmt is None or stmt.empty:
        return None
    cols = sorted(pd.to_datetime(stmt.columns))
    usable = [c for c in cols if c <= pd.Timestamp(cutoff)]
    if len(usable) < 2:
        return None
    return usable[-1], usable[-2]


def row(stmt: pd.DataFrame, col: pd.Timestamp, *names: str) -> float:
    """First matching line item, NaN if absent."""
    for n in names:
        if n in stmt.index:
            v = stmt.at[n, col]
            if pd.notna(v):
                return float(v)
    return np.nan


def build_features(inc: pd.DataFrame, bs: pd.DataFrame,
                   price_formation: float) -> dict | None:
    """FY-vintage fundamental ratios priced at the formation date.
    Everything here was knowable on FORMATION_PRICE_DATE."""
    vintage = pick_vintage(inc)
    if vintage is None or pick_vintage(bs) is None:
        return None
    fy, prior = vintage
    if fy not in bs.columns:
        return None

    net_income = row(inc, fy, "Net Income", "Net Income Common Stockholders")
    revenue = row(inc, fy, "Total Revenue")
    revenue_prior = row(inc, prior, "Total Revenue")
    ebitda = row(inc, fy, "EBITDA", "Normalized EBITDA")
    equity = row(bs, fy, "Stockholders Equity")
    debt = row(bs, fy, "Total Debt")
    cur_assets = row(bs, fy, "Current Assets")
    cur_liab = row(bs, fy, "Current Liabilities")
    cash = row(bs, fy, "Cash And Cash Equivalents",
               "Cash Cash Equivalents And Short Term Investments")
    shares = row(bs, fy, "Ordinary Shares Number", "Share Issued")

    if not np.isfinite([net_income, revenue, equity, shares]).all() \
            or shares <= 0 or revenue <= 0 or not np.isfinite(price_formation):
        return None

    mktcap = price_formation * shares
    ev = mktcap + (debt if np.isfinite(debt) else 0.0) \
        - (cash if np.isfinite(cash) else 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return {
            "pe": mktcap / net_income if net_income != 0 else np.nan,
            "pb": mktcap / equity if equity != 0 else np.nan,
            "ev_ebitda": ev / ebitda if np.isfinite(ebitda) and ebitda != 0 else np.nan,
            "debt_to_equity": debt / equity if np.isfinite(debt) and equity != 0 else np.nan,
            "current_ratio": cur_assets / cur_liab
                             if np.isfinite([cur_assets, cur_liab]).all() and cur_liab != 0
                             else np.nan,
            "profit_margin": net_income / revenue,
            "roe": net_income / equity if equity != 0 else np.nan,
            "revenue_growth": revenue / revenue_prior - 1.0
                              if np.isfinite(revenue_prior) and revenue_prior > 0
                              else np.nan,
        }


def clean_matrix(matrix: pd.DataFrame,
                 max_col_missing: float = MAX_COL_MISSING) -> pd.DataFrame:
    """Drop metrics missing for too many firms FIRST (keeps banks that report
    no current ratio), then drop incomplete rows, then winsorize 1%/99%."""
    m = matrix.replace([np.inf, -np.inf], np.nan)
    keep = m.columns[m.isna().mean() <= max_col_missing]
    m = m[keep].dropna()
    return m.clip(m.quantile(0.01), m.quantile(0.99), axis=1)


def twin_candidates(matrix: pd.DataFrame,
                    max_cluster: int = MAX_CLUSTER,
                    blob_top: int = BLOB_TOP_PAIRS,
                    cap: int = MAX_CANDIDATES) -> tuple[list[tuple[str, str]], dict]:
    """OPTICS on winsorized+scaled ratios; pairs only within clusters,
    ranked by fundamental-space distance (closest twins first). Oversized
    clusters (style factors) contribute only their closest pairs."""
    from sklearn.cluster import OPTICS
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(matrix.to_numpy())
    labels = OPTICS(min_samples=2, metric="euclidean",
                    xi=0.05).fit_predict(X)
    pos = {t: X[i] for i, t in enumerate(matrix.index)}
    by_cluster: dict[int, list[str]] = {}
    for t, l in zip(matrix.index, labels):
        if l != -1:
            by_cluster.setdefault(int(l), []).append(t)

    scored: list[tuple[float, str, str]] = []
    for members in by_cluster.values():
        members = sorted(members)
        pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
        pairs.sort(key=lambda p: float(np.linalg.norm(pos[p[0]] - pos[p[1]])))
        if len(members) > max_cluster:
            pairs = pairs[:blob_top]
        scored.extend((float(np.linalg.norm(pos[a] - pos[b])), a, b)
                      for a, b in pairs)
    scored.sort()                                     # closest twins first
    return [(a, b) for _, a, b in scored[:cap]], by_cluster


# ---------------------------------------------------------------------------
class FundamentalArbEngine:
    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or []
        self.matrix: pd.DataFrame | None = None      # injectable for tests
        self.prices: pd.DataFrame | None = None      # injectable for tests

    # ------------------------------------------------------------------
    def fetch_universe(self) -> list[str]:
        if not self.tickers:
            self.tickers = IndustrialHunter().fetch_universe()
        return self.tickers

    def fetch_prices(self) -> pd.DataFrame:
        if self.prices is None:
            hunter = IndustrialHunter(tickers=self.tickers)
            import analysis.industrial_hunter as ih
            old_start, old_end = ih.FORMATION_START, ih.PERIOD_2_END
            ih.FORMATION_START, ih.PERIOD_2_END = PRICE_START, PRICE_END
            try:
                self.prices = hunter.ingest()
            finally:
                ih.FORMATION_START, ih.PERIOD_2_END = old_start, old_end
        return self.prices

    # ------------------------------------------------------------------
    def _fetch_single(self, ticker: str, price_formation: float) -> dict | None:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            feats = build_features(t.income_stmt, t.balance_sheet,
                                   price_formation)
        except Exception:  # noqa: BLE001 - vendor boundary, drop the name
            return None
        if feats is None:
            return None
        return {"symbol": ticker, **feats}

    def ingest_business_physics(self) -> pd.DataFrame:
        """Point-in-time fundamental matrix. Prices at the FORMATION date --
        never today's -- feed the valuation ratios."""
        if self.matrix is not None:
            return self.matrix
        prices = self.fetch_prices()
        asof = prices.loc[:FORMATION_PRICE_DATE].iloc[-1]
        universe = [t for t in prices.columns]
        print(f"  reconstructing FY2022-vintage fundamentals for "
              f"{len(universe)} firms ({MAX_WORKERS} workers)...")
        rows = []
        with concurrent.futures.ThreadPoolExecutor(MAX_WORKERS) as pool:
            futs = {pool.submit(self._fetch_single, t, float(asof[t])): t
                    for t in universe}
            for i, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                r = fut.result()
                if r:
                    rows.append(r)
                if i % 100 == 0:
                    print(f"    {i}/{len(universe)} processed, "
                          f"{len(rows)} usable")
        raw = pd.DataFrame(rows).set_index("symbol")
        self.matrix = clean_matrix(raw)
        print(f"  fundamental matrix: {len(self.matrix)}/{len(universe)} firms, "
              f"metrics kept: {list(self.matrix.columns)}")
        return self.matrix

    # ------------------------------------------------------------------
    def run(self) -> dict:
        matrix = self.ingest_business_physics()
        prices = self.fetch_prices()

        candidates, clusters = twin_candidates(matrix)
        n = len(candidates)

        gauntlet_px = prices.loc[:]                   # warmup consumed causally
        rows, confirmed = [], []
        for a, b in candidates:
            if a not in gauntlet_px.columns or b not in gauntlet_px.columns:
                continue
            r = run_gauntlet(gauntlet_px[a], gauntlet_px[b])
            row_ = {"pair": f"{a}/{b}", **{k: r[k] for k in
                    ("verdict", "net_return", "max_dd", "sharpe",
                     "n_trades", "risk_of_ruin", "fail_reason")}}
            if r["verdict"] == "FUNDABLE":
                from backtest.deflated_sharpe import deflated_sharpe
                rets = r["equity"].pct_change().dropna()
                d = deflated_sharpe(rets.to_numpy(), n_trials=max(n, 1))
                row_.update(psr=d["psr"], dsr=d["dsr"],
                            dsr_verdict=d["verdict"])
                confirmed.append(row_)
            rows.append(row_)

        return {
            "n_firms": int(len(matrix)),
            "metrics": list(matrix.columns),
            "n_clusters": len(clusters),
            "clusters": {int(k): sorted(v) for k, v in clusters.items()},
            "n_candidates": n,
            "results": rows,
            "confirmed": confirmed,
            "protocol": {
                "statement_vintage": f"newest FY <= {STATEMENT_CUTOFF}",
                "formation_price": FORMATION_PRICE_DATE,
                "trading": f"~{TRADE_START} -> {PRICE_END} "
                           f"(252d OLS warmup consumed causally)",
            },
        }


# ---------------------------------------------------------------------------
def main() -> None:
    eng = FundamentalArbEngine()
    eng.fetch_universe()
    out = eng.run()

    print(f"\nFUNDAMENTAL ARB -- point-in-time twins -> price gauntlet")
    p = out["protocol"]
    print(f"  statements: {p['statement_vintage']} | formation price "
          f"{p['formation_price']} | trading {p['trading']}")
    print(f"  DISCLOSURES: current S&P membership (survivorship bias); "
          f"statements as\n  currently reported (vendor restatement risk)")

    print(f"\n  {out['n_firms']} firms x {len(out['metrics'])} metrics -> "
          f"{out['n_clusters']} fundamental clusters -> "
          f"{out['n_candidates']} twin pairs")

    fundable = [r for r in out["results"] if r["verdict"] == "FUNDABLE"]
    dead = [r for r in out["results"] if r["verdict"] != "FUNDABLE"]
    print(f"\n  gauntlet: {len(fundable)} FUNDABLE / {len(dead)} DEAD of "
          f"{out['n_candidates']} (expected false positives at 5%: "
          f"~{out['n_candidates'] * 0.05:.1f})")
    for r in sorted(fundable, key=lambda x: -x["net_return"]):
        print(f"    {r['pair']:<12}{r['net_return']:>+8.1%}  "
              f"maxDD {r['max_dd']:.1%}  sharpe {r['sharpe']:.2f}  "
              f"trades {r['n_trades']}  DSR {r['dsr']:.1%} ({r['dsr_verdict']})")
    if not fundable:
        print("    none -- fundamental twins did not mean-revert profitably "
              "net of friction")

    log = ROOT / "logs" / "fundamental_arb.json"
    log.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n  results -> {log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
