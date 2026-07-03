"""Performance metrics for the futures backtest.

Reports the usual risk-adjusted stats plus two things a futures trader needs:
expectancy in dollars per trade, and an explicit prop-firm verdict, since on a
funded account the only result that matters is whether you would have breached
the daily loss limit or the trailing drawdown at any point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backtest.backtester import BacktestResult


@dataclass
class PerformanceReport:
    total_pnl: float
    return_pct: float
    n_trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    prop_firm_pass: bool
    prop_firm_note: str
    by_regime: pd.DataFrame = field(default_factory=pd.DataFrame)
    extras: dict = field(default_factory=dict)


def analyze(result: BacktestResult, config: dict) -> PerformanceReport:
    bt = config.get("backtest", {})
    initial = float(result.meta.get("initial_equity", bt.get("initial_equity", 50000.0)))
    equity = result.equity_curve
    trades = result.trades

    total_pnl = (float(equity.iloc[-1]) - initial) if len(equity) else 0.0
    return_pct = total_pnl / initial if initial else 0.0

    if trades is None or trades.empty:
        return PerformanceReport(total_pnl, return_pct, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                 not result.blown,
                                 result.blown_reason or "no trades taken")

    pnl = trades["pnl"].astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    n = len(pnl)
    win_rate = len(wins) / n if n else 0.0
    gross_win, gross_loss = wins.sum(), abs(losses.sum())
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    avg_trade = pnl.mean()
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = abs(losses.mean()) if len(losses) else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    # Drawdown on the equity curve.
    max_dd, max_dd_pct = _max_drawdown(equity)

    # Sharpe / Sortino on per-bar equity returns (annualised by bar count).
    sharpe, sortino = _risk_adjusted(equity, bt)

    # Prop-firm verdict.
    pf_pass, pf_note = _prop_firm_verdict(result, config, initial, max_dd)

    by_regime = _by_regime(result)

    return PerformanceReport(
        total_pnl=total_pnl, return_pct=return_pct, n_trades=n, win_rate=win_rate,
        profit_factor=profit_factor, avg_trade=avg_trade, expectancy=expectancy,
        max_drawdown=max_dd, max_drawdown_pct=max_dd_pct, sharpe=sharpe, sortino=sortino,
        prop_firm_pass=pf_pass, prop_firm_note=pf_note, by_regime=by_regime,
        extras={"windows": result.windows, "avg_win": avg_win, "avg_loss": avg_loss,
                "gross_win": gross_win, "gross_loss": gross_loss},
    )


def _max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if len(equity) == 0:
        return 0.0, 0.0
    running_max = equity.cummax()
    dd = equity - running_max
    max_dd = float(dd.min())
    idx = dd.idxmin()
    peak = float(running_max.loc[idx]) if idx in running_max.index else float(running_max.max())
    max_dd_pct = (max_dd / peak) if peak else 0.0
    return max_dd, max_dd_pct


def _risk_adjusted(equity: pd.Series, bt: dict) -> tuple[float, float]:
    if len(equity) < 3:
        return 0.0, 0.0
    rets = equity.pct_change().dropna()
    if rets.std() == 0 or len(rets) == 0:
        return 0.0, 0.0
    # Annualisation factor from bar frequency.
    bars_per_year = float(bt.get("bars_per_year", 252 * 78))  # ~5-min RTH default
    ann = np.sqrt(bars_per_year)
    sharpe = float(rets.mean() / rets.std() * ann)
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std() * ann) if len(downside) and downside.std() > 0 else 0.0
    return sharpe, sortino


def _prop_firm_verdict(result: BacktestResult, config: dict,
                       initial: float, max_dd: float) -> tuple[bool, str]:
    pf = config.get("risk", {}).get("prop_firm", {})
    if not pf.get("enabled", True):
        return (not result.blown), "prop-firm rules disabled"
    if result.blown:
        return False, f"FAILED: {result.blown_reason}"
    tmdd = float(pf.get("trailing_max_drawdown", 0))
    dll = float(pf.get("daily_loss_limit", 0))
    if tmdd and abs(max_dd) >= tmdd:
        return False, f"FAILED: max drawdown ${abs(max_dd):.0f} >= trailing limit ${tmdd:.0f}"
    return True, f"PASSED: stayed within daily ${dll:.0f} / trailing ${tmdd:.0f} limits"


def _by_regime(result: BacktestResult) -> pd.DataFrame:
    trades, regimes = result.trades, result.regime_history
    if trades is None or trades.empty or regimes is None or regimes.empty:
        return pd.DataFrame()
    # Time-in-regime share.
    share = regimes["regime"].value_counts(normalize=True).rename("time_pct")
    rows = []
    for label, pct in share.items():
        rows.append({"regime": label, "time_pct": round(float(pct), 3)})
    return pd.DataFrame(rows)


def format_report(report: PerformanceReport) -> str:
    lines = [
        "=" * 56,
        "  FUTURES SCALPER  —  BACKTEST RESULT",
        "=" * 56,
        f"  Total P&L          : ${report.total_pnl:,.0f}",
        f"  Return on account  : {report.return_pct * 100:.1f}%",
        f"  Trades             : {report.n_trades}",
        f"  Win rate           : {report.win_rate * 100:.1f}%",
        f"  Profit factor      : {report.profit_factor:.2f}",
        f"  Avg trade          : ${report.avg_trade:,.1f}",
        f"  Expectancy / trade : ${report.expectancy:,.1f}",
        f"  Max drawdown       : ${report.max_drawdown:,.0f} ({report.max_drawdown_pct * 100:.1f}%)",
        f"  Sharpe             : {report.sharpe:.2f}",
        f"  Sortino            : {report.sortino:.2f}",
        f"  Walk-fwd windows   : {report.extras.get('windows', 0)}",
        "-" * 56,
        f"  PROP-FIRM VERDICT  : {report.prop_firm_note}",
        "=" * 56,
    ]
    return "\n".join(lines)
