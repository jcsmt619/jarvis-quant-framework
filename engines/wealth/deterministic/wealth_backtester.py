from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


PHASE_ID = "12B"
BACKTESTER_NAME = "Wealth Backtester"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/wealth_backtester")


@dataclass(frozen=True)
class WealthCostSlippageAssumptions:
    commission_bps: float = 1.0
    spread_bps: float = 2.0
    market_impact_bps: float = 5.0
    min_trade_cost_bps: float = 0.5
    impact_exponent: float = 1.5
    enabled: bool = True

    def validate(self) -> None:
        for name, value in (
            ("commission_bps", self.commission_bps),
            ("spread_bps", self.spread_bps),
            ("market_impact_bps", self.market_impact_bps),
            ("min_trade_cost_bps", self.min_trade_cost_bps),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.impact_exponent < 1.0:
            raise ValueError("impact_exponent must be at least 1.0")

    @classmethod
    def disabled(cls) -> "WealthCostSlippageAssumptions":
        return cls(
            commission_bps=0.0,
            spread_bps=0.0,
            market_impact_bps=0.0,
            min_trade_cost_bps=0.0,
            enabled=False,
        )


@dataclass(frozen=True)
class WealthBacktestConfig:
    train_size: int
    test_size: int | None = None
    initial_equity: float = 1.0
    cost_bps: float = 1.0
    annualization: int = 252
    max_abs_weight: float = 1.0
    cost_slippage: WealthCostSlippageAssumptions = field(default_factory=WealthCostSlippageAssumptions)

    def validate(self) -> None:
        if self.train_size < 1:
            raise ValueError("train_size must be positive")
        if self.test_size is not None and self.test_size < 1:
            raise ValueError("test_size must be positive when provided")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.cost_bps < 0:
            raise ValueError("cost_bps cannot be negative")
        if self.annualization <= 0:
            raise ValueError("annualization must be positive")
        if self.max_abs_weight <= 0:
            raise ValueError("max_abs_weight must be positive")
        self.cost_slippage.validate()


@dataclass(frozen=True)
class CostBreakdown:
    total_cost: pd.Series
    components: pd.DataFrame


CostHook = Callable[[pd.DataFrame, pd.DataFrame, WealthBacktestConfig], CostBreakdown]


@dataclass(frozen=True)
class WealthBacktestResult:
    config: WealthBacktestConfig
    train_prices: pd.DataFrame
    test_prices: pd.DataFrame
    target_weights: pd.DataFrame
    execution_weights: pd.DataFrame
    asset_returns: pd.DataFrame
    strategy_returns: pd.Series
    gross_returns: pd.Series
    cost_returns: pd.Series
    cost_components: pd.DataFrame
    equity_curve: pd.Series
    benchmark_returns: dict[str, pd.Series]
    benchmark_metrics: dict[str, dict[str, float | int]]
    metrics: dict[str, float | int]
    safety: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "cost_slippage_phase": "12C",
        "backtester": BACKTESTER_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def default_conservative_cost_slippage_hook(
    execution_weights: pd.DataFrame,
    target_weights: pd.DataFrame,
    config: WealthBacktestConfig,
) -> CostBreakdown:
    assumptions = config.cost_slippage
    trade_abs = execution_weights.diff().abs().fillna(execution_weights.abs())
    turnover = trade_abs.sum(axis=1)
    legacy_linear_cost = turnover * (config.cost_bps / 10_000.0)

    if not assumptions.enabled:
        total = legacy_linear_cost
        return CostBreakdown(
            total_cost=total.rename("total_cost"),
            components=pd.DataFrame(
                {
                    "legacy_linear_bps_cost": legacy_linear_cost,
                    "commission_cost": 0.0,
                    "spread_cost": 0.0,
                    "market_impact_cost": 0.0,
                    "min_trade_cost": 0.0,
                },
                index=execution_weights.index,
            ),
        )

    commission_cost = turnover * (assumptions.commission_bps / 10_000.0)
    spread_cost = turnover * (assumptions.spread_bps / 10_000.0)
    market_impact_cost = (
        trade_abs.pow(assumptions.impact_exponent).sum(axis=1)
        * (assumptions.market_impact_bps / 10_000.0)
    )
    min_trade_cost = (turnover > 0.0).astype(float) * (assumptions.min_trade_cost_bps / 10_000.0)
    total = legacy_linear_cost + commission_cost + spread_cost + market_impact_cost + min_trade_cost

    return CostBreakdown(
        total_cost=total.rename("total_cost"),
        components=pd.DataFrame(
            {
                "legacy_linear_bps_cost": legacy_linear_cost,
                "commission_cost": commission_cost,
                "spread_cost": spread_cost,
                "market_impact_cost": market_impact_cost,
                "min_trade_cost": min_trade_cost,
            },
            index=execution_weights.index,
        ),
    )


def default_linear_cost_hook(
    execution_weights: pd.DataFrame,
    target_weights: pd.DataFrame,
    config: WealthBacktestConfig,
) -> CostBreakdown:
    turnover = execution_weights.diff().abs().fillna(execution_weights.abs()).sum(axis=1)
    linear_cost = turnover * (config.cost_bps / 10_000.0)
    return CostBreakdown(
        total_cost=linear_cost.rename("total_cost"),
        components=pd.DataFrame({"linear_bps_cost": linear_cost}, index=execution_weights.index),
    )


def run_wealth_backtest(
    prices: pd.Series | pd.DataFrame,
    target_weights: pd.Series | pd.DataFrame,
    config: WealthBacktestConfig,
    *,
    cost_hook: CostHook | None = None,
) -> WealthBacktestResult:
    config.validate()
    price_frame = _coerce_price_frame(prices)
    weight_frame = _coerce_weight_frame(target_weights, price_frame.columns)
    price_frame, weight_frame = _align_inputs(price_frame, weight_frame)

    if len(price_frame) <= config.train_size:
        raise ValueError("prices must contain rows beyond the train_size")

    test_end = len(price_frame) if config.test_size is None else config.train_size + config.test_size
    if test_end > len(price_frame):
        raise ValueError("train_size + test_size exceeds available observations")

    train_prices = price_frame.iloc[: config.train_size].copy()
    test_prices = price_frame.iloc[config.train_size:test_end].copy()
    test_weights = weight_frame.iloc[config.train_size:test_end].copy().clip(
        lower=-config.max_abs_weight,
        upper=config.max_abs_weight,
    )

    asset_returns = test_prices.pct_change().fillna(0.0)
    execution_weights = test_weights.shift(1).fillna(0.0)
    gross_returns = (execution_weights * asset_returns).sum(axis=1).rename("gross_return")

    hook = cost_hook or default_conservative_cost_slippage_hook
    costs = hook(execution_weights, test_weights, config)
    cost_returns = costs.total_cost.reindex(test_prices.index).fillna(0.0).rename("cost_return")
    cost_components = costs.components.reindex(test_prices.index).fillna(0.0)
    strategy_returns = (gross_returns - cost_returns).rename("strategy_return")
    equity_curve = (config.initial_equity * (1.0 + strategy_returns).cumprod()).rename("equity")

    benchmark_returns = build_benchmark_returns(test_prices)
    benchmark_metrics = {
        name: compute_return_metrics(returns, annualization=config.annualization)
        for name, returns in benchmark_returns.items()
    }
    metrics = compute_return_metrics(strategy_returns, equity_curve=equity_curve, annualization=config.annualization)
    metrics.update(
        {
            "train_observations": int(len(train_prices)),
            "test_observations": int(len(test_prices)),
            "turnover": float(execution_weights.diff().abs().fillna(execution_weights.abs()).sum(axis=1).sum()),
            "total_cost": float(cost_returns.sum()),
            "benchmark_count": int(len(benchmark_returns)),
        }
    )

    return WealthBacktestResult(
        config=config,
        train_prices=train_prices,
        test_prices=test_prices,
        target_weights=test_weights,
        execution_weights=execution_weights,
        asset_returns=asset_returns,
        strategy_returns=strategy_returns,
        gross_returns=gross_returns,
        cost_returns=cost_returns,
        cost_components=cost_components,
        equity_curve=equity_curve,
        benchmark_returns=benchmark_returns,
        benchmark_metrics=benchmark_metrics,
        metrics=metrics,
        safety=safety_manifest(),
    )


def build_benchmark_returns(test_prices: pd.DataFrame) -> dict[str, pd.Series]:
    asset_returns = test_prices.pct_change().fillna(0.0)
    benchmarks: dict[str, pd.Series] = {
        "equal_weight_buy_hold": asset_returns.mean(axis=1).rename("equal_weight_buy_hold"),
    }
    if len(test_prices.columns) == 1:
        col = test_prices.columns[0]
        benchmarks[f"{col}_buy_hold"] = asset_returns[col].rename(f"{col}_buy_hold")
    else:
        for col in test_prices.columns:
            benchmarks[f"{col}_buy_hold"] = asset_returns[col].rename(f"{col}_buy_hold")
    return benchmarks


def compute_return_metrics(
    returns: pd.Series,
    *,
    equity_curve: pd.Series | None = None,
    annualization: int = 252,
) -> dict[str, float | int]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0).astype(float)
    equity = equity_curve if equity_curve is not None else (1.0 + clean).cumprod()
    total_return = float((1.0 + clean).prod() - 1.0) if len(clean) else 0.0
    volatility = float(clean.std(ddof=1) * sqrt(annualization)) if len(clean) > 1 else 0.0
    sharpe = (
        float(clean.mean() / clean.std(ddof=1) * sqrt(annualization))
        if len(clean) > 1 and clean.std(ddof=1) > 0
        else 0.0
    )
    drawdown = equity / equity.cummax() - 1.0
    win_rate = float((clean > 0.0).sum() / len(clean)) if len(clean) else 0.0
    return {
        "total_return": total_return,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
        "win_rate": win_rate,
        "observations": int(len(clean)),
    }


