"""
backtest/multistrat.py
======================
Multi-strategy extension of the walk-forward backtester. It runs several
strategies in parallel through the CapitalAllocator + health system + portfolio
risk layer and tracks BOTH portfolio-level and per-strategy metrics.

It operates on per-strategy daily-return series (data-agnostic) so it is fully
testable with synthetic returns. The CLI wraps real strategies by turning each
into a return stream via the single-strategy walk-forward on its primary symbol.

Single-strategy mode in backtester.py is unchanged; this is purely additive.

The guiding question (printed in the report): does the dynamically-allocated
multi-strat portfolio earn a better CALMAR than the best single strategy alone?
If not, the extra machinery is not paying for itself.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.performance import _max_drawdown, _sharpe, _sortino
from core.capital_allocator import CapitalAllocator, PortfolioSnapshot

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------
def equity_metrics(equity: np.ndarray, returns: np.ndarray) -> dict:
    n = len(equity)
    if n < 2 or equity[0] <= 0:
        return {"total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "sortino": 0.0,
                "max_drawdown": 0.0, "calmar": 0.0}
    total = float(equity[-1] / equity[0] - 1.0)
    years = n / TRADING_DAYS
    cagr = float((equity[-1] / equity[0]) ** (1 / years) - 1.0) if years > 0 else 0.0
    mdd, _ = _max_drawdown(equity)
    calmar = float(cagr / abs(mdd)) if mdd != 0 else 0.0
    return {"total_return": total, "cagr": cagr, "sharpe": _sharpe(returns),
            "sortino": _sortino(returns), "max_drawdown": mdd, "calmar": calmar}


def _curve_from_returns(returns: np.ndarray, initial: float = 100000.0) -> np.ndarray:
    return initial * np.cumprod(1.0 + returns)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class MultiStratResult:
    index: pd.DatetimeIndex
    portfolio_equity: np.ndarray
    portfolio_returns: np.ndarray
    strategy_returns: pd.DataFrame          # raw per-strategy daily returns (OOS)
    weight_history: pd.DataFrame            # date x strategy weights actually applied
    allocator_log: list[dict]
    correlation_matrix: pd.DataFrame
    correlation_history: pd.DataFrame       # long format: date, strategy_A, strategy_B, corr
    pair_over_threshold_pct: dict
    portfolio_metrics: dict
    per_strategy_metrics: dict
    turnover: int
    disabled_periods: dict
    benchmarks: dict = field(default_factory=dict)


class MultiStrategyBacktester:
    def __init__(self, registry, allocator: CapitalAllocator | None = None,
                 portfolio_risk=None, corr_window: int = 60, corr_threshold: float = 0.80,
                 enforce_health: bool = True):
        self.registry = registry
        self.allocator = allocator or CapitalAllocator(registry)
        self.portfolio_risk = portfolio_risk
        self.corr_window = corr_window
        self.corr_threshold = corr_threshold
        self.enforce_health = enforce_health

    # ------------------------------------------------------------------
    def run(self, strategy_returns: dict[str, pd.Series], initial_capital: float = 100000.0) -> MultiStratResult:
        names = list(strategy_returns)
        df = pd.DataFrame(strategy_returns).dropna()
        idx = df.index
        for n in names:
            self.registry.get(n).reset_state()

        port_eq = initial_capital
        port_curve, port_rets = [], []
        weight_hist = {n: [] for n in names}
        alloc_log: list[dict] = []
        disabled_periods = {n: [] for n in names}
        weights = {n: 0.0 for n in names}
        turnover, last_week, peak_eq = 0, None, initial_capital

        for _, date in enumerate(idx):
            rets = {n: float(df.loc[date, n]) for n in names}
            for n in names:
                self.registry.get(n).record_daily_return(rets[n])

            week = date.isocalendar()[:2]
            if last_week is None or week != last_week:
                last_week = week
                if self.enforce_health:
                    # Symmetric health gate (scoped to the backtested strategies):
                    # suspend a strategy while unhealthy, resume it once it recovers.
                    # A disable-only gate would strand a strategy in cash forever
                    # after one rough patch, degenerating the whole portfolio.
                    for n in names:
                        s = self.registry.get(n)
                        healthy = s.health_check().is_healthy
                        if healthy and not s.is_enabled:
                            s.on_enable()
                        elif not healthy and s.is_enabled:
                            s.on_disable()
                daily_dd = max(0.0, -(port_rets[-1] if port_rets else 0.0))
                peak_dd = (peak_eq - port_eq) / peak_eq if peak_eq > 0 else 0.0
                before = dict(weights)
                changes = self.allocator.rebalance(
                    self.registry, PortfolioSnapshot(total_capital=port_eq, daily_drawdown=daily_dd))
                # Weights are tracked as persistent FRACTIONS from the allocator's
                # target (AllocationChange.new_weight), not derived from dollar
                # allocated_capital -- the latter drifts as portfolio equity grows.
                for c in changes:
                    wb = before.get(c.strategy_name, 0.0)
                    if c.strategy_name in weights:
                        weights[c.strategy_name] = c.new_weight
                    alloc_log.append({"date": date, "strategy_name": c.strategy_name,
                                      "weight_before": wb, "weight_after": c.new_weight, "reason": c.reason})
                    if abs(c.new_weight - wb) > 0.05:
                        turnover += 1
                # Portfolio risk peak-DD halt (defense in depth above the allocator).
                if self.portfolio_risk is not None and peak_dd > getattr(self.portfolio_risk.limits, "peak_dd_halt", 1.0):
                    weights = {n: 0.0 for n in names}

            port_ret = sum(weights.get(n, 0.0) * rets[n] for n in names if self.registry.get(n).is_enabled)
            port_eq *= (1.0 + port_ret)
            peak_eq = max(peak_eq, port_eq)
            port_curve.append(port_eq)
            port_rets.append(port_ret)
            for n in names:
                enabled = self.registry.get(n).is_enabled
                weight_hist[n].append(weights.get(n, 0.0) if enabled else 0.0)
                if not enabled:
                    disabled_periods[n].append(date)

        equity = np.asarray(port_curve)
        preturns = np.asarray(port_rets)
        wh = pd.DataFrame(weight_hist, index=idx)

        return self._assemble(names, df, idx, equity, preturns, wh, alloc_log,
                              turnover, disabled_periods, initial_capital)

    # ------------------------------------------------------------------
    def _assemble(self, names, df, idx, equity, preturns, wh, alloc_log,
                  turnover, disabled_periods, initial_capital) -> MultiStratResult:
        portfolio_metrics = equity_metrics(equity, preturns)

        # --- per-strategy standalone metrics + attribution ---
        per_strategy: dict = {}
        total_attr = 0.0
        for n in names:
            r = df[n].to_numpy()
            eq = _curve_from_returns(r, initial_capital)
            m = equity_metrics(eq, r)
            contrib_return = float((wh[n].to_numpy() * r).sum())
            total_attr += contrib_return
            m["contribution_return"] = contrib_return
            m["disabled_days"] = len(disabled_periods[n])
            m["avg_weight"] = float(np.mean(wh[n].to_numpy()))
            per_strategy[n] = m

        # contribution to variance (average-weight risk decomposition)
        w_bar = np.array([per_strategy[n]["avg_weight"] for n in names])
        cov = df.cov().to_numpy()
        port_var = float(w_bar @ cov @ w_bar) if len(names) else 0.0
        rc = w_bar * (cov @ w_bar) if port_var > 0 else np.zeros(len(names))
        for i, n in enumerate(names):
            per_strategy[n]["contribution_variance"] = float(rc[i] / port_var) if port_var > 0 else 0.0
            denom = total_attr if abs(total_attr) > 1e-12 else 1.0
            per_strategy[n]["contribution_return_pct"] = per_strategy[n]["contribution_return"] / denom

        # --- correlation ---
        corr_matrix = df.corr()
        corr_hist_rows, pair_pct = [], {}
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                roll = df[a].rolling(self.corr_window).corr(df[b])
                valid = roll.dropna()
                over = float((valid > self.corr_threshold).mean()) if len(valid) else 0.0
                pair_pct[f"{a}~{b}"] = over
                for d, c in roll.items():
                    if pd.notna(c):
                        corr_hist_rows.append({"date": d, "strategy_A": a, "strategy_B": b, "rolling_correlation": float(c)})
        corr_history = pd.DataFrame(corr_hist_rows)

        return MultiStratResult(
            index=idx, portfolio_equity=equity, portfolio_returns=preturns,
            strategy_returns=df, weight_history=wh, allocator_log=alloc_log,
            correlation_matrix=corr_matrix, correlation_history=corr_history,
            pair_over_threshold_pct=pair_pct, portfolio_metrics=portfolio_metrics,
            per_strategy_metrics=per_strategy, turnover=turnover,
            disabled_periods=disabled_periods,
        )

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------
    def run_benchmarks(self, strategy_returns: dict[str, pd.Series], per_strategy_metrics: dict,
                       initial_capital: float = 100000.0, buy_hold_returns: pd.Series | None = None) -> dict:
        df = pd.DataFrame(strategy_returns).dropna()
        out: dict = {}

        # 1) Equal weight (static 1/N, no dynamic allocation)
        eq_ret = df.mean(axis=1).to_numpy()
        out["equal_weight"] = equity_metrics(_curve_from_returns(eq_ret, initial_capital), eq_ret)

        # 2/3) Best / worst single strategy (hindsight)
        by_total = sorted(per_strategy_metrics.items(), key=lambda kv: kv[1]["total_return"])
        if by_total:
            worst_name, best_name = by_total[0][0], by_total[-1][0]
            out["best_single"] = {"name": best_name, **{k: per_strategy_metrics[best_name][k]
                                  for k in ("total_return", "sharpe", "max_drawdown", "calmar")}}
            out["worst_single"] = {"name": worst_name, **{k: per_strategy_metrics[worst_name][k]
                                   for k in ("total_return", "sharpe", "max_drawdown", "calmar")}}

        # 4) Buy-and-hold of the most-traded symbol (returns supplied by caller)
        if buy_hold_returns is not None:
            r = buy_hold_returns.reindex(df.index).dropna().to_numpy()
            if len(r) > 1:
                out["buy_hold"] = equity_metrics(_curve_from_returns(r, initial_capital), r)
        return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_outputs(result: MultiStratResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    eq = pd.DataFrame({"date": result.index, "portfolio_equity": result.portfolio_equity})
    for n in result.strategy_returns.columns:
        eq[f"{n}_equity"] = _curve_from_returns(result.strategy_returns[n].to_numpy(), result.portfolio_equity[0])
    eq.to_csv(out_dir / "multistrat_equity.csv", index=False)

    pd.DataFrame(result.allocator_log).to_csv(out_dir / "allocator_log.csv", index=False)
    result.correlation_history.to_csv(out_dir / "correlation_history.csv", index=False)

    rows = []
    for n, m in result.per_strategy_metrics.items():
        rows.append({"strategy_name": n, "total_return": m["total_return"], "sharpe": m["sharpe"],
                     "max_dd": m["max_drawdown"], "contribution": m["contribution_return"]})
    pd.DataFrame(rows).to_csv(out_dir / "per_strategy_metrics.csv", index=False)
