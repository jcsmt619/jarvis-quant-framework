"""
hybrid_aggressor.py
===================
"Hybrid Aggressor" experiment: the creator's regime-mapped SCALPER ENTRIES
(QuietRangeScalp / NormalTrendScalp / VolatileBreakoutScalp, long AND short)
grafted onto two exit arms, A/B'd on identical entries:

  fixed  : the creator's shipped exit -- fixed bracket (1.0 ATR stop / 2.0 ATR target)
  runner : our Runner Mode -- bank 50% @ +1.5R, breakeven, trail 2.0x ATR

Walk-forward protocol matches the Step 4 backtester: HMM trained on 252 bars,
traded 126 bars OOS, rolled forward; forward-filtered regimes only (no look-ahead);
identical seed across arms so entries are bit-for-bit identical.

Risk: 1.5% of equity risked to the stop per trade (course rule), no leverage,
slippage 5 bps per side. The 25% kill-switch gate judges every arm.

Run:  python hybrid_aggressor.py
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TRADING_DAYS = 252
KILL_DD = 0.25
RISK_PER_TRADE = 0.015
SLIPPAGE = 0.0005
OUT = ROOT / "logs" / "hybrid_aggressor.json"


# ---------------------------------------------------------------------------
# Indicators (all strictly causal / rolling)
# ---------------------------------------------------------------------------
def scalp_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    out["ema9"] = c.ewm(span=9, adjust=False).mean()
    out["ema21"] = c.ewm(span=21, adjust=False).mean()
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    # ADX(14)
    up_m, dn_m = h.diff(), -l.diff()
    plus_dm = pd.Series(np.where((up_m > dn_m) & (up_m > 0), up_m, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0.0), index=df.index)
    atr_s = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_s
    mdi = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_s
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    out["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
    out["roc5"] = c.pct_change(5)
    tp = (h + l + c) / 3
    out["vwap20"] = (tp * v).rolling(20).sum() / v.rolling(20).sum()   # rolling VWAP proxy
    out["hh20"] = h.rolling(20).max().shift(1)                          # prior 20-bar extremes
    out["ll20"] = l.rolling(20).min().shift(1)
    return out


# ---------------------------------------------------------------------------
# Scalper entries (creator's logic, daily-bar port). Returns (dir, stop_atr) or None.
# ---------------------------------------------------------------------------
def entry_signal(vol_frac: float, row: pd.Series) -> tuple[int, float] | None:
    atr = row["atr"]
    if not np.isfinite(atr) or atr <= 0:
        return None
    if vol_frac <= 1.0 / 3.0:
        # QuietRangeScalp: mean reversion around VWAP
        if not np.isfinite(row["vwap20"]):
            return None
        stretch = (row["close"] - row["vwap20"]) / atr
        if stretch > 1.0 and row["rsi"] > 60:
            return (-1, 1.0)
        if stretch < -1.0 and row["rsi"] < 40:
            return (+1, 1.0)
        return None
    if vol_frac <= 2.0 / 3.0:
        # NormalTrendScalp: momentum with ADX gate
        if not (np.isfinite(row["adx"]) and row["adx"] >= 20):
            return None
        if row["ema9"] > row["ema21"] and row["roc5"] > 0:
            return (+1, 1.0)
        if row["ema9"] < row["ema21"] and row["roc5"] < 0:
            return (-1, 1.0)
        return None
    # VolatileBreakoutScalp: continuation through prior 20-bar extreme, widest stop
    if np.isfinite(row["hh20"]) and row["close"] > row["hh20"]:
        return (+1, 1.5)
    if np.isfinite(row["ll20"]) and row["close"] < row["ll20"]:
        return (-1, 1.5)
    return None


# ---------------------------------------------------------------------------
# Walk-forward simulation of one (symbol, exit_arm)
# ---------------------------------------------------------------------------
def run_arm(symbol: str, exit_arm: str) -> dict:
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")

    from core.hmm_engine import HMMRegimeEngine
    from data.feature_engineering import build_features, log_returns, standardize_features
    from utils.runner_exit import RunnerManager

    df = pd.read_parquet(ROOT / "data" / "raw" / f"{symbol.lower()}.parquet")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    df.columns = [c.lower() for c in df.columns]

    feats_std = standardize_features(build_features(df), 252)
    valid = feats_std.replace([np.inf, -np.inf], np.nan).dropna()
    ind = scalp_indicators(df).reindex(valid.index)
    ret_label = log_returns(df["close"]).reindex(valid.index)
    close = df["close"].reindex(valid.index).to_numpy()
    feat_matrix = valid.to_numpy()
    n = len(valid)

    train_w, test_w, step = 252, 126, 126
    equity = 100000.0
    curve = np.full(n, np.nan)
    trades: list[dict] = []
    runner = RunnerManager(trigger_r=1.5, trail_atr_mult=2.0)

    # position state
    pos_dir, pos_shares, pos_entry, pos_stop, pos_target = 0, 0.0, 0.0, 0.0, 0.0
    banked_events = 0

    def close_frac(price: float, frac: float) -> None:
        nonlocal equity, pos_shares, trades
        qty = pos_shares * frac
        fill = price * (1 - SLIPPAGE * pos_dir)
        pnl = qty * (fill - pos_entry) * pos_dir
        equity += pnl
        trades.append({"pnl": pnl, "r": (fill - pos_entry) * pos_dir / abs(pos_entry - pos_stop_init)
                       if abs(pos_entry - pos_stop_init) > 0 else 0.0})
        pos_shares -= qty

    pos_stop_init = 0.0
    w = 0
    while w + train_w < n:
        is_s, is_e = w, w + train_w
        oos_e = min(is_e + test_w, n)
        eng = HMMRegimeEngine(n_candidates=[3, 4, 5], n_init=2,
                              min_train_bars=train_w, random_state=42)
        try:
            eng.train(valid.iloc[is_s:is_e], returns=ret_label.iloc[is_s:is_e])
        except Exception:
            w += step
            continue
        order = sorted(eng.regime_info.values(), key=lambda ri: ri.expected_volatility)
        rank = {ri.regime_id: i for i, ri in enumerate(order)}
        k = len(order)

        eng.reset_state()
        for row in feat_matrix[is_s:is_e]:
            eng.update(row)

        for j in range(is_e, oos_e):
            st = eng.update(feat_matrix[j])
            price = float(close[j])
            row = ind.iloc[j]
            atr = float(row["atr"]) if np.isfinite(row["atr"]) else 0.0

            # ---- manage open position ----
            if pos_dir != 0:
                if exit_arm == "runner":
                    act = runner.update(price, atr)
                    if act.banked_this_bar:
                        close_frac(price, 0.5)
                        banked_events += 1
                    if act.exited:
                        close_frac(price, 1.0)
                        pos_dir = 0
                        runner.close_trade()
                else:  # fixed bracket: creator's exit
                    hit_stop = (price - pos_stop) * pos_dir <= 0
                    hit_target = (price - pos_target) * pos_dir >= 0
                    if hit_stop or hit_target:
                        close_frac(pos_stop if hit_stop else pos_target, 1.0)
                        pos_dir = 0

            # ---- entries (only when flat, confident, stable) ----
            if pos_dir == 0 and st.probability >= 0.55 and not eng.is_flickering() and atr > 0:
                vol_frac = rank.get(st.state_id, 0) / (k - 1) if k > 1 else 0.0
                sig = entry_signal(vol_frac, row)
                if sig is not None:
                    d, stop_mult = sig
                    stop_dist = stop_mult * atr
                    fill = price * (1 + SLIPPAGE * d)
                    shares = (equity * RISK_PER_TRADE) / stop_dist
                    shares = min(shares, equity / fill)          # no leverage
                    pos_dir, pos_shares, pos_entry = d, shares, fill
                    pos_stop = fill - d * stop_dist
                    pos_stop_init = pos_stop
                    pos_target = fill + d * 2.0 * stop_dist      # fixed arm only
                    if exit_arm == "runner":
                        runner.open_trade(fill, pos_stop, direction=d)

            curve[j] = equity + (pos_shares * (price - pos_entry) * pos_dir if pos_dir != 0 else 0.0)
        w += step

    covered = ~np.isnan(curve)
    eq = curve[covered]
    rets = np.concatenate([[0.0], np.diff(eq) / eq[:-1]])
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    sd = rets.std(ddof=1)
    years = len(eq) / TRADING_DAYS
    cagr = float((eq[-1] / eq[0]) ** (1 / years) - 1.0) if eq[-1] > 0 else -1.0
    wins = [t for t in trades if t["pnl"] > 0]
    rs = [t["r"] for t in trades]
    return {
        "symbol": symbol, "exit_arm": exit_arm,
        "total_return": float(eq[-1] / eq[0] - 1.0), "cagr": cagr,
        "max_dd": float(dd.max()),
        "sharpe": float(rets.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
        "calmar": float(cagr / dd.max()) if dd.max() > 1e-9 else 0.0,
        "n_trades": len(trades), "win_rate": float(len(wins) / len(trades)) if trades else 0.0,
        "best_r": float(max(rs)) if rs else 0.0, "avg_r": float(np.mean(rs)) if rs else 0.0,
        "banked_events": banked_events,
        "kill_switch_ok": bool(dd.max() <= KILL_DD),
    }


def main() -> None:
    jobs = [(s, a) for s in ("TQQQ", "SOXL") for a in ("fixed", "runner")]
    print("HYBRID AGGRESSOR walk-forward: scalper entries x {fixed, runner} exits")
    print(f"risk/trade {RISK_PER_TRADE:.1%}, no leverage, slippage {SLIPPAGE:.2%}/side, "
          f"kill-switch gate {KILL_DD:.0%}\n")

    results = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_arm, s, a) for s, a in jobs]
        for f in futs:
            results.append(f.result())

    for r in sorted(results, key=lambda x: (x["symbol"], x["exit_arm"])):
        print(f"  {r['symbol']:<5} {r['exit_arm']:<7} ret {r['total_return']:>+8.1%}  "
              f"CAGR {r['cagr']:>+7.1%}  maxDD {r['max_dd']:>6.1%}  sharpe {r['sharpe']:>5.2f}  "
              f"calmar {r['calmar']:>5.2f}  trades {r['n_trades']:>4}  win {r['win_rate']:>4.0%}  "
              f"avgR {r['avg_r']:>+5.2f}  bestR {r['best_r']:>+6.2f}  "
              f"kill25% {'PASS' if r['kill_switch_ok'] else 'FAIL'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nResults -> {OUT}")


if __name__ == "__main__":
    main()
