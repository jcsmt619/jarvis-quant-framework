from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "12D"
FILTER_NAME = "Wealth Regime Filters"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/wealth_regime_filters")


@dataclass(frozen=True)
class WealthRegimeFilterConfig:
    volatility_window: int = 20
    max_annualized_volatility: float = 0.35
    volatility_spike_ratio: float = 1.75
    trend_short_window: int = 50
    trend_long_window: int = 200
    liquidity_window: int = 20
    min_avg_dollar_volume: float = 5_000_000.0
    min_avg_volume: float = 100_000.0
    risk_off_drawdown: float = -0.12
    annualization: int = 252

    def validate(self) -> None:
        for name, value in (
            ("volatility_window", self.volatility_window),
            ("trend_short_window", self.trend_short_window),
            ("trend_long_window", self.trend_long_window),
            ("liquidity_window", self.liquidity_window),
            ("annualization", self.annualization),
        ):
            if value < 1:
                raise ValueError(f"{name} must be positive")
        if self.trend_short_window >= self.trend_long_window:
            raise ValueError("trend_short_window must be below trend_long_window")
        if self.max_annualized_volatility <= 0:
            raise ValueError("max_annualized_volatility must be positive")
        if self.volatility_spike_ratio < 1.0:
            raise ValueError("volatility_spike_ratio must be at least 1.0")
        if self.min_avg_dollar_volume < 0 or self.min_avg_volume < 0:
            raise ValueError("liquidity thresholds cannot be negative")
        if self.risk_off_drawdown >= 0:
            raise ValueError("risk_off_drawdown must be negative")


@dataclass(frozen=True)
class WealthRegimeFilterResult:
    config: WealthRegimeFilterConfig
    filters: pd.DataFrame
    latest: dict[str, Any]
    safety: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "filter": FILTER_NAME,
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


def regime_filter_definitions() -> dict[str, str]:
    return {
        "volatility_filter_pass": "True when realized annualized volatility is below the configured ceiling and not in a short-term volatility spike.",
        "trend_filter_pass": "True when close is above the long moving average and the short moving average is at or above the long moving average.",
        "liquidity_filter_pass": "True when trailing average volume and dollar volume meet configured research thresholds.",
        "risk_off_filter_pass": "True when drawdown and optional external risk-off signal do not trip defensive mode.",
        "research_weight_multiplier": "Offline research multiplier: 1.0 when all filters pass, otherwise 0.0.",
        "filter_label": "RESEARCH_ONLY when all filters pass, otherwise BLOCKED_BY_SAFETY_GATE.",
    }


def build_wealth_regime_filters(
    market_data: pd.DataFrame | pd.Series,
    config: WealthRegimeFilterConfig | None = None,
    *,
    risk_off_signal: pd.Series | None = None,
) -> pd.DataFrame:
    cfg = config or WealthRegimeFilterConfig()
    cfg.validate()
    frame = _coerce_market_frame(market_data)
    close = frame["close"]
    returns = close.pct_change().fillna(0.0)

    realized_vol = (
        returns.rolling(cfg.volatility_window, min_periods=cfg.volatility_window).std(ddof=1)
        * sqrt(cfg.annualization)
    )
    long_vol = realized_vol.rolling(cfg.volatility_window * 3, min_periods=cfg.volatility_window).mean()
    vol_spike = realized_vol > (long_vol * cfg.volatility_spike_ratio)
    volatility_filter = (realized_vol <= cfg.max_annualized_volatility) & ~vol_spike.fillna(False)

    short_ma = close.rolling(cfg.trend_short_window, min_periods=cfg.trend_short_window).mean()
    long_ma = close.rolling(cfg.trend_long_window, min_periods=cfg.trend_long_window).mean()
    trend_filter = (close >= long_ma) & (short_ma >= long_ma)

    volume = frame["volume"]
    avg_volume = volume.rolling(cfg.liquidity_window, min_periods=cfg.liquidity_window).mean()
    avg_dollar_volume = (close * volume).rolling(
        cfg.liquidity_window,
        min_periods=cfg.liquidity_window,
    ).mean()
    liquidity_filter = (avg_volume >= cfg.min_avg_volume) & (
        avg_dollar_volume >= cfg.min_avg_dollar_volume
    )

    drawdown = close / close.cummax() - 1.0
    external_risk_off = _coerce_risk_off_signal(risk_off_signal, close.index)
    risk_off_filter = (drawdown >= cfg.risk_off_drawdown) & ~external_risk_off

    all_filters_pass = (
        volatility_filter.fillna(False)
        & trend_filter.fillna(False)
        & liquidity_filter.fillna(False)
        & risk_off_filter.fillna(False)
    )
    research_weight_multiplier = all_filters_pass.astype(float)
    filter_label = pd.Series(BLOCKED_BY_SAFETY_GATE, index=close.index, dtype=object)
    filter_label[all_filters_pass] = RESEARCH_ONLY

    return pd.DataFrame(
        {
            "close": close,
            "volume": volume,
            "return": returns,
            "realized_annualized_volatility": realized_vol,
            "volatility_spike": vol_spike.fillna(False).astype(bool),
            "volatility_filter_pass": volatility_filter.fillna(False).astype(bool),
            "short_trend_ma": short_ma,
            "long_trend_ma": long_ma,
            "trend_filter_pass": trend_filter.fillna(False).astype(bool),
            "avg_volume": avg_volume,
            "avg_dollar_volume": avg_dollar_volume,
            "liquidity_filter_pass": liquidity_filter.fillna(False).astype(bool),
            "drawdown": drawdown,
            "external_risk_off": external_risk_off.astype(bool),
            "risk_off_filter_pass": risk_off_filter.fillna(False).astype(bool),
            "all_filters_pass": all_filters_pass.astype(bool),
            "research_weight_multiplier": research_weight_multiplier,
            "filter_label": filter_label,
        }
    )