def build_report_payload(result: WealthBacktestResult) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "backtester": BACKTESTER_NAME,
        "safety": result.safety,
        "config": {
            "train_size": result.config.train_size,
            "test_size": result.config.test_size,
            "initial_equity": result.config.initial_equity,
            "cost_bps": result.config.cost_bps,
            "cost_slippage": {
                "phase": "12C",
                "commission_bps": result.config.cost_slippage.commission_bps,
                "spread_bps": result.config.cost_slippage.spread_bps,
                "market_impact_bps": result.config.cost_slippage.market_impact_bps,
                "min_trade_cost_bps": result.config.cost_slippage.min_trade_cost_bps,
                "impact_exponent": result.config.cost_slippage.impact_exponent,
                "enabled": result.config.cost_slippage.enabled,
            },
            "annualization": result.config.annualization,
            "max_abs_weight": result.config.max_abs_weight,
        },
        "train_period": _period_payload(result.train_prices),
        "test_period": _period_payload(result.test_prices),
        "metrics": result.metrics,
        "benchmark_metrics": result.benchmark_metrics,
    }


def render_markdown_report(result: WealthBacktestResult) -> str:
    payload = build_report_payload(result)
    lines = [
        f"# {PHASE_ID} {BACKTESTER_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Train/Test Separation",
        f"- Train observations: {payload['metrics']['train_observations']}",
        f"- Test observations: {payload['metrics']['test_observations']}",
        "",
        "## Strategy Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {_format_metric(value)}")

    lines.extend(["", "## Benchmarks"])
    for benchmark_name, metrics in payload["benchmark_metrics"].items():
        lines.append(f"- {benchmark_name}: total_return={metrics['total_return']:.6f}, sharpe={metrics['sharpe']:.6f}")

    lines.extend(
        [
            "",
            "## Cost and Slippage",
            f"- Model phase: {payload['config']['cost_slippage']['phase']}",
            f"- Enabled: {payload['config']['cost_slippage']['enabled']}",
            f"- Commission bps: {payload['config']['cost_slippage']['commission_bps']:.6f}",
            f"- Spread bps: {payload['config']['cost_slippage']['spread_bps']:.6f}",
            f"- Market impact bps: {payload['config']['cost_slippage']['market_impact_bps']:.6f}",
            "",
            "## Safety",
            "- No broker imports, order routing, or order submission are used.",
            "- Target weights are shifted one bar before return accounting.",
            "- Outputs are deterministic research artifacts and require human review before trade-relevant use.",
        ]
    )
    return "\n".join(lines)


