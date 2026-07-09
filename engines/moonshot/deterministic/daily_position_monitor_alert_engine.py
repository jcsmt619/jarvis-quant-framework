from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionPosition,
    PaperOptionsPortfolioReport,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-08"
MODULE_NAME = "Daily Position Monitor Alert Engine"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_REPORT_DIR = Path("reports/br08_daily_position_monitor_alert_engine")


@dataclass(frozen=True)
class DailyPositionMonitorConfig:
    theta_decay_alert_abs: float = 5.0
    near_expiration_dte: int = 120
    urgent_expiration_dte: int = 45
    max_bid_ask_spread_pct: float = 0.18
    spread_degradation_pct: float = 0.05
    volatility_change_pct: float = 0.20
    underlying_price_move_pct: float = 0.08

    def validate(self) -> None:
        _require_positive("theta_decay_alert_abs", self.theta_decay_alert_abs)
        if self.near_expiration_dte <= 0:
            raise ValueError("near_expiration_dte must be positive")
        if self.urgent_expiration_dte <= 0:
            raise ValueError("urgent_expiration_dte must be positive")
        if self.urgent_expiration_dte > self.near_expiration_dte:
            raise ValueError("urgent_expiration_dte cannot exceed near_expiration_dte")
        for field_name, value in (
            ("max_bid_ask_spread_pct", self.max_bid_ask_spread_pct),
            ("spread_degradation_pct", self.spread_degradation_pct),
            ("volatility_change_pct", self.volatility_change_pct),
            ("underlying_price_move_pct", self.underlying_price_move_pct),
        ):
            _require_positive(field_name, value)


@dataclass(frozen=True)
class PositionMonitorSnapshot:
    contract_id: str
    observed_at: datetime
    previous_underlying_price: float
    current_underlying_price: float
    previous_bid_ask_spread_pct: float
    current_bid_ask_spread_pct: float
    previous_implied_volatility: float
    current_implied_volatility: float
    thesis_valid: bool
    thesis_status_note: str
    previous_risk_gate_label: str
    current_risk_gate_label: str
    risk_gate_reasons: tuple[str, ...] = ()
    label: str = MONITOR_ONLY

    @property
    def underlying_price_move_pct(self) -> float:
        return _pct_change(self.previous_underlying_price, self.current_underlying_price)

    @property
    def implied_volatility_change_pct(self) -> float:
        return _pct_change(self.previous_implied_volatility, self.current_implied_volatility)

    @property
    def spread_change_pct(self) -> float:
        return round(self.current_bid_ask_spread_pct - self.previous_bid_ask_spread_pct, 6)

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_positive("previous_underlying_price", self.previous_underlying_price)
        _require_positive("current_underlying_price", self.current_underlying_price)
        _require_non_negative("previous_bid_ask_spread_pct", self.previous_bid_ask_spread_pct)
        _require_non_negative("current_bid_ask_spread_pct", self.current_bid_ask_spread_pct)
        _require_positive("previous_implied_volatility", self.previous_implied_volatility)
        _require_positive("current_implied_volatility", self.current_implied_volatility)
        _require_text("thesis_status_note", self.thesis_status_note)
        _require_safe_label(self.previous_risk_gate_label)
        _require_safe_label(self.current_risk_gate_label)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class DailyPositionAlert:
    alert_id: str
    contract_id: str
    underlying_symbol: str
    category: str
    severity: str
    reason: str
    observed_value: float | str
    threshold: float | str
    label: str = HUMAN_REVIEW_REQUIRED
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_call_performed: bool = False

    def validate(self) -> None:
        _require_text("alert_id", self.alert_id)
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.underlying_symbol)
        _require_text("category", self.category)
        if self.severity not in {"INFO", "WARN", "CRITICAL"}:
            raise ValueError("severity must be INFO, WARN, or CRITICAL")
        _require_text("reason", self.reason)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("daily position alerts must be human-review-required")
        if not self.human_review_required:
            raise ValueError("daily position alerts must require human review")
        if self.live_trading_enabled or self.broker_order_call_performed:
            raise ValueError("daily position alerts cannot enable trading or broker calls")


