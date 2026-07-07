from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.leaps_research_engine import (
    LeapsResearchMemo,
    build_leaps_payload,
)
from engines.moonshot.deterministic.options_research import (
    OptionsResearchMemo,
    memo_payload,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "13E"
MODULE_NAME = "Options Monitor Dashboard"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/options_monitor_dashboard")


@dataclass(frozen=True)
class OptionsMonitorConfig:
    max_data_age_minutes: int = 30
    near_expiration_dte: int = 45
    high_abs_delta: float = 0.75
    max_theta_abs: float = 0.03
    max_bid_ask_spread_pct: float = 0.15
    min_open_interest: int = 100
    min_volume: int = 10

    def validate(self) -> None:
        if self.max_data_age_minutes < 0:
            raise ValueError("max_data_age_minutes cannot be negative")
        if self.near_expiration_dte <= 0:
            raise ValueError("near_expiration_dte must be positive")
        if not 0.0 < self.high_abs_delta <= 1.0:
            raise ValueError("high_abs_delta must be between 0 and 1")
        if self.max_theta_abs < 0:
            raise ValueError("max_theta_abs cannot be negative")
        if self.max_bid_ask_spread_pct < 0:
            raise ValueError("max_bid_ask_spread_pct cannot be negative")
        if self.min_open_interest < 0:
            raise ValueError("min_open_interest cannot be negative")
        if self.min_volume < 0:
            raise ValueError("min_volume cannot be negative")


@dataclass(frozen=True)
class OptionsMonitorRow:
    source_phase: str
    symbol: str
    contract_type: str
    strike: float
    expiration: str
    dte: int
    moneyness: str
    label: str
    monitor_allowed: bool
    alerts: tuple[str, ...]
    human_review_required: bool
    details: dict[str, Any]


@dataclass(frozen=True)
class OptionsMonitorDashboard:
    config: OptionsMonitorConfig
    rows: tuple[OptionsMonitorRow, ...]
    metrics: dict[str, int]
    safety: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
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


def build_options_monitor_dashboard(
    option_memos: list[OptionsResearchMemo] | tuple[OptionsResearchMemo, ...] = (),
    leaps_memos: list[LeapsResearchMemo] | tuple[LeapsResearchMemo, ...] = (),
    config: OptionsMonitorConfig | None = None,
) -> OptionsMonitorDashboard:
    cfg = config or OptionsMonitorConfig()
    cfg.validate()

    rows: list[OptionsMonitorRow] = []
    rows.extend(_row_from_options_memo(memo, cfg) for memo in option_memos)
    rows.extend(_row_from_leaps_memo(memo, cfg) for memo in leaps_memos)

    return OptionsMonitorDashboard(
        config=cfg,
        rows=tuple(rows),
        metrics=_dashboard_metrics(rows),
        safety=safety_manifest(),
    )


def build_dashboard_payload(dashboard: OptionsMonitorDashboard) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "safety": dashboard.safety,
        "config": {
            "max_data_age_minutes": dashboard.config.max_data_age_minutes,
            "near_expiration_dte": dashboard.config.near_expiration_dte,
            "high_abs_delta": dashboard.config.high_abs_delta,
            "max_theta_abs": dashboard.config.max_theta_abs,
            "max_bid_ask_spread_pct": dashboard.config.max_bid_ask_spread_pct,
            "min_open_interest": dashboard.config.min_open_interest,
            "min_volume": dashboard.config.min_volume,
        },
        "metrics": dashboard.metrics,
        "rows": [_row_payload(row) for row in dashboard.rows],
    }


def render_markdown_dashboard(dashboard: OptionsMonitorDashboard) -> str:
    payload = build_dashboard_payload(dashboard)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Monitor Rows"])
    if not payload["rows"]:
        lines.append("- no_options_under_monitor")
    for row in payload["rows"]:
        lines.append(
            "- "
            + row["symbol"]
            + f" {row['contract_type']} {row['strike']:.2f} {row['expiration']}: "
            + f"label={row['label']}, monitor_allowed={row['monitor_allowed']}, "
            + f"dte={row['dte']}, moneyness={row['moneyness']}"
        )
        if row["alerts"]:
            lines.append("  alerts: " + ", ".join(row["alerts"]))

    lines.extend(
        [
            "",
            "## Safety",
            "- Static monitor dashboard only; no broker routing or order submission.",
            "- Trade-relevant rows require human review.",
            "- Blocked rows stay visible for audit and monitoring context.",
        ]
    )
    return "\n".join(lines)


def write_options_monitor_report(
    dashboard: OptionsMonitorDashboard,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_dashboard_payload(dashboard)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_dashboard(dashboard), encoding="utf-8")
    return json_path, md_path


