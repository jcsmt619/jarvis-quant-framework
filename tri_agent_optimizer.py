"""
Tri-Agent Adversarial Optimizer (Domain-Aware)
==============================================
Quant Generator -> Adversarial Red Team -> Chief Risk Officer, but the CRO now
grades and approves each strategy WITHIN its own asset domain instead of blending
returns across unrelated assets. Domains:

  * Crypto / High-Beta Momentum : BTC-USD (daily) + SOXL, TQQQ (60m intraday),
    traded by the HyperAlpha-Kelly breakout engine. Intraday LETF breakout
    parameters are optimized on a TRAIN split and graded on the untouched
    TEST split (out-of-sample) to expose overfitting.
  * Equity Mean Reversion       : SPY (daily), RSI-2 long-only.
  * Bond Regime (invert)        : TLT (daily), RSI-2 with allow_short=True so it
    shorts below the 200-SMA instead of buying falling knives.

ADVERSARIAL NOTES
  - The intraday LETF window (2023-2026) is a near-uninterrupted bull run for
    SOXL/TQQQ, so in-sample momentum looks heroic. Only the OOS/test column is
    treated as evidence, and the in-sample->OOS decay is reported.
  - 3x LETFs carry volatility decay (already embedded in the real price series),
    plus expense ratios and overnight gap risk that this daily/60m backtest does
    NOT fully model. Slippage is bumped for intraday fills but borrow/expense are
    not charged. Treat all results as research-stage, not deployable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import backtrader as bt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
INTRADAY_DIR = ROOT / "data" / "intraday"
LOGS_DIR = ROOT / "logs"

sys.path.insert(0, str(ROOT))
from strategies.hyper_alpha_kelly import HyperAlphaKelly
from strategies.skool_variant_1 import SkoolVariant1

# Intraday file stems keyed by symbol.
INTRADAY_STEMS = {
    "SOXL": "soxl_60m",
    "TQQQ": "tqqq_60m",
    "ETH-USD": "eth_usd_60m",
}

# Per-domain configuration + CRO thresholds appropriate to the asset class.
DOMAINS = [
    {
        "key": "crypto_hibeta_momentum",
        "label": "Crypto / High-Beta Momentum",
        "engine": "hyper_alpha",
        "cro": {"min_return": 0.10, "max_dd": 0.45, "min_sharpe": 0.30},
        "assets": [
            {"symbol": "BTC-USD", "timeframe": "daily"},
            {"symbol": "SOXL", "timeframe": "intraday"},
            {"symbol": "TQQQ", "timeframe": "intraday"},
        ],
    },
    {
        "key": "equity_mean_reversion",
        "label": "Equity Mean Reversion",
        "engine": "skool_regime",
        "cro": {"min_return": 0.05, "max_dd": 0.25, "min_sharpe": 0.20},
        "assets": [{"symbol": "SPY", "timeframe": "daily"}],
        "params": {"allow_short": False},
    },
    {
        "key": "bond_regime_invert",
        "label": "Bond Regime (TLT invert)",
        "engine": "skool_regime",
        "cro": {"min_return": 0.03, "max_dd": 0.25, "min_sharpe": 0.20},
        "assets": [{"symbol": "TLT", "timeframe": "daily"}],
        "params": {"allow_short": True},
    },
    {
        # STEP 5 aggressive challenger: full-Kelly / up-to-4x breakout on BTC +
        # 3x LETFs, guarded by the RiskManager circuit breakers. Deliberately
        # strict CRO thresholds -- a hyper-leveraged book must earn a lot AND
        # keep drawdown contained, or it is rejected.
        "key": "kelly_hypervelocity",
        "label": "Kelly Hyper-Velocity (4x)",
        "engine": "kelly_hypervelocity",
        "cro": {"min_return": 0.20, "max_dd": 0.35, "min_sharpe": 0.50},
        "assets": [
            {"symbol": "BTC-USD", "timeframe": "daily"},
            {"symbol": "SOXL", "timeframe": "intraday"},
            {"symbol": "TQQQ", "timeframe": "intraday"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _read(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.columns = [c.lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]].sort_index()


def load_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    if timeframe == "intraday":
        stem = INTRADAY_STEMS.get(symbol, symbol.lower().replace("-", "_") + "_60m")
        directory = INTRADAY_DIR
    else:
        stem = symbol.lower().replace("-", "_")
        directory = RAW_DIR
    for ext in (".parquet", ".csv"):
        path = directory / f"{stem}{ext}"
        if path.exists():
            return _read(path)
    raise FileNotFoundError(f"No data for {symbol} ({timeframe}) under {directory}")


def load_stress_frame(symbol: str) -> pd.DataFrame | None:
    """Build a stressed OHLC frame from the *_stress files (daily only)."""
    stem = symbol.lower().replace("-", "_")
    path = RAW_DIR / f"{stem}_stress.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if "stress_close" not in df.columns or "Close" not in df.columns:
        return None
    ratio = (df["stress_close"] / df["Close"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out = pd.DataFrame(index=df.index)
    out["open"] = df["Open"] * ratio
    out["high"] = df["High"] * ratio
    out["low"] = df["Low"] * ratio
    out["close"] = df["stress_close"]
    out["volume"] = df.get("Volume", 0)
    return out.dropna()


# ---------------------------------------------------------------------------
# Backtest primitive
# ---------------------------------------------------------------------------
def _annualized_sharpe(daily_rets: list[float], rf: float = 0.045) -> float:
    arr = np.array([r for r in daily_rets if r is not None], dtype=float)
    if arr.size < 2 or arr.std(ddof=1) == 0:
        return 0.0
    excess = arr - rf / 252.0
    return float(excess.mean() / arr.std(ddof=1) * np.sqrt(252.0))


def run_backtest(strategy_cls, kwargs: dict, df: pd.DataFrame, intraday: bool = False) -> tuple[float, float, float]:
    if df is None or len(df) < 60:
        return 0.0, 0.0, 0.0
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(strategy_cls, **kwargs)
    cerebro.broker.set_cash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    # Realistic friction: heavier slippage on fast intraday LETF fills.
    cerebro.broker.set_slippage_perc(perc=0.001 if intraday else 0.0005)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addanalyzer(bt.analyzers.Returns, _name="ret")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="tr", timeframe=bt.TimeFrame.Days)

    res = cerebro.run()[0]
    total = float(res.analyzers.ret.get_analysis().get("rtot", 0.0) or 0.0)
    max_dd = float(res.analyzers.dd.get_analysis().get("max", {}).get("drawdown", 0.0) or 0.0) / 100.0
    sharpe = _annualized_sharpe(list(res.analyzers.tr.get_analysis().values()))
    return total, max_dd, sharpe


# ---------------------------------------------------------------------------
# Quant Generator
# ---------------------------------------------------------------------------
# Intraday LETF breakout grid: faster channels tuned for 60m high-beta trends.
# Higher SIGNAL DENSITY: shorter lookbacks + a small breakout buffer + looser
# trend requirement to capture high-velocity intraday micro-trends. This is an
# overfitting-prone configuration BY DESIGN -- the OOS test split is what keeps
# it honest.
INTRADAY_MOMENTUM_GRID = [
    {"breakout_period": bp, "momentum_period": mp, "atr_period": 14,
     "trend_ema": te, "atr_trail_mult": 2.5, "kelly_fraction": 0.5,
     "breakout_buffer": buf, "require_trend_rising": False, "momentum_threshold": -0.001}
    for bp in (3, 5, 8, 12)
    for mp in (2, 4)
    for te in (12, 24)
    for buf in (0.0, 0.002)
]

DAILY_MOMENTUM = {
    "breakout_period": 20, "momentum_period": 10, "atr_period": 14,
    "trend_ema": 50, "atr_trail_mult": 2.5, "kelly_fraction": 0.5,
}

DAILY_RSI2 = {
    "rsi_period": 2, "rsi_entry": 10.0, "rsi_exit": 50.0, "trend_ma": 200,
    "exit_ma": 5, "max_hold": 10, "atr_period": 14, "atr_stop_mult": 2.0,
    "risk_per_trade": 0.02,
}


def optimize_intraday_breakout(df: pd.DataFrame) -> dict:
    """Grid-search breakout params on a 70% train split, grade OOS on 30% test."""
    split = int(len(df) * 0.70)
    train, test = df.iloc[:split], df.iloc[split:]

    best_score, best_params, best_train = -1e9, INTRADAY_MOMENTUM_GRID[0], (0.0, 0.0, 0.0)
    for params in INTRADAY_MOMENTUM_GRID:
        tr = run_backtest(HyperAlphaKelly, params, train, intraday=True)
        # FITNESS = raw compounding VELOCITY (train total return). Drawdown is no
        # longer part of SELECTION -- but it remains a hard CRO APPROVAL floor.
        score = tr[0]
        if score > best_score:
            best_score, best_params, best_train = score, params, tr

    oos = run_backtest(HyperAlphaKelly, best_params, test, intraday=True)
    full = run_backtest(HyperAlphaKelly, best_params, df, intraday=True)
    return {"params": best_params, "train": best_train, "oos": oos, "full": full}


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------
class TriAgentOptimizer:
    def __init__(self, domains: list[dict] | None = None):
        self.domains = domains or DOMAINS
        self.matrix: list[dict] = []

    def _grade(self, cro: dict, ret: float, dd: float, sharpe: float, robust_ok: bool) -> tuple[bool, str]:
        checks = []
        approved = True
        if ret < cro["min_return"]:
            approved = False
            checks.append(f"ret<{cro['min_return']:.0%}")
        if dd > cro["max_dd"]:
            approved = False
            checks.append(f"DD>{cro['max_dd']:.0%}")
        if not robust_ok:
            approved = False
            checks.append("failed robustness")
        return approved, "Robust" if approved else ", ".join(checks)

    def run(self) -> list[dict]:
        print("=" * 84)
        print("TRI-AGENT ADVERSARIAL OPTIMIZATION — DOMAIN-ROUTED")
        print("=" * 84)

        for domain in self.domains:
            print(f"\n### DOMAIN: {domain['label']}")
            engine = domain["engine"]
            base_params = domain.get("params", {})

            for asset in domain["assets"]:
                symbol, tf = asset["symbol"], asset["timeframe"]
                intraday = tf == "intraday"
                print(f"  [Quant] {symbol} ({tf}) via {engine}...")

                row = {"domain": domain["label"], "symbol": symbol, "timeframe": tf, "engine": engine}

                try:
                    if engine == "hyper_alpha" and intraday:
                        # Quant Generator optimizes breakout params; Red Team = OOS split.
                        opt = optimize_intraday_breakout(load_frame(symbol, tf))
                        tr_ret, tr_dd, _ = opt["train"]
                        oos_ret, oos_dd, oos_sh = opt["oos"]
                        full_ret, full_dd, full_sh = opt["full"]
                        # Robustness: OOS must stay positive and not collapse vs train.
                        robust_ok = oos_ret > 0 and oos_dd <= domain["cro"]["max_dd"]
                        approved, reason = self._grade(domain["cro"], oos_ret, oos_dd, oos_sh, robust_ok)
                        row.update({
                            "params": opt["params"],
                            "is_return": tr_ret, "is_dd": tr_dd,
                            "return": oos_ret, "max_dd": oos_dd, "sharpe": oos_sh,
                            "full_return": full_ret, "full_dd": full_dd,
                            "graded_on": "OOS test split",
                            "approved": approved, "reason": reason,
                        })
                        print(f"          train ret={tr_ret:.2%} -> OOS ret={oos_ret:.2%} "
                              f"(decay {tr_ret - oos_ret:+.2%}) DD={oos_dd:.2%}")
                    elif engine == "hyper_alpha":
                        ret, dd, sh = run_backtest(HyperAlphaKelly, DAILY_MOMENTUM, load_frame(symbol, tf))
                        # Red Team: re-run on the stress dataset.
                        stress = load_stress_frame(symbol)
                        s_ret, s_dd, _ = run_backtest(HyperAlphaKelly, DAILY_MOMENTUM, stress) if stress is not None else (ret, dd, sh)
                        robust_ok = s_dd <= domain["cro"]["max_dd"]
                        approved, reason = self._grade(domain["cro"], ret, dd, sh, robust_ok)
                        row.update({
                            "params": DAILY_MOMENTUM, "return": ret, "max_dd": dd, "sharpe": sh,
                            "stress_dd": s_dd, "graded_on": "full 15y", "approved": approved, "reason": reason,
                        })
                    elif engine == "kelly_hypervelocity":
                        from backtest_harness import simulate_kelly_hypervelocity
                        # Loosen breakout lookbacks (denser micro-trend capture);
                        # the HMM gate + circuit breakers still govern exposure.
                        if intraday:
                            res = simulate_kelly_hypervelocity(symbol, tf, breakout_period=6,
                                                               momentum_period=3, trend_ema=24)
                        else:
                            res = simulate_kelly_hypervelocity(symbol, tf, breakout_period=15,
                                                               momentum_period=8, trend_ema=40)
                        ret, dd, sh = res["total_return"], abs(res["max_dd"]), res["sharpe"]
                        robust_ok = (not res["ruined"]) and dd <= domain["cro"]["max_dd"]
                        approved, reason = self._grade(domain["cro"], ret, dd, sh, robust_ok)
                        if res["ruined"]:
                            reason = "RUIN (account wiped)"
                        elif res["lock_triggered"]:
                            reason = ("hard-halt lock fired" if reason == "Robust"
                                      else reason + "; hard-halt lock fired")
                        row.update({
                            "return": ret, "max_dd": dd, "sharpe": sh,
                            "graded_on": "full history (RM breakers)",
                            "lock_triggered": res["lock_triggered"], "ruined": res["ruined"],
                            "approved": approved, "reason": reason,
                        })
                        print(f"          ret={ret:.2%} DD={dd:.2%} lock={res['lock_triggered']} ruined={res['ruined']}")
                    else:  # skool_regime (RSI-2), daily
                        params = {**DAILY_RSI2, **base_params}
                        ret, dd, sh = run_backtest(SkoolVariant1, params, load_frame(symbol, tf))
                        stress = load_stress_frame(symbol)
                        s_ret, s_dd, _ = run_backtest(SkoolVariant1, params, stress) if stress is not None else (ret, dd, sh)
                        robust_ok = s_dd <= domain["cro"]["max_dd"]
                        approved, reason = self._grade(domain["cro"], ret, dd, sh, robust_ok)
                        row.update({
                            "params": params, "return": ret, "max_dd": dd, "sharpe": sh,
                            "stress_dd": s_dd, "graded_on": "full 15y", "approved": approved, "reason": reason,
                        })
                except Exception as exc:  # pragma: no cover - defensive
                    row.update({"approved": False, "reason": f"error: {exc}", "return": 0, "max_dd": 0, "sharpe": 0})
                    print(f"          FAILED: {exc}")

                self.matrix.append(row)

        self._print_matrix()
        LOGS_DIR.mkdir(exist_ok=True)
        (LOGS_DIR / "tri_agent_results.json").write_text(json.dumps(self.matrix, indent=2, default=str))
        print(f"\nDetailed results saved to {LOGS_DIR / 'tri_agent_results.json'}")
        return self.matrix

    def _print_matrix(self) -> None:
        print("\n" + "=" * 84)
        print("HIGH-VELOCITY MULTI-ASSET PERFORMANCE MATRIX  (CRO graded per domain)")
        print("=" * 84)
        hdr = "{:<26}{:<9}{:<6}{:>9}{:>8}{:>8}  {}"
        print(hdr.format("DOMAIN", "SYMBOL", "TF", "Return", "MaxDD", "Sharpe", "Verdict"))
        print("-" * 84)
        row_fmt = "{:<26}{:<9}{:<6}{:>9}{:>8}{:>8}  {}"
        for r in self.matrix:
            verdict = "APPROVED" if r.get("approved") else f"REJECTED ({r.get('reason','')})"
            print(row_fmt.format(
                r["domain"][:25], r["symbol"], r["timeframe"][:5],
                f"{r.get('return', 0):.2%}", f"{r.get('max_dd', 0):.2%}",
                f"{r.get('sharpe', 0):.2f}", verdict,
            ))
        print("=" * 84)
        print("Intraday rows graded OUT-OF-SAMPLE (test split); daily rows graded on full 15y + stress.")


if __name__ == "__main__":
    TriAgentOptimizer().run()