@dataclass(frozen=True)
class DailyPositionMonitorReport:
    as_of: datetime
    config: DailyPositionMonitorConfig
    portfolio_report: PaperOptionsPortfolioReport
    snapshots: tuple[PositionMonitorSnapshot, ...]
    alerts: tuple[DailyPositionAlert, ...]
    warnings: tuple[str, ...]
    safety: dict[str, Any]
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        self.config.validate()
        self.portfolio_report.validate()
        for snapshot in self.snapshots:
            snapshot.validate()
        for alert in self.alerts:
            alert.validate()
        _require_safe_label(self.label)
        if self.alerts and self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("reports with alerts must be human-review-required")
        if self.safety.get("live_trading_enabled") is not False:
            raise ValueError("daily position monitor cannot enable live trading")
        if self.safety.get("broker_order_call_performed") is not False:
            raise ValueError("daily position monitor cannot perform broker calls")


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "paper_positions_only": True,
        "human_review_alerts_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_daily_position_monitor_report(
    portfolio_report: PaperOptionsPortfolioReport,
    snapshots: tuple[PositionMonitorSnapshot, ...] | list[PositionMonitorSnapshot],
    as_of: datetime,
    config: DailyPositionMonitorConfig | None = None,
) -> DailyPositionMonitorReport:
    cfg = config or DailyPositionMonitorConfig()
    cfg.validate()
    portfolio_report.validate()
    ordered_snapshots = tuple(sorted(snapshots, key=lambda item: (item.contract_id, item.observed_at)))
    for snapshot in ordered_snapshots:
        snapshot.validate()

    latest_snapshots = _latest_snapshots(ordered_snapshots, as_of)
    alerts: list[DailyPositionAlert] = []
    warnings: list[str] = []
    for position in portfolio_report.positions:
        snapshot = latest_snapshots.get(position.contract_id)
        if snapshot is None:
            warnings.append(f"{position.contract_id}:missing_monitor_snapshot")
            alerts.append(
                _alert(
                    position,
                    "risk_gate_change",
                    "WARN",
                    "missing_daily_monitor_snapshot",
                    "missing",
                    "snapshot_required",
                )
            )
            continue
        alerts.extend(_alerts_for_position(position, snapshot, cfg, as_of))

    report = DailyPositionMonitorReport(
        as_of=as_of,
        config=cfg,
        portfolio_report=portfolio_report,
        snapshots=ordered_snapshots,
        alerts=tuple(sorted(alerts, key=lambda item: (item.contract_id, item.category, item.alert_id))),
        warnings=tuple(dict.fromkeys(warnings)),
        safety=safety_manifest(),
        label=HUMAN_REVIEW_REQUIRED if alerts else MONITOR_ONLY,
    )
    report.validate()
    return report


def daily_position_monitor_payload(report: DailyPositionMonitorReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "metrics": {
            "position_count": len(report.portfolio_report.positions),
            "snapshot_count": len(report.snapshots),
            "alert_count": len(report.alerts),
            "warning_count": len(report.warnings),
            "human_review_required_alert_count": len(
                tuple(alert for alert in report.alerts if alert.label == HUMAN_REVIEW_REQUIRED)
            ),
        },
        "alerts": [_alert_payload(alert) for alert in report.alerts],
        "warnings": report.warnings,
        "snapshots": [_snapshot_payload(snapshot) for snapshot in report.snapshots],
        "safety": report.safety,
    }


def render_markdown_daily_position_monitor(report: DailyPositionMonitorReport) -> str:
    payload = daily_position_monitor_payload(report)
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

    lines.extend(["", "## Human Review Alerts"])
    if not payload["alerts"]:
        lines.append("- no_daily_position_monitor_alerts")
    for alert in payload["alerts"]:
        lines.append(
            "- "
            + alert["contract_id"]
            + f": category={alert['category']}, severity={alert['severity']}, "
            + f"reason={alert['reason']}, label={alert['label']}"
        )

    lines.extend(["", "## Warnings"])
    if payload["warnings"]:
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_daily_position_monitor_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Daily monitor alert engine only; alerts are human-review-required.",
            "- Paper positions and local monitor snapshots only.",
            "- No broker routing, broker calls, live trading, or order submission.",
        ]
    )
    return "\n".join(lines)


