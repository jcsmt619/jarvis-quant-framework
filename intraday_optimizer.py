"""
Intraday Tri-Agent Optimizer (Hyper-Alpha, Full Kelly, 5x Leverage)
===================================================================
Runs the three-perspective loop (Quant Generator -> Adversarial Red Team ->
Chief Risk Officer) over the HyperAlphaKelly strategy on intraday high-velocity
data with FULL Kelly sizing and up to 5x leverage.

Adversarial realism baked in (per quant-research guidelines):
    - Realistic friction: per-asset commissions + percentage slippage.
    - Leverage permitted (checksubmit disabled) so 5x exposure is actually taken.
    - LIQUIDATION / RUIN DETECTION: a value analyzer flags any path where equity
      collapses below the maintenance threshold; such runs are reported as BLOWN UP
      rather than being silently averaged into a rosy number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import backtrader as bt
import pandas as pd

ROOT = Path(__file__).resolve().parent
INTRADAY_DIR = ROOT / "data" / "intraday"
LOGS_DIR = ROOT / "logs"

sys.path.insert(0, str(ROOT))
from strategies.hyper_alpha_kelly import HyperAlphaKelly

# Flushed progress logging so long runs can be monitored via the file.
LOGS_DIR.mkdir(parents=True, exist_ok=True)
_PROGRESS = open(LOGS_DIR / "intraday_progress.log", "w", buffering=1)


def log(msg: str) -> None:
    print(msg, flush=True)
    _PROGRESS.write(msg + "\n")
    _PROGRESS.flush()

# --- Friction model (per-asset, realistic for intraday high-beta) ---
# Crypto: ~10 bps taker fee; leveraged ETFs: ~2 bps commission but wider intraday spread.
FRICTION = {
    "btc_usd": {"commission": 0.0010, "slippage": 0.0010},
    "eth_usd": {"commission": 0.0010, "slippage": 0.0012},
    "soxl":    {"commission": 0.0002, "slippage": 0.0008},
    "tqqq":    {"commission": 0.0002, "slippage": 0.0006},
}

INTERVAL = "60m"
STARTING_CASH = 100_000.0
# 5x leverage => a ~20% adverse move destroys the account. Flag ruin below this.
LIQUIDATION_EQUITY = STARTING_CASH * 0.20


class ValueTracker(bt.Analyzer):
    """Tracks min equity and detects liquidation/ruin along the path."""

    def start(self):
        self.min_value = float("inf")
        self.max_value = float("-inf")
        self.blown_up = False

    def next(self):
        v = self.strategy.broker.getvalue()
        self.min_value = min(self.min_value, v)
        self.max_value = max(self.max_value, v)
        if v <= LIQUIDATION_EQUITY:
            self.blown_up = True

    def get_analysis(self):
        return {
            "min_value": self.min_value,
            "max_value": self.max_value,
            "blown_up": self.blown_up,
        }


class IntradayHyperAlphaOptimizer:
    def __init__(self, interval: str = INTERVAL):
        self.interval = interval
        self.assets = self._discover_assets()

    def _discover_assets(self) -> dict[str, Path]:
        assets = {}
        for stem in FRICTION.keys():
            path = INTRADAY_DIR / f"{stem}_{self.interval}.csv"
            if path.exists():
                assets[stem] = path
        return assets

    def load_data(self, stem: str) -> pd.DataFrame:
        df = pd.read_csv(self.assets[stem], parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].sort_index()
        df = df.dropna()
        return df

    # ------------------------------------------------------------------
    # QUANT GENERATOR
    # ------------------------------------------------------------------
    def quant_generator(self) -> list[dict]:
        print("=== QUANT GENERATOR (Intraday, Full Kelly, 5x) ===")
        proposals = [
            {"name": "Intraday-Fast",     "breakout_period": 20, "momentum_period": 8,  "atr_period": 14, "trend_ema": 40, "kelly_fraction": 1.0},
            {"name": "Intraday-Turbo",    "breakout_period": 12, "momentum_period": 5,  "atr_period": 10, "trend_ema": 30, "kelly_fraction": 1.0},
            {"name": "Intraday-Scalp",    "breakout_period": 8,  "momentum_period": 4,  "atr_period": 8,  "trend_ema": 20, "kelly_fraction": 1.0},
            {"name": "Intraday-Swing",    "breakout_period": 30, "momentum_period": 12, "atr_period": 20, "trend_ema": 60, "kelly_fraction": 1.0},
            {"name": "Intraday-Momentum", "breakout_period": 16, "momentum_period": 6,  "atr_period": 12, "trend_ema": 34, "kelly_fraction": 1.0},
        ]
        print(f"Generated {len(proposals)} intraday proposals")
        return proposals

    # ------------------------------------------------------------------
    # ADVERSARIAL RED TEAM
    # ------------------------------------------------------------------
    def red_team(self, proposals: list[dict]) -> list[dict]:
        log("\n=== ADVERSARIAL RED TEAM (friction + liquidation) ===")
        results = []
        for proposal in proposals:
            log(f"  Testing {proposal['name']}...")
            per_asset = {}
            any_blowup = False
            returns, drawdowns = [], []
            for stem in self.assets:
                try:
                    metrics = self._backtest(proposal, stem)
                except Exception as e:
                    log(f"    {stem}: FAILED {e}")
                    metrics = {"total_return": 0.0, "max_drawdown": 0.0, "blown_up": True, "trades": 0, "min_equity": 0.0, "final_value": 0.0}
                per_asset[stem] = metrics
                log(f"    {stem}: ret={metrics['total_return']*100:.2f}% dd={metrics['max_drawdown']*100:.2f}% "
                    f"{'BLOWN UP' if metrics['blown_up'] else 'ok'} ({metrics.get('trades',0)} trades)")
                returns.append(metrics["total_return"])
                drawdowns.append(metrics["max_drawdown"])
                any_blowup = any_blowup or metrics["blown_up"]

            avg_return = sum(returns) / len(returns) if returns else 0.0
            avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0.0
            results.append({
                "proposal": proposal,
                "avg_return": avg_return,
                "avg_drawdown": avg_dd,
                "any_blowup": any_blowup,
                "per_asset": per_asset,
            })
        return results

    def _backtest(self, proposal: dict, stem: str) -> dict:
        cerebro = bt.Cerebro()
        cerebro.addstrategy(
            HyperAlphaKelly,
            breakout_period=proposal["breakout_period"],
            momentum_period=proposal["momentum_period"],
            atr_period=proposal["atr_period"],
            trend_ema=proposal["trend_ema"],
            kelly_fraction=proposal["kelly_fraction"],
            atr_trail_mult=2.5,
            kelly_max_leverage=5.0,
        )

        broker = cerebro.broker
        broker.set_cash(STARTING_CASH)
        # Permit leverage: don't pre-reject orders that exceed cash (5x exposure).
        broker.set_checksubmit(False)

        fr = FRICTION[stem]
        broker.setcommission(commission=fr["commission"])
        broker.set_slippage_perc(perc=fr["slippage"])

        data = self.load_data(stem)
        cerebro.adddata(bt.feeds.PandasData(dataname=data, name=stem))

        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(ValueTracker, _name="value")

        strat = cerebro.run()[0]
        returns = strat.analyzers.returns.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        value = strat.analyzers.value.get_analysis()

        total_return = float(returns.get("rtot", 0.0))
        max_dd = float(drawdown.get("max", {}).get("drawdown", 0.0)) / 100.0
        if pd.isna(total_return):
            total_return = 0.0
        if pd.isna(max_dd):
            max_dd = 0.0

        final_value = broker.getvalue()
        return {
            "total_return": total_return,
            "max_drawdown": max_dd,
            "blown_up": bool(value["blown_up"]),
            "min_equity": float(value["min_value"]),
            "final_value": float(final_value),
            "trades": getattr(strat, "final_stats", {}).get("trades", 0),
        }

    # ------------------------------------------------------------------
    # CHIEF RISK OFFICER
    # ------------------------------------------------------------------
    def chief_risk_officer(self, results: list[dict]) -> list[dict]:
        print("\n=== CHIEF RISK OFFICER ===")
        verdicts = []
        for r in results:
            blown = r["any_blowup"]
            avg_return = r["avg_return"]
            avg_dd = r["avg_drawdown"]
            # HyperAlpha criteria + hard ruin veto.
            approved = (not blown) and avg_return > 0.10 and avg_dd < 0.40
            reason = (
                "BLOWN UP (liquidation on >=1 asset) — VETOED" if blown
                else ("Robust" if approved else f"Ret={avg_return:.2%}, DD={avg_dd:.2%}")
            )
            verdicts.append({**r, "approved": approved, "reason": reason})
        approved_n = sum(1 for v in verdicts if v["approved"])
        print(f"Approved {approved_n} of {len(verdicts)} proposals "
              f"({sum(1 for v in verdicts if v['any_blowup'])} blew up)")
        return verdicts

    # ------------------------------------------------------------------
    def run(self) -> None:
        log("=" * 80)
        log("INTRADAY HYPER-ALPHA TRI-AGENT OPTIMIZER — FULL KELLY / 5x LEVERAGE")
        log("=" * 80)
        if not self.assets:
            log("No intraday data found. Run intraday_fetcher.py first.")
            return
        log(f"Assets: {list(self.assets.keys())} | interval={self.interval}\n")

        proposals = self.quant_generator()
        results = self.red_team(proposals)
        verdicts = self.chief_risk_officer(results)

        ranked = sorted(verdicts, key=lambda x: x["avg_return"], reverse=True)

        log("\n" + "=" * 80)
        log("INTRADAY COMPOUNDING PERFORMANCE MATRIX")
        log("=" * 80)
        header = f"{'Strategy':<20}{'AvgRet':>10}{'AvgDD':>10}{'BlewUp':>9}{'Status':>12}"
        log(header)
        log("-" * len(header))
        for v in ranked:
            status = "APPROVED" if v["approved"] else ("BLOWN UP" if v["any_blowup"] else "REJECTED")
            log(f"{v['proposal']['name']:<20}"
                f"{v['avg_return']*100:>9.2f}%"
                f"{v['avg_drawdown']*100:>9.2f}%"
                f"{('YES' if v['any_blowup'] else 'no'):>9}"
                f"{status:>12}")

        # Per-asset breakdown for the top proposal
        log("\nPer-asset detail (top proposal):")
        top = ranked[0]
        for stem, m in top["per_asset"].items():
            log(f"  {stem:<10} ret={m['total_return']*100:7.2f}%  "
                f"dd={m['max_drawdown']*100:6.2f}%  "
                f"final=${m['final_value']:,.0f}  "
                f"minEq=${m['min_equity']:,.0f}  "
                f"{'BLOWN UP' if m['blown_up'] else 'survived'}")

        out = LOGS_DIR / "intraday_hyperalpha_results.json"
        out.write_text(json.dumps({"verdicts": ranked}, indent=2, default=str))
        log(f"\nDetailed results saved to {out}")


if __name__ == "__main__":
    IntradayHyperAlphaOptimizer(INTERVAL).run()