def _row_from_options_memo(
    memo: OptionsResearchMemo,
    config: OptionsMonitorConfig,
) -> OptionsMonitorRow:
    payload = memo_payload(memo)
    alerts = tuple(
        dict.fromkeys(
            [
                *_common_alerts(payload["dte"], payload["thesis"]["label"], config),
                *_greeks_alerts(payload["greeks"], config),
                *payload["risk_notes"],
            ]
        )
    )
    label = BLOCKED_BY_SAFETY_GATE if _has_blocking_alerts(alerts) else MONITOR_ONLY
    return OptionsMonitorRow(
        source_phase=payload["phase"],
        symbol=payload["symbol"],
        contract_type=payload["contract_type"],
        strike=float(payload["strike"]),
        expiration=payload["expiration"],
        dte=int(payload["dte"]),
        moneyness=payload["moneyness"],
        label=label,
        monitor_allowed=label == MONITOR_ONLY,
        alerts=alerts,
        human_review_required=True,
        details={
            "source_module": payload["module"],
            "expiration_bucket": payload["expiration_bucket"],
            "greeks": payload["greeks"],
            "thesis": payload["thesis"],
        },
    )


def _row_from_leaps_memo(
    memo: LeapsResearchMemo,
    config: OptionsMonitorConfig,
) -> OptionsMonitorRow:
    payload = build_leaps_payload(memo)
    alerts = tuple(
        dict.fromkeys(
            [
                *_common_alerts(payload["dte"], payload["research"]["label"], config),
                *_leaps_liquidity_alerts(payload["liquidity"], config),
                *payload["risk"]["warnings"],
            ]
        )
    )
    label = (
        MONITOR_ONLY
        if payload["monitor_allowed"] and not _has_blocking_alerts(alerts)
        else BLOCKED_BY_SAFETY_GATE
    )
    return OptionsMonitorRow(
        source_phase=payload["phase"],
        symbol=payload["symbol"],
        contract_type=payload["contract_type"],
        strike=float(payload["strike"]),
        expiration=payload["expiration"],
        dte=int(payload["dte"]),
        moneyness=payload["moneyness"],
        label=label,
        monitor_allowed=label == MONITOR_ONLY,
        alerts=alerts,
        human_review_required=True,
        details={
            "source_module": payload["module"],
            "expiration_bucket": payload["expiration_bucket"],
            "delta": payload["delta"],
            "liquidity": payload["liquidity"],
            "research": payload["research"],
        },
    )


def _common_alerts(dte: int, research_label: str, config: OptionsMonitorConfig) -> list[str]:
    alerts: list[str] = ["HUMAN_REVIEW_REQUIRED"]
    if dte <= config.near_expiration_dte:
        alerts.append("near_expiration_monitor_review")
    if research_label != HUMAN_REVIEW_REQUIRED:
        alerts.append("trade_relevant_research_should_remain_human_review_required")
    return alerts


def _greeks_alerts(greeks: dict[str, Any], config: OptionsMonitorConfig) -> list[str]:
    alerts: list[str] = []
    if abs(float(greeks["delta"])) >= config.high_abs_delta:
        alerts.append("high_delta_monitor_review")
    if abs(float(greeks["theta"])) >= config.max_theta_abs:
        alerts.append("theta_decay_monitor_review")
    return alerts


def _leaps_liquidity_alerts(liquidity: dict[str, Any], config: OptionsMonitorConfig) -> list[str]:
    alerts: list[str] = []
    if int(liquidity["data_age_minutes"]) > config.max_data_age_minutes:
        alerts.append("stale_options_data")
    if int(liquidity["open_interest"]) < config.min_open_interest:
        alerts.append("open_interest_liquidity_warning")
    if int(liquidity["volume"]) < config.min_volume:
        alerts.append("volume_liquidity_warning")
    if float(liquidity["bid_ask_spread_pct"]) > config.max_bid_ask_spread_pct:
        alerts.append("wide_bid_ask_spread_warning")
    return alerts


def _dashboard_metrics(rows: list[OptionsMonitorRow]) -> dict[str, int]:
    blocked = [row for row in rows if row.label == BLOCKED_BY_SAFETY_GATE]
    allowed = [row for row in rows if row.monitor_allowed]
    return {
        "row_count": len(rows),
        "monitor_allowed_count": len(allowed),
        "blocked_count": len(blocked),
        "human_review_required_count": sum(1 for row in rows if row.human_review_required),
        "alert_count": sum(len(row.alerts) for row in rows),
    }


def _has_blocking_alerts(alerts: tuple[str, ...]) -> bool:
    informational_prefixes = ("expiration_bucket=",)
    informational_alerts = {
        "HUMAN_REVIEW_REQUIRED",
        "implied_volatility_context_required",
    }
    return any(
        alert not in informational_alerts
        and not any(alert.startswith(prefix) for prefix in informational_prefixes)
        for alert in alerts
    )


def _row_payload(row: OptionsMonitorRow) -> dict[str, Any]:
    return {
        "source_phase": row.source_phase,
        "symbol": row.symbol,
        "contract_type": row.contract_type,
        "strike": row.strike,
        "expiration": row.expiration,
        "dte": row.dte,
        "moneyness": row.moneyness,
        "label": row.label,
        "monitor_allowed": row.monitor_allowed,
        "alerts": row.alerts,
        "human_review_required": row.human_review_required,
        "details": row.details,
    }