def write_daily_position_monitor_report(
    report: DailyPositionMonitorReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "daily_position_monitor_alerts.json"
    md_path = out_dir / "daily_position_monitor_alerts.md"
    json_path.write_text(json.dumps(daily_position_monitor_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_daily_position_monitor(report), encoding="utf-8")
    return json_path, md_path


def _alerts_for_position(
    position: PaperOptionPosition,
    snapshot: PositionMonitorSnapshot,
    config: DailyPositionMonitorConfig,
    as_of: datetime,
) -> list[DailyPositionAlert]:
    dte = (position.expiration - as_of.date()).days
    alerts: list[DailyPositionAlert] = []
    if abs(position.theta_exposure) >= config.theta_decay_alert_abs:
        alerts.append(
            _alert(
                position,
                "theta_decay",
                "WARN",
                "theta_decay_threshold_reached",
                abs(position.theta_exposure),
                config.theta_decay_alert_abs,
            )
        )
    if dte <= config.urgent_expiration_dte:
        alerts.append(_alert(position, "dte_threshold", "CRITICAL", "urgent_dte_threshold_reached", dte, config.urgent_expiration_dte))
    elif dte <= config.near_expiration_dte:
        alerts.append(_alert(position, "dte_threshold", "WARN", "near_dte_threshold_reached", dte, config.near_expiration_dte))
    if snapshot.current_bid_ask_spread_pct >= config.max_bid_ask_spread_pct:
        alerts.append(
            _alert(
                position,
                "spread_degradation",
                "WARN",
                "bid_ask_spread_above_threshold",
                snapshot.current_bid_ask_spread_pct,
                config.max_bid_ask_spread_pct,
            )
        )
    if snapshot.spread_change_pct >= config.spread_degradation_pct:
        alerts.append(
            _alert(
                position,
                "spread_degradation",
                "WARN",
                "bid_ask_spread_degraded",
                snapshot.spread_change_pct,
                config.spread_degradation_pct,
            )
        )
    if not snapshot.thesis_valid:
        alerts.append(
            _alert(
                position,
                "thesis_invalidation",
                "CRITICAL",
                snapshot.thesis_status_note,
                "invalid",
                "valid_thesis_required",
            )
        )
    if abs(snapshot.implied_volatility_change_pct) >= config.volatility_change_pct:
        alerts.append(
            _alert(
                position,
                "volatility_change",
                "WARN",
                "implied_volatility_change_threshold_reached",
                snapshot.implied_volatility_change_pct,
                config.volatility_change_pct,
            )
        )
    if abs(snapshot.underlying_price_move_pct) >= config.underlying_price_move_pct:
        alerts.append(
            _alert(
                position,
                "price_move",
                "WARN",
                "underlying_price_move_threshold_reached",
                snapshot.underlying_price_move_pct,
                config.underlying_price_move_pct,
            )
        )
    if snapshot.current_risk_gate_label != snapshot.previous_risk_gate_label:
        alerts.append(
            _alert(
                position,
                "risk_gate_change",
                "CRITICAL" if snapshot.current_risk_gate_label == BLOCKED_BY_SAFETY_GATE else "WARN",
                "risk_gate_label_changed",
                f"{snapshot.previous_risk_gate_label}->{snapshot.current_risk_gate_label}",
                "stable_or_improved_gate_state",
            )
        )
    if snapshot.current_risk_gate_label == BLOCKED_BY_SAFETY_GATE:
        alerts.append(
            _alert(
                position,
                "risk_gate_change",
                "CRITICAL",
                ",".join(snapshot.risk_gate_reasons) or "risk_gate_blocked",
                snapshot.current_risk_gate_label,
                "non_blocked_risk_gate",
            )
        )
    return alerts


def _latest_snapshots(
    snapshots: tuple[PositionMonitorSnapshot, ...],
    as_of: datetime,
) -> dict[str, PositionMonitorSnapshot]:
    latest: dict[str, PositionMonitorSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.observed_at > as_of:
            continue
        current = latest.get(snapshot.contract_id)
        if current is None or snapshot.observed_at > current.observed_at:
            latest[snapshot.contract_id] = snapshot
    return latest


def _alert(
    position: PaperOptionPosition,
    category: str,
    severity: str,
    reason: str,
    observed_value: float | str,
    threshold: float | str,
) -> DailyPositionAlert:
    return DailyPositionAlert(
        alert_id=f"{position.contract_id}:{category}:{reason}",
        contract_id=position.contract_id,
        underlying_symbol=position.underlying_symbol,
        category=category,
        severity=severity,
        reason=reason,
        observed_value=observed_value,
        threshold=threshold,
    )


def _snapshot_payload(snapshot: PositionMonitorSnapshot) -> dict[str, Any]:
    return {
        "contract_id": snapshot.contract_id,
        "observed_at": snapshot.observed_at.isoformat(),
        "previous_underlying_price": snapshot.previous_underlying_price,
        "current_underlying_price": snapshot.current_underlying_price,
        "underlying_price_move_pct": snapshot.underlying_price_move_pct,
        "previous_bid_ask_spread_pct": snapshot.previous_bid_ask_spread_pct,
        "current_bid_ask_spread_pct": snapshot.current_bid_ask_spread_pct,
        "spread_change_pct": snapshot.spread_change_pct,
        "previous_implied_volatility": snapshot.previous_implied_volatility,
        "current_implied_volatility": snapshot.current_implied_volatility,
        "implied_volatility_change_pct": snapshot.implied_volatility_change_pct,
        "thesis_valid": snapshot.thesis_valid,
        "thesis_status_note": snapshot.thesis_status_note,
        "previous_risk_gate_label": snapshot.previous_risk_gate_label,
        "current_risk_gate_label": snapshot.current_risk_gate_label,
        "risk_gate_reasons": snapshot.risk_gate_reasons,
        "label": snapshot.label,
    }


def _alert_payload(alert: DailyPositionAlert) -> dict[str, Any]:
    return {
        "alert_id": alert.alert_id,
        "contract_id": alert.contract_id,
        "underlying_symbol": alert.underlying_symbol,
        "category": alert.category,
        "severity": alert.severity,
        "reason": alert.reason,
        "observed_value": alert.observed_value,
        "threshold": alert.threshold,
        "label": alert.label,
        "human_review_required": alert.human_review_required,
        "live_trading_enabled": alert.live_trading_enabled,
        "broker_order_call_performed": alert.broker_order_call_performed,
    }


def _pct_change(previous: float, current: float) -> float:
    if previous == 0:
        return 0.0
    return round((current - previous) / previous, 6)


def _require_symbol(symbol: str) -> None:
    _require_text("symbol", symbol)
    if symbol.strip() != symbol.strip().upper():
        raise ValueError("symbol must be uppercase")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(field_name: str, value: float | int) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float | int) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
