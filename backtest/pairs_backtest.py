"""
backtest/pairs_backtest.py
==========================
Walk-forward pairs (stat-arb) backtester with institutional friction.
Integrates the pairs_scanner signal with utils.friction costs -- honestly.

Corrections vs the draft this was adapted from:
  * Hedge ratio is a ROLLING walk-forward OLS (trailing window, applied from
    t+1) -- the scanner's full-sample OLS would leak the future relationship.
  * Signals decided at bar t are FILLED at bar t+1 close (1-bar lag).
  * Spread-replication sizing: shares_B = hedge_ratio * shares_A (the draft's
    dollar-split sizing didn't replicate the spread being traded).
  * ATR proxy from price CHANGES (rolling mean |diff|), not price-level std.
  * Mark-to-market equity every bar -> real max DD / Sharpe, not just final cash.
  * Borrow drag accrues on the CURRENT short-leg value (HTB rate), not the
    entry-day value.
  * Added the band-snap stop: |z| > z_stop means the rubber band is breaking;
    exit, don't pray.

Run:  python backtest/pairs_backtest.py --a V --b MA
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.friction import FrictionConfig, InstitutionalFrictionEngine

TRADING_DAYS = 252


@dataclass
class PairConfig:
    ols_window: int = 252          # trailing window for the rolling hedge ratio
    z_window: int = 21             # rolling z-score window
    z_entry: float = 2.0
    z_exit: float = 0.2
    z_stop: float = 3.5            # band-snap stop: co-integration is breaking
    max_hold_days: int = 21
    gross_per_trade: float = 0.90  # fraction of equity deployed across both legs
    adv_shares: float = 5_000_000  # conservative ADV assumption per leg
    htb_borrow: bool = True        # short legs treated as hard-to-borrow
    # Adaptive Kelly sizing ("ArbitrageLab" gauntlet): size each trade from the
    # pair's REALIZED rolling stats. Emergent property: enough losses drive the
    # Kelly fraction negative and the strategy SHUTS ITSELF OFF.
    kelly_sizing: bool = False
    kelly_fraction: float = 0.5    # half-Kelly
    kelly_cap: float = 0.20        # never > 20% of equity on one pair
    kelly_warmup: float = 0.10     # allocation before enough trades exist
    kelly_min_trades: int = 10


@dataclass
class PairResult:
    equity: pd.Series
    trades: list[dict]
    metrics: dict
    friction_paid: float
    borrow_paid: float


# ---------------------------------------------------------------------------
def rolling_signals(pa: pd.Series, pb: pd.Series, cfg: PairConfig) -> pd.DataFrame:
    """Causal hedge ratio + spread z-score. Everything at t uses data <= t,
    and the CALLER acts on it at t+1."""
    df = pd.DataFrame({"a": pa, "b": pb}).dropna()
    # Rolling OLS slope: beta = cov(a,b)/var(b) over trailing window.
    cov = df["a"].rolling(cfg.ols_window).cov(df["b"])
    var = df["b"].rolling(cfg.ols_window).var()
    df["hedge"] = (cov / var.replace(0.0, np.nan))
    df["spread"] = df["a"] - df["hedge"] * df["b"]
    mu = df["spread"].rolling(cfg.z_window).mean()
    sd = df["spread"].rolling(cfg.z_window).std()
    # Degenerate-spread guard: when the hedge is near-perfect the spread is
    # floating-point noise and z = noise/noise emits spurious +/-2 sigma
    # "signals". Require spread vol to be economically meaningful (>=1bp of
    # price A) before trusting a z-score.
    sd_floor = 1e-4 * df["a"]
    sd = sd.where(sd > sd_floor)
    df["z"] = (df["spread"] - mu) / sd
    # ATR proxy per leg: rolling mean absolute daily change (causal).
    df["atr_a"] = df["a"].diff().abs().rolling(21).mean()
    df["atr_b"] = df["b"].diff().abs().rolling(21).mean()
    return df.dropna()


def backtest_pair(pa: pd.Series, pb: pd.Series, cfg: PairConfig | None = None,
                  base_capital: float = 100_000.0,
                  friction: InstitutionalFrictionEngine | None = None) -> PairResult:
    cfg = cfg or PairConfig()
    eng = friction or InstitutionalFrictionEngine(FrictionConfig(htb_borrow_annual=0.12))
    sig = rolling_signals(pa, pb, cfg)

    cash = base_capital
    equity = pd.Series(np.nan, index=sig.index)
    trades: list[dict] = []
    friction_paid = borrow_paid = 0.0

    pos = None   # dict(dir, sh_a, sh_b, ea, eb, entry_idx, days)
    pending = None  # signal decided at t-1, filled at t

    def leg_cost(price, shares, atr) -> float:
        return eng.execution_cost(price, abs(shares), atr, cfg.adv_shares)

    def kelly_alloc() -> float:
        """Allocation fraction from REALIZED closed trades (guards: empty wins
        or losses -> warmup; negative Kelly -> 0 = adaptive shutdown)."""
        pnls = [t_["pnl"] for t_ in trades]
        if len(pnls) < cfg.kelly_min_trades:
            return cfg.kelly_warmup
        wins_ = [p for p in pnls if p > 0]
        losses_ = [p for p in pnls if p <= 0]
        if not wins_ or not losses_:
            return cfg.kelly_warmup
        w = len(wins_) / len(pnls)
        r = float(np.mean(wins_) / abs(np.mean(losses_)))
        if r <= 0:
            return 0.0
        k = (w - (1.0 - w) / r) * cfg.kelly_fraction
        return float(np.clip(k, 0.0, cfg.kelly_cap))

    for t in range(len(sig)):
        row = sig.iloc[t]
        a, b = float(row["a"]), float(row["b"])

        # ---- 1. fill the order decided YESTERDAY ----
        if pending is not None:
            action, direction = pending
            pending = None
            if action == "enter" and pos is None:
                mtm = cash
                frac = kelly_alloc() if cfg.kelly_sizing else cfg.gross_per_trade
                if frac <= 0:
                    pass                                   # Kelly shutdown: no edge, no trade
                else:
                    alloc = mtm * frac / 2.0
                    sh_a = alloc / a
                    sh_b = float(row["hedge"]) * sh_a          # spread replication
                    c = leg_cost(a, sh_a, row["atr_a"]) + leg_cost(b, sh_b, row["atr_b"])
                    cash -= c
                    friction_paid += c
                    pos = {"dir": direction, "sh_a": sh_a, "sh_b": sh_b,
                           "ea": a, "eb": b, "days": 0, "entry_date": sig.index[t]}
            elif action == "exit" and pos is not None:
                d = 1.0 if pos["dir"] == "LONG_A" else -1.0
                pnl = d * (pos["sh_a"] * (a - pos["ea"]) - pos["sh_b"] * (b - pos["eb"]))
                c = leg_cost(a, pos["sh_a"], row["atr_a"]) + leg_cost(b, pos["sh_b"], row["atr_b"])
                cash += pnl - c
                friction_paid += c
                trades.append({"entry": pos["entry_date"], "exit": sig.index[t],
                               "dir": pos["dir"], "days": pos["days"],
                               "pnl": pnl - c, "cost": c})
                pos = None

        # ---- 2. accrue borrow on the CURRENT short leg value ----
        if pos is not None:
            pos["days"] += 1
            short_val = (pos["sh_b"] * b) if pos["dir"] == "LONG_A" else (pos["sh_a"] * a)
            drag = eng.short_borrow_cost(short_val, 1, hard_to_borrow=cfg.htb_borrow)
            cash -= drag
            borrow_paid += drag

        # ---- 3. decide (acted on tomorrow) ----
        z = float(row["z"])
        if pos is None:
            if z < -cfg.z_entry:
                pending = ("enter", "LONG_A")
            elif z > cfg.z_entry:
                pending = ("enter", "SHORT_A")
        else:
            snapped = abs(z) > cfg.z_stop
            reverted = abs(z) < cfg.z_exit
            timed_out = pos["days"] >= cfg.max_hold_days
            if snapped or reverted or timed_out:
                pending = ("exit", None)

        # ---- 4. mark to market ----
        mtm = cash
        if pos is not None:
            d = 1.0 if pos["dir"] == "LONG_A" else -1.0
            mtm += d * (pos["sh_a"] * (a - pos["ea"]) - pos["sh_b"] * (b - pos["eb"]))
        equity.iloc[t] = mtm

    equity = equity.dropna()
    if len(equity) < 2:
        # Degenerate pair (e.g. exactly proportional -> constant spread -> no z).
        return PairResult(equity=equity, trades=trades,
                          metrics={"total_return": 0.0, "cagr": 0.0, "max_dd": 0.0,
                                   "sharpe": 0.0, "n_trades": 0, "win_rate": 0.0,
                                   "avg_hold_days": 0.0, "friction_drag_pct": 0.0,
                                   "borrow_drag_pct": 0.0},
                          friction_paid=friction_paid, borrow_paid=borrow_paid)
    r = equity.pct_change().dropna()
    peak = equity.cummax()
    dd = (peak - equity) / peak
    years = len(equity) / TRADING_DAYS
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    sd = r.std(ddof=1)
    wins = [t_ for t_ in trades if t_["pnl"] > 0]
    metrics = {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
        "cagr": cagr, "max_dd": float(dd.max()) if len(dd) else 0.0,
        "sharpe": float(r.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0,
        "n_trades": len(trades),
        "win_rate": float(len(wins) / len(trades)) if trades else 0.0,
        "avg_hold_days": float(np.mean([t_["days"] for t_ in trades])) if trades else 0.0,
        "friction_drag_pct": friction_paid / base_capital,
        "borrow_drag_pct": borrow_paid / base_capital,
    }
    return PairResult(equity=equity, trades=trades, metrics=metrics,
                      friction_paid=friction_paid, borrow_paid=borrow_paid)


# ---------------------------------------------------------------------------
# Fund-mandate verdict ("the gauntlet"): three gates, ALL must pass.
# ---------------------------------------------------------------------------
def fund_verdict(res: PairResult, max_dd_limit: float = 0.20,
                 ruin_threshold: float = 0.05, ruin_dd: float = 0.20,
                 base_capital: float = 100_000.0, n_sims: int = 2000,
                 seed: int = 42) -> dict:
    """Gate 1: max MTM drawdown <= limit. Gate 2: positive net expectancy.
    Gate 3: bootstrap risk-of-ruin <= threshold (the gate the draft declared
    but never implemented). Drawdown uses the MARKED-TO-MARKET equity curve --
    a cash-only curve hides open losses and makes a DD gate meaningless."""
    reasons = []
    if res.metrics["max_dd"] > max_dd_limit:
        reasons.append(f"max MTM drawdown {res.metrics['max_dd']:.1%} > {max_dd_limit:.0%} mandate")
    if res.metrics["cagr"] <= 0:
        reasons.append("negative expectancy net of friction")

    ruin_prob = 0.0
    pnls = np.array([t_["pnl"] for t_ in res.trades], dtype=float)
    if len(pnls) >= 10:
        rets = pnls / base_capital
        rng = np.random.default_rng(seed)
        draws = rng.choice(rets, size=(n_sims, max(len(rets), 100)), replace=True)
        eq = np.cumprod(1.0 + draws, axis=1)
        dd = 1.0 - eq / np.maximum.accumulate(eq, axis=1)
        ruin_prob = float((dd.max(axis=1) >= ruin_dd).mean())
        if ruin_prob > ruin_threshold:
            reasons.append(f"risk of ruin {ruin_prob:.1%} > {ruin_threshold:.0%} tolerance")
    elif len(pnls) > 0:
        reasons.append(f"only {len(pnls)} trades -- too few to certify (needs 10+)")

    return {"status": "FUNDABLE" if not reasons else "DEAD",
            "fail_reasons": reasons, "risk_of_ruin": ruin_prob}


# ---------------------------------------------------------------------------
def main() -> None:
    import yfinance as yf

    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="V")
    ap.add_argument("--b", default="MA")
    ap.add_argument("--years", type=int, default=8)
    ap.add_argument("--kelly", action="store_true",
                    help="adaptive half-Kelly sizing from realized pair stats")
    args = ap.parse_args()

    raw = yf.download([args.a, args.b], period=f"{args.years}y",
                      auto_adjust=True, progress=False)["Close"].dropna()
    cfg = PairConfig(kelly_sizing=args.kelly)
    res = backtest_pair(raw[args.a], raw[args.b], cfg)
    gross = res.metrics["total_return"] + (res.friction_paid + res.borrow_paid) / 100_000.0

    m = res.metrics
    mode = "adaptive half-Kelly" if args.kelly else f"fixed {cfg.gross_per_trade:.0%} gross"
    print(f"PAIRS BACKTEST {args.a}/{args.b}  ({res.equity.index[0]:%Y-%m-%d} -> "
          f"{res.equity.index[-1]:%Y-%m-%d}, walk-forward hedge ratio, t+1 fills, {mode})")
    print(f"  net ret {m['total_return']:>+8.1%}   CAGR {m['cagr']:>+6.1%}   "
          f"maxDD {m['max_dd']:>6.1%}   sharpe {m['sharpe']:>5.2f}")
    print(f"  trades {m['n_trades']}   win {m['win_rate']:.0%}   avg hold {m['avg_hold_days']:.1f}d")
    print(f"  friction paid ${res.friction_paid:,.0f}   borrow paid ${res.borrow_paid:,.0f}   "
          f"(~{(res.friction_paid + res.borrow_paid) / 100_000.0:+.1%} of capital; "
          f"gross-of-cost return would be ~{gross:+.1%})")

    v = fund_verdict(res)
    print(f"  VERDICT: {v['status']}"
          + (f" -- {'; '.join(v['fail_reasons'])}" if v["fail_reasons"] else "")
          + (f"   (risk of ruin {v['risk_of_ruin']:.1%})" if v["risk_of_ruin"] else ""))


if __name__ == "__main__":
    main()
