"""
strategies/meridian_lite.py
===========================
Phase 2: Meridian-Lite BETA-NEUTRAL long/short equity engine (from the
hedge-fund dump's L2/L4 blueprint, price-derivable subset).

Mechanism
---------
* Factors (causal, sector-relative z-scores):
    - Momentum composite: 12-1 month return (skips the reversal month),
      6-month return, 3m acceleration, 52-week-high proximity.
    - Low-volatility (quality proxy): inverse 60-day realized vol.
    - Composite = 0.6 * momentum + 0.4 * low-vol, ranked WITHIN sector.
* Long book : top-N composite names (strong stocks).
* Short book: bottom-N composite names (weak stocks) -- the beta hedge.
* Beta neutrality: rolling 60-day betas vs SPY; the short book's gross is
  scaled so   net_beta = long_gross*beta_L - short_gross*beta_S  ~ 0.
* Constraints: sector cap per book, quarterly rebalance (configurable),
  10 bps/side costs.

The market's direction should not matter BY CONSTRUCTION: in a crash the
short book's gains offset the long book's losses.

Walk-forward: every score/beta at rebalance date t uses ONLY data <= t; the
new weights earn returns from t+1 onward (one-day implementation lag).

HONEST CAVEATS: current-day large-cap universe => survivorship-inflated long
alpha (see data/fetch_universe.py); no borrow costs/short rebates modeled
(large-cap borrow is cheap but not free); monthly bars of factor data only.

Run:  python strategies/meridian_lite.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UNIVERSE_DIR = ROOT / "data" / "universe"
TRADING_DAYS = 252
OUT_JSON = ROOT / "logs" / "meridian_lite_results.json"

CRISIS_WINDOWS = {
    "2020_covid": ("2020-02-19", "2020-04-30"),
    "2022_bear": ("2022-01-03", "2022-10-14"),
}


@dataclass
class MeridianConfig:
    n_long: int = 20
    n_short: int = 20
    long_gross: float = 0.75          # fraction of equity long
    beta_window: int = 60
    vol_window: int = 60
    sector_cap: int = 5               # max names per sector per book
    short_scale_bounds: tuple = (0.40, 1.10)  # sanity clamp on short gross
    cost_bps_side: float = 10.0       # per side, on traded notional
    mom_weight: float = 0.6
    lowvol_weight: float = 0.4
    warmup_days: int = 300            # need 12m momentum + beta window
    rebalance_freq: str = "ME"        # MONTHLY. Quarterly was A/B-tested 2026-07-02:
                                      # turnover cost saved ~0.4%/yr but momentum
                                      # staleness cost more (carry -0.6% -> -1.2%/yr).
    borrow_annual: float = 0.005      # GC borrow on the short book (mega-caps).
                                      # utils/friction.py rates; shorts are not free.


# ---------------------------------------------------------------------------
# Factor computation (STRICTLY causal: everything uses prices up to `asof`)
# ---------------------------------------------------------------------------
def factor_scores(prices: pd.DataFrame, sectors: dict[str, str], asof_loc: int,
                  cfg: MeridianConfig) -> pd.DataFrame | None:
    """Composite factor score per ticker using data up to (and incl.) row asof_loc."""
    hist = prices.iloc[: asof_loc + 1]
    if len(hist) < cfg.warmup_days:
        return None
    px = hist.iloc[-1]

    r_12_1 = hist.iloc[-21] / hist.iloc[-252] - 1.0        # 12-1 month momentum
    r_6m = px / hist.iloc[-126] - 1.0
    r_3m = px / hist.iloc[-63] - 1.0
    accel = r_3m - (hist.iloc[-63] / hist.iloc[-126] - 1.0)
    hi52 = px / hist.iloc[-252:].max()                     # 52w-high proximity
    vol60 = hist.pct_change().iloc[-cfg.vol_window:].std() * np.sqrt(TRADING_DAYS)

    df = pd.DataFrame({
        "r_12_1": r_12_1, "r_6m": r_6m, "accel": accel, "hi52": hi52,
        "low_vol": -vol60,
    })
    df["sector"] = pd.Series(sectors)
    df = df.dropna()

    def sector_z(col: str) -> pd.Series:
        g = df.groupby("sector")[col]
        return (df[col] - g.transform("mean")) / g.transform("std").replace(0, np.nan)

    mom = (sector_z("r_12_1") + sector_z("r_6m") + sector_z("accel") + sector_z("hi52")) / 4.0
    lv = sector_z("low_vol")
    df["composite"] = cfg.mom_weight * mom + cfg.lowvol_weight * lv
    return df.dropna(subset=["composite"])


def rolling_beta(prices: pd.DataFrame, spy: pd.Series, asof_loc: int, window: int) -> pd.Series:
    """60-day beta vs SPY using data up to asof_loc."""
    rets = prices.iloc[asof_loc - window: asof_loc + 1].pct_change().dropna()
    mkt = spy.iloc[asof_loc - window: asof_loc + 1].pct_change().dropna()
    mkt = mkt.reindex(rets.index)
    var_m = mkt.var()
    if not np.isfinite(var_m) or var_m <= 0:
        return pd.Series(1.0, index=rets.columns)
    return rets.apply(lambda c: c.cov(mkt) / var_m)


def _pick_with_sector_cap(ranked: pd.DataFrame, n: int, cap: int) -> list[str]:
    picked, counts = [], {}
    for t, row in ranked.iterrows():
        if counts.get(row["sector"], 0) >= cap:
            continue
        picked.append(t)
        counts[row["sector"]] = counts.get(row["sector"], 0) + 1
        if len(picked) == n:
            break
    return picked


# ---------------------------------------------------------------------------
# Walk-forward backtest
# ---------------------------------------------------------------------------
def run_backtest(cfg: MeridianConfig | None = None) -> dict:
    cfg = cfg or MeridianConfig()
    prices = pd.read_parquet(UNIVERSE_DIR / "prices.parquet")
    sectors = json.loads((UNIVERSE_DIR / "sectors.json").read_text())
    spy = prices["SPY"]
    stocks = prices[[c for c in prices.columns if c in sectors]]

    daily_ret = stocks.pct_change().fillna(0.0)
    dates = prices.index
    rebal_days = prices.groupby(pd.Grouper(freq=cfg.rebalance_freq)).tail(1).index

    weights = pd.Series(0.0, index=stocks.columns)
    port_ret = pd.Series(0.0, index=dates)
    beta_hist, gross_hist, turnover_total = [], [], 0.0

    for t_loc in range(len(dates)):
        date = dates[t_loc]
        # 1. Earn today's return with YESTERDAY's weights (implementation lag),
        #    minus the GC borrow drag on whatever short book is being carried.
        if t_loc > 0:
            short_gross = float(-weights[weights < 0].sum())
            borrow_drag = short_gross * cfg.borrow_annual / TRADING_DAYS
            port_ret.iloc[t_loc] = float((weights * daily_ret.iloc[t_loc]).sum()) - borrow_drag

        # 2. Rebalance at period-end closes, using data up to today only.
        if date in rebal_days and t_loc >= cfg.warmup_days:
            scores = factor_scores(stocks, sectors, t_loc, cfg)
            if scores is None or len(scores) < (cfg.n_long + cfg.n_short) * 2:
                continue
            betas = rolling_beta(stocks, spy, t_loc, cfg.beta_window)

            longs = _pick_with_sector_cap(
                scores.sort_values("composite", ascending=False), cfg.n_long, cfg.sector_cap)
            shorts = _pick_with_sector_cap(
                scores.sort_values("composite", ascending=True), cfg.n_short, cfg.sector_cap)

            beta_l = float(betas.reindex(longs).clip(0.1, 3.0).mean())
            beta_s = float(betas.reindex(shorts).clip(0.1, 3.0).mean())
            # Scale the short book so net beta ~ 0.
            short_gross = cfg.long_gross * beta_l / beta_s
            short_gross = float(np.clip(short_gross, *cfg.short_scale_bounds))

            new_w = pd.Series(0.0, index=stocks.columns)
            new_w[longs] = cfg.long_gross / len(longs)
            new_w[shorts] = -short_gross / len(shorts)

            turnover = float((new_w - weights).abs().sum())
            cost = turnover * cfg.cost_bps_side / 10_000.0
            port_ret.iloc[t_loc] -= cost
            turnover_total += turnover
            weights = new_w
            beta_hist.append({"date": str(date.date()),
                              "net_beta": cfg.long_gross * beta_l - short_gross * beta_s,
                              "gross": cfg.long_gross + short_gross})
            gross_hist.append(cfg.long_gross + short_gross)

    # ---- results over the traded region ----
    start_loc = cfg.warmup_days
    pr = port_ret.iloc[start_loc:]
    equity = 100_000.0 * (1.0 + pr).cumprod()
    spy_eq = 100_000.0 * (1.0 + spy.pct_change().fillna(0.0).iloc[start_loc:]).cumprod()

    def metrics(eq: pd.Series) -> dict:
        r = eq.pct_change().dropna()
        peak = eq.cummax()
        dd = (peak - eq) / peak
        years = len(eq) / TRADING_DAYS
        cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1.0)
        sd = r.std(ddof=1)
        return {"total_return": float(eq.iloc[-1] / eq.iloc[0] - 1.0), "cagr": cagr,
                "max_dd": float(dd.max()),
                "sharpe": float(r.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
                "calmar": float(cagr / dd.max()) if dd.max() > 1e-9 else 0.0}

    def window_ret(eq: pd.Series, s: str, e: str) -> float | None:
        w = eq.loc[s:e]
        return float(w.iloc[-1] / w.iloc[0] - 1.0) if len(w) > 5 else None

    result = {
        "engine": metrics(equity),
        "spy": metrics(spy_eq),
        "windows": {},
        "avg_net_beta": float(np.mean([b["net_beta"] for b in beta_hist])),
        "max_abs_net_beta": float(np.max(np.abs([b["net_beta"] for b in beta_hist]))),
        "avg_gross": float(np.mean(gross_hist)),
        "annual_turnover": float(turnover_total / (len(pr) / TRADING_DAYS)),
        "n_rebalances": len(beta_hist),
    }
    for name, (s, e) in CRISIS_WINDOWS.items():
        result["windows"][name] = {"engine": window_ret(equity, s, e),
                                   "spy": window_ret(spy_eq, s, e)}
    result["equity_curve"] = {str(d.date()): float(v)
                              for d, v in equity.resample("ME").last().items()}
    result["_daily_returns"] = pr          # pd.Series (stripped before JSON dump)
    return result


def main() -> None:
    res = run_backtest()
    e, s = res["engine"], res["spy"]
    print("MERIDIAN-LITE beta-neutral L/S  (monthly rebal, 10bps/side, beta-scaled short book)")
    print(f"  traded period metrics:")
    print(f"    engine  ret {e['total_return']:>+8.1%}  CAGR {e['cagr']:>+6.1%}  "
          f"maxDD {e['max_dd']:>5.1%}  sharpe {e['sharpe']:>5.2f}  calmar {e['calmar']:>5.2f}")
    print(f"    SPY B&H ret {s['total_return']:>+8.1%}  CAGR {s['cagr']:>+6.1%}  "
          f"maxDD {s['max_dd']:>5.1%}  sharpe {s['sharpe']:>5.2f}  calmar {s['calmar']:>5.2f}")
    print(f"  neutrality: avg net beta {res['avg_net_beta']:+.3f}  "
          f"max |net beta| {res['max_abs_net_beta']:.3f}  avg gross {res['avg_gross']:.2f}x")
    print(f"  turnover {res['annual_turnover']:.1f}x/yr over {res['n_rebalances']} rebalances")
    for name, w in res["windows"].items():
        eng = f"{w['engine']:+.1%}" if w["engine"] is not None else "n/a"
        spx = f"{w['spy']:+.1%}" if w["spy"] is not None else "n/a"
        print(f"  {name:<12} engine {eng:>7}   SPY {spx:>7}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({k: v for k, v in res.items()
                                    if not k.startswith("_")}, indent=2))
    print(f"\nResults -> {OUT_JSON}")


if __name__ == "__main__":
    main()
