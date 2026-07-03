"""
backtest/performance.py
=======================
Performance analytics for the allocation walk-forward backtester:
  * core metrics (total return, CAGR, Sharpe, Sortino, Calmar, max DD + duration,
    win rate, profit factor, trades, avg holding period)
  * regime-specific breakdown table
  * confidence-bucketed table (<50, 50-60, 60-70, 70+)
  * benchmark comparison (buy & hold, 200-SMA, random)
  * worst-case stats (worst day/week/month, max consecutive losses, longest underwater)
  * CSV export (equity curve, trade log, regime history)

Rendering uses `rich` when available and falls back to plain text.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:
    from rich.console import Console
    from rich.table import Table
    _RICH = True
except Exception:  # pragma: no cover
    _RICH = False

TRADING_DAYS = 252
RISK_FREE = 0.045


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
def _max_drawdown(equity: np.ndarray) -> tuple[float, int]:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min()) if len(dd) else 0.0
    # Longest underwater duration (bars below the running peak).
    underwater = equity < peak
    longest, cur = 0, 0
    for flag in underwater:
        cur = cur + 1 if flag else 0
        longest = max(longest, cur)
    return max_dd, longest


def _sharpe(returns: np.ndarray, rf: float = RISK_FREE) -> float:
    if returns.size < 2 or returns.std(ddof=1) == 0:
        return 0.0
    excess = returns - rf / TRADING_DAYS
    return float(excess.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _sortino(returns: np.ndarray, rf: float = RISK_FREE) -> float:
    if returns.size < 2:
        return 0.0
    excess = returns - rf / TRADING_DAYS
    downside = excess[excess < 0]
    dd = downside.std(ddof=1) if downside.size > 1 else 0.0
    return float(excess.mean() / dd * np.sqrt(TRADING_DAYS)) if dd > 0 else 0.0


def compute_metrics(equity: np.ndarray, returns: np.ndarray, trades: list[dict]) -> dict:
    n = len(equity)
    total_return = float(equity[-1] / equity[0] - 1.0) if n else 0.0
    years = n / TRADING_DAYS
    cagr = float((equity[-1] / equity[0]) ** (1 / years) - 1.0) if years > 0 and equity[0] > 0 else 0.0
    max_dd, underwater = _max_drawdown(equity)
    calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    win_rate = float(len(wins) / len(trades)) if trades else 0.0
    avg_hold = float(np.mean([t["hold_bars"] for t in trades])) if trades else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": _sharpe(returns),
        "sortino": _sortino(returns),
        "calmar": calmar,
        "max_drawdown": max_dd,
        "underwater_bars": underwater,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": len(trades),
        "avg_holding_bars": avg_hold,
    }


def worst_case(returns: np.ndarray, trades: list[dict], equity: np.ndarray) -> dict:
    daily = pd.Series(returns)
    worst_day = float(daily.min()) if len(daily) else 0.0
    worst_week = float(daily.rolling(5).sum().min()) if len(daily) >= 5 else 0.0
    worst_month = float(daily.rolling(21).sum().min()) if len(daily) >= 21 else 0.0

    max_consec, cur = 0, 0
    for t in trades:
        cur = cur + 1 if t["pnl"] < 0 else 0
        max_consec = max(max_consec, cur)

    _, underwater = _max_drawdown(equity)
    return {
        "worst_day": worst_day, "worst_week": worst_week, "worst_month": worst_month,
        "max_consecutive_losses": max_consec, "longest_underwater_bars": underwater,
    }


# ---------------------------------------------------------------------------
# Breakdown tables
# ---------------------------------------------------------------------------
def regime_breakdown(regime_history: list[dict], returns: np.ndarray, trades: list[dict]) -> pd.DataFrame:
    if not regime_history:
        return pd.DataFrame()
    labels = [m["label"] for m in regime_history]
    r = returns[: len(labels)]
    df = pd.DataFrame({"label": labels, "ret": r})
    total = len(df)
    rows = []
    for label, grp in df.groupby("label"):
        seg_trades = [t for t in trades if t.get("meta") and t["meta"].get("label") == label]
        pnls = [t["pnl"] for t in seg_trades]
        wins = [p for p in pnls if p > 0]
        rows.append({
            "Regime": label,
            "% Time In": f"{100 * len(grp) / total:.1f}%",
            "Return Contribution": f"{100 * grp['ret'].sum():.2f}%",
            "Avg Trade P&L": f"{np.mean(pnls):.0f}" if pnls else "-",
            "Win Rate": f"{100 * len(wins) / len(pnls):.1f}%" if pnls else "-",
            "Sharpe": f"{_sharpe(grp['ret'].to_numpy()):.2f}",
        })
    return pd.DataFrame(rows)


def confidence_breakdown(trades: list[dict]) -> pd.DataFrame:
    buckets = [("< 50%", 0.0, 0.5), ("50-60%", 0.5, 0.6), ("60-70%", 0.6, 0.7), ("70%+", 0.7, 1.01)]
    rows = []
    for name, lo, hi in buckets:
        sel = [t for t in trades if t.get("meta") and lo <= t["meta"].get("probability", 0) < hi]
        pnls = [t["pnl"] for t in sel]
        rets = np.array([t["return_pct"] for t in sel])
        wins = [p for p in pnls if p > 0]
        rows.append({
            "Confidence": name,
            "Trades": len(sel),
            "Sharpe": f"{_sharpe(rets):.2f}" if len(rets) > 1 else "-",
            "Win Rate": f"{100 * len(wins) / len(pnls):.1f}%" if pnls else "-",
            "Avg P&L": f"{np.mean(pnls):.0f}" if pnls else "-",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _print_df(title: str, df: pd.DataFrame) -> None:
    if df.empty:
        print(f"\n{title}: (no data)")
        return
    if _RICH:
        console = Console()
        table = Table(title=title, header_style="bold cyan")
        for col in df.columns:
            table.add_column(str(col))
        for _, row in df.iterrows():
            table.add_row(*[str(v) for v in row.values])
        console.print(table)
    else:
        print(f"\n=== {title} ===")
        print(df.to_string(index=False))


def _print_metrics(title: str, metrics: dict) -> None:
    df = pd.DataFrame([
        {"Metric": "Total Return", "Value": f"{metrics['total_return']:.2%}"},
        {"Metric": "CAGR", "Value": f"{metrics['cagr']:.2%}"},
        {"Metric": "Sharpe", "Value": f"{metrics['sharpe']:.2f}"},
        {"Metric": "Sortino", "Value": f"{metrics['sortino']:.2f}"},
        {"Metric": "Calmar", "Value": f"{metrics['calmar']:.2f}"},
        {"Metric": "Max Drawdown", "Value": f"{metrics['max_drawdown']:.2%}"},
        {"Metric": "Underwater (bars)", "Value": str(metrics["underwater_bars"])},
        {"Metric": "Win Rate", "Value": f"{metrics['win_rate']:.2%}"},
        {"Metric": "Profit Factor", "Value": f"{metrics['profit_factor']:.2f}"},
        {"Metric": "Total Trades", "Value": str(metrics["total_trades"])},
        {"Metric": "Avg Holding (bars)", "Value": f"{metrics['avg_holding_bars']:.1f}"},
    ])
    _print_df(title, df)


def report(result, benchmarks: dict | None = None, out_dir: Path | None = None) -> dict:
    """Print the full performance report; optionally write CSVs. Returns metrics dict."""
    metrics = compute_metrics(result.equity, result.returns, result.trades)
    wc = worst_case(result.returns, result.trades, result.equity)

    print("\n" + "=" * 74)
    print(f"WALK-FORWARD RESULTS — {result.symbol}  "
          f"({result.index[0].date()} → {result.index[-1].date()}, "
          f"{result.n_windows} OOS windows)")
    print("=" * 74)

    _print_metrics("Core Metrics (out-of-sample)", metrics)
    _print_df("Regime Breakdown", regime_breakdown(result.regime_history, result.returns, result.trades))
    _print_df("Confidence Buckets", confidence_breakdown(result.trades))

    wc_df = pd.DataFrame([
        {"Worst-Case": "Worst Day", "Value": f"{wc['worst_day']:.2%}"},
        {"Worst-Case": "Worst Week", "Value": f"{wc['worst_week']:.2%}"},
        {"Worst-Case": "Worst Month", "Value": f"{wc['worst_month']:.2%}"},
        {"Worst-Case": "Max Consecutive Losses", "Value": str(wc["max_consecutive_losses"])},
        {"Worst-Case": "Longest Underwater (bars)", "Value": str(wc["longest_underwater_bars"])},
    ])
    _print_df("Worst-Case", wc_df)

    if benchmarks:
        rows = [{
            "Strategy": "HMM Allocation",
            "Total Return": f"{metrics['total_return']:.2%}",
            "Sharpe": f"{metrics['sharpe']:.2f}",
            "Max DD": f"{metrics['max_drawdown']:.2%}",
        }]
        for name, eq in benchmarks.items():
            if name == "random":
                rows.append({
                    "Strategy": "Random (mean±std)",
                    "Total Return": f"{eq['return_mean']:.2%} ± {eq['return_std']:.2%}",
                    "Sharpe": f"{eq['sharpe_mean']:.2f} ± {eq['sharpe_std']:.2f}",
                    "Max DD": "-",
                })
            else:
                bret = float(eq[-1] / eq[0] - 1.0)
                bdr = np.diff(eq) / eq[:-1]
                bdd, _ = _max_drawdown(eq)
                rows.append({
                    "Strategy": name,
                    "Total Return": f"{bret:.2%}",
                    "Sharpe": f"{_sharpe(bdr):.2f}",
                    "Max DD": f"{bdd:.2%}",
                })
        _print_df("Benchmark Comparison", pd.DataFrame(rows))

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"date": result.index, "equity": result.equity,
                      "target": result.target, "close": result.close}).to_csv(out_dir / "equity_curve.csv", index=False)
        pd.DataFrame([{k: v for k, v in t.items() if k != "meta"} for t in result.trades]).to_csv(
            out_dir / "trade_log.csv", index=False)
        pd.DataFrame(result.regime_history).to_csv(out_dir / "regime_history.csv", index=False)
        print(f"\nCSV artefacts written to {out_dir}/")

    return metrics
