"""
strategies/regime_blend.py
==========================
"Regime-Weighted Blend": the HMM decides how the book is split between the
AGGRESSIVE sleeve (TQQQ/SOXL regime strategy -- the velocity) and the
MERIDIAN-LITE beta-neutral sleeve (the shield).

Blend map (per the spec; mid-vol interpolates between the two anchors):
    Low Vol  (vol_rank <= 1/3):  80% aggressive / 20% neutral
    Mid Vol  (1/3 .. 2/3)     :  45% / 55% (linear midpoint)
    High Vol (>= 2/3) or
    uncertain/flickering      :  10% aggressive / 90% neutral (full shield)

Causality: the regime label at bar t comes from the walk-forward engine's
FILTERED state (past data only), and the blend applies it from bar t+1.
Sleeve re-weighting costs 5 bps on turnover.

The aggressive sleeve runs with the satellite cap disabled INSIDE the sleeve
because the blend itself enforces the satellite doctrine at the book level
(10% aggressive in high vol; 80% only in confirmed calm).

Run:  python strategies/regime_blend.py
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
SLEEVE_COST = 0.0005          # 5 bps on blend-weight turnover
OUT_DIR = ROOT / "logs" / "regime_blend"

WINDOWS = {
    "2018_q4": ("2018-10-01", "2018-12-24"),
    "2020_covid": ("2020-02-19", "2020-04-30"),
    "2021_rally": ("2021-01-04", "2021-12-31"),
    "2022_crash": ("2022-01-03", "2022-10-14"),
    "2023_rally": ("2023-01-03", "2023-12-29"),
}

# vol_rank_frac -> aggressive sleeve weight. Mid-tier REVERTED to 0.45
# (2026-07-02): the 0.20 slash halved returns without fixing DD -- the battery
# proved mid-tier exposure carries the compounding, not just the risk.
W_LOW, W_MID, W_HIGH = 0.80, 0.45, 0.05


def blend_weight(vol_frac: float, uncertain: bool, prob: float = 1.0,
                 conf_gate: float | None = None) -> float:
    """Sleeve weight for the aggressive book.

    conf_gate=None  -> original 3-tier map (low 80/20, mid 45/55, high 10/90).
    conf_gate=0.80  -> CONFIDENCE GUARDRAIL: the racecar (80/20) deploys ONLY
    when the regime is low-vol AND its filtered probability >= gate. Anything
    confusing (prob < gate), mid-vol, high-vol, or uncertain = full shield.
    A confusing market is treated as a dangerous market.
    """
    if conf_gate is not None:
        if (not uncertain) and vol_frac <= 1.0 / 3.0 and prob >= conf_gate:
            return W_LOW
        return W_HIGH
    if uncertain or vol_frac >= 2.0 / 3.0:
        return W_HIGH
    if vol_frac <= 1.0 / 3.0:
        return W_LOW
    return W_MID


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


def run_pair(symbol: str, conf_gate: float | None = None,
             meridian_freq: str | None = None, seed: int = 42,
             ensemble_seeds: list[int] | None = None) -> dict:
    """One blend pair: {symbol} aggressive sleeve + Meridian-Lite shield."""
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")

    from backtest.backtester import WalkForwardBacktester
    from strategies.meridian_lite import MeridianConfig
    from strategies.meridian_lite import run_backtest as run_meridian

    # --- aggressive sleeve: HMM regime strategy on the LETF ---
    df = pd.read_parquet(ROOT / "data" / "raw" / f"{symbol.lower()}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    # n_init=10 ("Stable Brain"): 10 EM restarts per window, keep the best fit.
    # n_init=2 fast mode was the mechanical cause of the seed fragility the
    # robustness battery exposed (different local optima per seed).
    bt = WalkForwardBacktester(n_init=10, random_state=seed, satellite_cap=10.0,
                               ensemble_seeds=ensemble_seeds)
    res = bt.run(df, symbol=symbol)
    agg_eq = pd.Series(res.equity, index=res.index)
    agg_ret = agg_eq.pct_change().fillna(0.0)

    # regime signal (filtered, causal) from the same run
    sig = pd.DataFrame(res.regime_history).set_index("date")
    vol_frac = sig["vol_rank_frac"].reindex(res.index).ffill()
    uncertain = (~sig["confirmed"].astype(bool)).reindex(res.index).ffill().fillna(True)
    prob = sig["probability"].reindex(res.index).ffill().fillna(0.0)

    # --- neutral sleeve ---
    mer_cfg = MeridianConfig(rebalance_freq=meridian_freq) if meridian_freq else None
    mer_ret = run_meridian(mer_cfg)["_daily_returns"]

    # --- align + blend ---
    idx = agg_ret.index.intersection(mer_ret.index)
    agg_r, mer_r = agg_ret.reindex(idx), mer_ret.reindex(idx).fillna(0.0)
    w_agg_signal = pd.Series(
        [blend_weight(v, u, p, conf_gate) for v, u, p in
         zip(vol_frac.reindex(idx), uncertain.reindex(idx), prob.reindex(idx))],
        index=idx)
    w_agg = w_agg_signal.shift(1).ffill().fillna(W_HIGH)     # apply from t+1 (causal)

    turnover = w_agg.diff().abs().fillna(0.0) * 2.0          # both sleeves trade
    blend_ret = w_agg * agg_r + (1.0 - w_agg) * mer_r - turnover * SLEEVE_COST
    equity = 100_000.0 * (1.0 + blend_ret).cumprod()

    out = {"symbol": symbol, "conf_gate": conf_gate, "seed": seed,
           "blend": _metrics(equity),
           "aggressive_only": _metrics(100_000.0 * (1.0 + agg_r).cumprod()),
           "meridian_only": _metrics(100_000.0 * (1.0 + mer_r).cumprod()),
           "windows": {}, "weight_shares": {
               "low": float((w_agg == W_LOW).mean()),
               "mid": float((w_agg == W_MID).mean()),
               "high": float((w_agg == W_HIGH).mean())},
           "regime_switches": int((w_agg.diff().abs() > 1e-9).sum()),
           "period": f"{idx.min():%Y-%m-%d} -> {idx.max():%Y-%m-%d}"}
    for name, (s, e) in WINDOWS.items():
        out["windows"][name] = {
            "blend": _window_ret(equity, s, e),
            "aggressive": _window_ret(100_000.0 * (1.0 + agg_r).cumprod(), s, e)}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"_gate{int(conf_gate * 100)}" if conf_gate is not None else ""
    pd.DataFrame({"equity": equity, "w_aggressive": w_agg}).to_csv(
        OUT_DIR / f"{symbol.lower()}_blend_equity{tag}.csv")
    return out


def _print_pair(r: dict) -> None:
    def row(label: str, m: dict) -> str:
        return (f"    {label:<16} ret {m['total_return']:>+9.1%}  CAGR {m['cagr']:>+7.1%}  "
                f"maxDD {m['max_dd']:>6.1%}  sharpe {m['sharpe']:>5.2f}  calmar {m['calmar']:>5.2f}  "
                f"kill25% {'PASS' if m['kill_switch_ok'] else 'FAIL'}")
    print(f"\n  PAIR: {r['symbol']} + Meridian-Lite   ({r['period']})")
    print(row("BLEND", r["blend"]))
    print(row("aggressive-only", r["aggressive_only"]))
    print(row("meridian-only", r["meridian_only"]))
    ws = r["weight_shares"]
    print(f"    time at {W_LOW:.0%}: {ws['low']:.0%}   {W_MID:.0%}: {ws['mid']:.0%}   "
          f"{W_HIGH:.0%}: {ws['high']:.0%}   switches: {r['regime_switches']}")
    for name, w in r["windows"].items():
        b = f"{w['blend']:+.1%}" if w["blend"] is not None else "n/a"
        a = f"{w['aggressive']:+.1%}" if w["aggressive"] is not None else "n/a"
        print(f"    {name:<12} blend {b:>8}   aggressive-only {a:>8}")


def main_gated(gate: float = 0.80) -> None:
    """Confidence Guardrail validation: SOXL blend with the 80% gate,
    compared before/after against the saved ungated (Sortino brain) run."""
    print(f"CONFIDENCE GUARDRAIL: racecar (80/20) ONLY when low-vol regime prob >= {gate:.0%};")
    print("anything confusing/mid/high/uncertain -> full shield (10/90)\n")
    gated = run_pair("SOXL", conf_gate=gate)

    before_file = OUT_DIR / "results.json"
    before = None
    if before_file.exists():
        before = {r["symbol"]: r for r in json.loads(before_file.read_text())}.get("SOXL")

    def row(label: str, m: dict) -> str:
        return (f"    {label:<26} ret {m['total_return']:>+9.1%}  CAGR {m['cagr']:>+7.1%}  "
                f"maxDD {m['max_dd']:>6.1%}  sharpe {m['sharpe']:>5.2f}  calmar {m['calmar']:>5.2f}  "
                f"kill25% {'PASS' if m['kill_switch_ok'] else 'FAIL'}")

    print("  BEFORE vs AFTER (SOXL + Meridian-Lite, Sortino brain, same seed)")
    if before is not None:
        print(row("BEFORE (no gate)", before["blend"]))
    print(row(f"AFTER  (gate {gate:.0%})", gated["blend"]))
    ws = gated["weight_shares"]
    print(f"    time at {W_LOW:.0%}: {ws['low']:.0%}   {W_HIGH:.0%}: {ws['high']:.0%}   "
          f"switches: {gated['regime_switches']}")
    print("\n  Crisis windows (blend):")
    for name in WINDOWS:
        b = before["windows"][name]["blend"] if before is not None else None
        a = gated["windows"][name]["blend"]
        bs = f"{b:+.1%}" if b is not None else "n/a"
        as_ = f"{a:+.1%}" if a is not None else "n/a"
        print(f"    {name:<12} before {bs:>8}   after {as_:>8}")

    (OUT_DIR / "results_gated.json").write_text(json.dumps(gated, indent=2))
    print(f"\nResults -> {OUT_DIR / 'results_gated.json'}")


def main() -> None:
    print("REGIME-WEIGHTED BLEND: HMM shifts 80/20 <-> 10/90 between LETF sleeve and")
    print("Meridian-Lite shield (mid-vol 45/55; uncertain -> full shield; 5bps sleeve costs)")
    with ProcessPoolExecutor(max_workers=2) as ex:
        fa, fb = ex.submit(run_pair, "TQQQ"), ex.submit(run_pair, "SOXL")
        a, b = fa.result(), fb.result()
    _print_pair(a)
    _print_pair(b)
    (OUT_DIR / "results.json").write_text(json.dumps([a, b], indent=2))
    print(f"\nEquity curves + results -> {OUT_DIR}")


if __name__ == "__main__":
    if "--gate" in sys.argv:
        main_gated(0.80)
    else:
        main()
