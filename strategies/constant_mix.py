"""
strategies/constant_mix.py
==========================
THE CONTROL: static 45% aggressive-LETF sleeve / 55% Meridian-Lite shield,
rebalanced daily. No regime switching. No HMM. Identical sleeves, identical
costs basis, identical period as strategies/regime_blend.py -- so the ONLY
difference vs the "smart" blend is the HMM's timing.

Hypothesis under test: if this dumb blend beats the regime blend, the HMM is
adding drag, not alpha.

Run:  python strategies/constant_mix.py
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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRADING_DAYS = 252
KILL_DD = 0.25
SLEEVE_COST = 0.0005
W_AGG = 0.45                     # static 45% aggressive / 55% shield
OUT_DIR = ROOT / "logs" / "regime_blend"

WINDOWS = {
    "2020_covid": ("2020-02-19", "2020-04-30"),
    "2021_rally": ("2021-01-04", "2021-12-31"),
    "2022_crash": ("2022-01-03", "2022-10-14"),
    "2023_rally": ("2023-01-03", "2023-12-29"),
}


def _metrics(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    peak = equity.cummax()
    dd = (peak - equity) / peak
    years = len(equity) / TRADING_DAYS
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    sd = r.std(ddof=1)
    return {"total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0), "cagr": cagr,
            "max_dd": float(dd.max()),
            "sharpe": float(r.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
            "calmar": float(cagr / dd.max()) if dd.max() > 1e-9 else 0.0,
            "kill_switch_ok": bool(dd.max() <= KILL_DD)}


def _window_ret(eq: pd.Series, s: str, e: str) -> float | None:
    w = eq.loc[s:e]
    return float(w.iloc[-1] / w.iloc[0] - 1.0) if len(w) > 5 else None


def run_pair(symbol: str) -> dict:
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")

    from backtest.backtester import WalkForwardBacktester
    from strategies.meridian_lite import run_backtest as run_meridian

    df = pd.read_parquet(ROOT / "data" / "raw" / f"{symbol.lower()}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    bt = WalkForwardBacktester(n_init=2, random_state=42, satellite_cap=10.0)
    res = bt.run(df, symbol=symbol)
    agg_ret = pd.Series(res.equity, index=res.index).pct_change().fillna(0.0)
    mer_ret = run_meridian()["_daily_returns"]

    idx = agg_ret.index.intersection(mer_ret.index)
    agg_r, mer_r = agg_ret.reindex(idx), mer_ret.reindex(idx).fillna(0.0)

    # Daily-rebalanced constant mix; charge the drift-rebalancing turnover.
    blend_gross = W_AGG * agg_r + (1.0 - W_AGG) * mer_r
    with np.errstate(divide="ignore", invalid="ignore"):
        w_drift = W_AGG * (1.0 + agg_r) / (1.0 + blend_gross)
    drift_turnover = (w_drift - W_AGG).abs().fillna(0.0) * 2.0
    blend_ret = blend_gross - drift_turnover * SLEEVE_COST
    equity = 100_000.0 * (1.0 + blend_ret).cumprod()

    out = {"symbol": symbol, "constant_mix": _metrics(equity), "windows": {},
           "avg_daily_drift_turnover": float(drift_turnover.mean()),
           "period": f"{idx.min():%Y-%m-%d} -> {idx.max():%Y-%m-%d}"}
    for name, (s, e) in WINDOWS.items():
        out["windows"][name] = _window_ret(equity, s, e)
    pd.DataFrame({"equity": equity}).to_csv(OUT_DIR / f"{symbol.lower()}_constant_mix.csv")
    return out


def main() -> None:
    print(f"CONSTANT MIX CONTROL: static {W_AGG:.0%} LETF sleeve / {1-W_AGG:.0%} Meridian-Lite,")
    print("daily rebalanced, drift costs charged. No HMM switching.\n")
    with ProcessPoolExecutor(max_workers=2) as ex:
        fa, fb = ex.submit(run_pair, "TQQQ"), ex.submit(run_pair, "SOXL")
        results = {r["symbol"]: r for r in (fa.result(), fb.result())}

    # --- Battle of the Blends: merge with the saved regime-blend results ---
    regime = {r["symbol"]: r for r in json.loads((OUT_DIR / "results.json").read_text())}

    print("=" * 86)
    print("BATTLE OF THE BLENDS  (identical sleeves, identical period; only the brain differs)")
    print("=" * 86)
    for sym in ("SOXL", "TQQQ"):
        rb, cm = regime[sym]["blend"], results[sym]["constant_mix"]
        print(f"\n  {sym} + Meridian-Lite   ({results[sym]['period']})")
        print(f"    {'arm':<22}{'total ret':>11}{'CAGR':>8}{'maxDD':>8}{'sharpe':>8}{'calmar':>8}{'kill25%':>9}")
        for label, m in (("REGIME BLEND (HMM)", rb), ("CONSTANT MIX (dumb)", cm)):
            print(f"    {label:<22}{m['total_return']:>+11.1%}{m['cagr']:>+8.1%}{m['max_dd']:>8.1%}"
                  f"{m['sharpe']:>8.2f}{m['calmar']:>8.2f}{'PASS' if m['kill_switch_ok'] else 'FAIL':>9}")
        for name in WINDOWS:
            rw = regime[sym]["windows"][name]["blend"]
            cw = results[sym]["windows"][name]
            rs = f"{rw:+.1%}" if rw is not None else "n/a"
            cs = f"{cw:+.1%}" if cw is not None else "n/a"
            print(f"      {name:<12} regime {rs:>8}   constant {cs:>8}")

        verdict = "CONSTANT MIX WINS" if cm["calmar"] > rb["calmar"] else "REGIME BLEND WINS"
        print(f"    -> Calmar verdict: {verdict}  "
              f"(regime {rb['calmar']:.2f} vs constant {cm['calmar']:.2f})")

    (OUT_DIR / "constant_mix_results.json").write_text(json.dumps(list(results.values()), indent=2))
    print(f"\nResults -> {OUT_DIR}")


if __name__ == "__main__":
    main()