def evaluate_wealth_regime_filters(
    market_data: pd.DataFrame | pd.Series,
    config: WealthRegimeFilterConfig | None = None,
    *,
    risk_off_signal: pd.Series | None = None,
) -> WealthRegimeFilterResult:
    cfg = config or WealthRegimeFilterConfig()
    filters = build_wealth_regime_filters(market_data, cfg, risk_off_signal=risk_off_signal)
    latest = filters.iloc[-1].to_dict() if len(filters) else {}
    return WealthRegimeFilterResult(
        config=cfg,
        filters=filters,
        latest=latest,
        safety=safety_manifest(),
    )


def build_report_payload(result: WealthRegimeFilterResult) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "filter": FILTER_NAME,
        "safety": result.safety,
        "filter_definitions": regime_filter_definitions(),
        "config": {
            "volatility_window": result.config.volatility_window,
            "max_annualized_volatility": result.config.max_annualized_volatility,
            "volatility_spike_ratio": result.config.volatility_spike_ratio,
            "trend_short_window": result.config.trend_short_window,
            "trend_long_window": result.config.trend_long_window,
            "liquidity_window": result.config.liquidity_window,
            "min_avg_dollar_volume": result.config.min_avg_dollar_volume,
            "min_avg_volume": result.config.min_avg_volume,
            "risk_off_drawdown": result.config.risk_off_drawdown,
            "annualization": result.config.annualization,
        },
        "latest": result.latest,
        "observations": int(len(result.filters)),
        "pass_count": int(result.filters["all_filters_pass"].sum()) if len(result.filters) else 0,
    }


def render_markdown_report(result: WealthRegimeFilterResult) -> str:
    payload = build_report_payload(result)
    latest = payload["latest"]
    lines = [
        f"# {PHASE_ID} {FILTER_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Filter Definitions",
    ]
    for name, definition in payload["filter_definitions"].items():
        lines.append(f"- {name}: {definition}")

    lines.extend(
        [
            "",
            "## Latest State",
            f"- Filter label: {latest.get('filter_label')}",
            f"- All filters pass: {latest.get('all_filters_pass')}",
            f"- Research weight multiplier: {_format_metric(latest.get('research_weight_multiplier'))}",
            f"- Realized annualized volatility: {_format_metric(latest.get('realized_annualized_volatility'))}",
            f"- Drawdown: {_format_metric(latest.get('drawdown'))}",
            "",
            "## Safety",
            "- No broker imports, order routing, or order submission are used.",
            "- Filters emit deterministic research state only.",
            "- Trade-relevant interpretation requires human review.",
        ]
    )
    return "\n".join(lines)


def write_research_report(
    result: WealthRegimeFilterResult,
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


def _coerce_market_frame(market_data: pd.DataFrame | pd.Series) -> pd.DataFrame:
    if isinstance(market_data, pd.Series):
        frame = market_data.to_frame("close")
    else:
        frame = market_data.copy()
        rename = {}
        if "Close" in frame.columns and "close" not in frame.columns:
            rename["Close"] = "close"
        if "Volume" in frame.columns and "volume" not in frame.columns:
            rename["Volume"] = "volume"
        frame = frame.rename(columns=rename)

    if "close" not in frame.columns:
        raise ValueError("market_data must be a Series or contain a close/Close column")
    if "volume" not in frame.columns:
        frame["volume"] = 0.0

    frame = frame.loc[:, ["close", "volume"]].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["close"]).copy()
    frame["volume"] = frame["volume"].fillna(0.0)
    if frame.empty:
        raise ValueError("market_data must contain numeric close observations")
    return frame.astype(float)


def _coerce_risk_off_signal(risk_off_signal: pd.Series | None, index: pd.Index) -> pd.Series:
    if risk_off_signal is None:
        return pd.Series(False, index=index)
    aligned = risk_off_signal.reindex(index).fillna(False)
    return aligned.astype(bool)


def _format_metric(value: Any) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)