def write_research_report(
    result: WealthBacktestResult,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(result)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_report(result), encoding="utf-8")
    return json_path, md_path


def _coerce_price_frame(prices: pd.Series | pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices, pd.Series):
        frame = prices.to_frame(prices.name or "asset")
    else:
        frame = prices.copy()
        if "close" in frame.columns and len(frame.columns) == 1:
            frame = frame.rename(columns={"close": "asset"})
        elif "Close" in frame.columns and len(frame.columns) == 1:
            frame = frame.rename(columns={"Close": "asset"})

    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    frame = frame.ffill().dropna(how="any")
    if frame.empty:
        raise ValueError("prices must contain numeric observations")
    return frame.astype(float)


def _coerce_weight_frame(weights: pd.Series | pd.DataFrame, columns: pd.Index) -> pd.DataFrame:
    if isinstance(weights, pd.Series):
        if len(columns) != 1:
            raise ValueError("Series weights can only be used with one price column")
        frame = weights.to_frame(columns[0])
    else:
        frame = weights.copy()
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"target_weights missing columns: {sorted(missing)}")
    frame = frame.loc[:, columns]
    return frame.apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


def _align_inputs(prices: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common_index = prices.index.intersection(weights.index)
    if len(common_index) < 2:
        raise ValueError("prices and target_weights must share at least two observations")
    return prices.reindex(common_index), weights.reindex(common_index)


def _period_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "start": frame.index[0] if len(frame) else None,
        "end": frame.index[-1] if len(frame) else None,
        "observations": int(len(frame)),
    }


def _format_metric(value: float | int) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)
