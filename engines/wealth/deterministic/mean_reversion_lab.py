from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


PHASE_ID = "12A"
LAB_NAME = "Wealth Mean Reversion Lab"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/wealth_mean_reversion")


@dataclass(frozen=True)
class MeanReversionConfig:
    lookback: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.25
    max_weight: float = 1.0
    cost_bps: float = 5.0
    annualization: int = 252

    def validate(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be at least 2")
        if self.entry_z <= 0:
            raise ValueError("entry_z must be positive")
        if self.exit_z < 0 or self.exit_z >= self.entry_z:
            raise ValueError("exit_z must be non-negative and below entry_z")
        if self.max_weight <= 0:
            raise ValueError("max_weight must be positive")
        if self.cost_bps < 0:
            raise ValueError("cost_bps cannot be negative")
        if self.annualization <= 0:
            raise ValueError("annualization must be positive")


@dataclass(frozen=True)
class MeanReversionBacktestResult:
    config: MeanReversionConfig
    signals: pd.DataFrame
    strategy_returns: pd.Series
    benchmark_returns: pd.Series
    equity_curve: pd.Series
    metrics: dict[str, float | int]
    safety: dict[str, Any]


def signal_definitions() -> dict[str, str]:
    return {
        "rolling_mean": "Trailing mean of close prices over the configured lookback window.",
        "rolling_std": "Trailing sample standard deviation over the configured lookback window.",
        "zscore": "Distance from rolling_mean measured in rolling_std units.",
        "raw_signal": "Contrarian research signal: long when zscore is below -entry_z, short when above entry_z, flat inside exit_z.",
        "target_weight": "Bounded research exposure used only for offline backtest accounting.",
    }


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "lab": LAB_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "LIVE TRADING": "DISABLED",
    }


def build_mean_reversion_signals(
    prices: pd.Series | pd.DataFrame,
    config: MeanReversionConfig | None = None,
) -> pd.DataFrame:
    cfg = config or MeanReversionConfig()
    cfg.validate()
    close = _coerce_close(prices)

    rolling_mean = close.rolling(cfg.lookback, min_periods=cfg.lookback).mean()
    rolling_std = close.rolling(cfg.lookback, min_periods=cfg.lookback).std(ddof=1)
    zscore = (close - rolling_mean) / rolling_std.mask(rolling_std == 0.0)

    raw_signal = pd.Series(0.0, index=close.index)
    raw_signal[zscore <= -cfg.entry_z] = 1.0
    raw_signal[zscore >= cfg.entry_z] = -1.0
    raw_signal[zscore.abs() <= cfg.exit_z] = 0.0
    raw_signal = raw_signal.ffill().fillna(0.0).clip(-1.0, 1.0)

    return pd.DataFrame(
        {
            "close": close,
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
            "zscore": zscore.astype(float),
            "raw_signal": raw_signal,
            "target_weight": raw_signal * cfg.max_weight,
        }
    )


def run_research_backtest(
    prices: pd.Series | pd.DataFrame,
    config: MeanReversionConfig | None = None,
) -> MeanReversionBacktestResult:
    cfg = config or MeanReversionConfig()
    cfg.validate()
    signals = build_mean_reversion_signals(prices, cfg)

    close = signals["close"]
    asset_returns = close.pct_change().fillna(0.0)
    target = signals["target_weight"].fillna(0.0)
    research_position = target.shift(1).fillna(0.0)
    turnover = research_position.diff().abs().fillna(research_position.abs())
    costs = turnover * (cfg.cost_bps / 10_000.0)

    strategy_returns = (research_position * asset_returns - costs).fillna(0.0)
    equity_curve = (1.0 + strategy_returns).cumprod()
    benchmark_returns = asset_returns.fillna(0.0)

    metrics = _compute_metrics(
        strategy_returns=strategy_returns,
        benchmark_returns=benchmark_returns,
        equity_curve=equity_curve,
        target=target,
        annualization=cfg.annualization,
    )

    return MeanReversionBacktestResult(
        config=cfg,
        signals=signals,
        strategy_returns=strategy_returns,
        benchmark_returns=benchmark_returns,
        equity_curve=equity_curve,
        metrics=metrics,
        safety=safety_manifest(),
    )


def build_report_payload(result: MeanReversionBacktestResult) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "lab": LAB_NAME,
        "safety": result.safety,
        "signal_definitions": signal_definitions(),
        "config": {
            "lookback": result.config.lookback,
            "entry_z": result.config.entry_z,
            "exit_z": result.config.exit_z,
            "max_weight": result.config.max_weight,
            "cost_bps": result.config.cost_bps,
            "annualization": result.config.annualization,
        },
        "metrics": result.metrics,
    }


def render_markdown_report(result: MeanReversionBacktestResult) -> str:
    payload = build_report_payload(result)
    lines = [
        f"# {PHASE_ID} {LAB_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Signal Definitions",
    ]
    for name, definition in payload["signal_definitions"].items():
        lines.append(f"- {name}: {definition}")

    lines.extend(["", "## Backtest Metrics"])
    for name, value in payload["metrics"].items():
        if isinstance(value, float):
            lines.append(f"- {name}: {value:.6f}")
        else:
            lines.append(f"- {name}: {value}")

    lines.extend(
        [
            "",
            "## Safety",
            "- No broker imports or order routing are used.",
            "- Signals are shifted by one bar before return accounting.",
            "- Output is research-only and requires human review before any trade-relevant use.",
        ]
    )
    return "\n".join(lines)


def write_research_report(
    result: MeanReversionBacktestResult,
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


def _coerce_close(prices: pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(prices, pd.Series):
        close = prices.copy()
    elif "close" in prices.columns:
        close = prices["close"].copy()
    elif "Close" in prices.columns:
        close = prices["Close"].copy()
    else:
        raise ValueError("prices must be a Series or contain a close/Close column")

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        raise ValueError("prices must contain at least one numeric close")
    return close.astype(float)


def _compute_metrics(
    *,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    equity_curve: pd.Series,
    target: pd.Series,
    annualization: int,
) -> dict[str, float | int]:
    total_return = float(equity_curve.iloc[-1] - 1.0) if not equity_curve.empty else 0.0
    benchmark_total_return = float((1.0 + benchmark_returns).prod() - 1.0)
    volatility = float(strategy_returns.std(ddof=1) * sqrt(annualization)) if len(strategy_returns) > 1 else 0.0
    sharpe = (
        float(strategy_returns.mean() / strategy_returns.std(ddof=1) * sqrt(annualization))
        if len(strategy_returns) > 1 and strategy_returns.std(ddof=1) > 0
        else 0.0
    )
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    active_days = int((target.abs() > 0).sum())
    signal_flips = int((target.diff().fillna(target).abs() > 0).sum())

    return {
        "total_return": total_return,
        "benchmark_total_return": benchmark_total_return,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "active_days": active_days,
        "signal_flips": signal_flips,
        "observations": int(len(strategy_returns)),
    }
