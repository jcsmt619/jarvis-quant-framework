from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.candidate_universe_builder import (
    CandidateUniverseReport,
)
from engines.moonshot.deterministic.daily_position_monitor_alert_engine import (
    DailyPositionMonitorReport,
)
from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    AnalystThesisReport,
)
from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionsPortfolioReport,
)
from engines.moonshot.deterministic.trade_score_risk_gate import (
    TradeScoreRiskGateReport,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-09"
MODULE_NAME = "Local Operator Dashboard"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_REPORT_DIR = Path("reports/br09_local_operator_dashboard")


@dataclass(frozen=True)
class LocalOperatorDashboardReport:
    as_of: datetime
    candidate_universe_report: CandidateUniverseReport
    trade_score_risk_gate_report: TradeScoreRiskGateReport
    paper_options_portfolio_report: PaperOptionsPortfolioReport
    daily_position_monitor_report: DailyPositionMonitorReport
    analyst_thesis_report: AnalystThesisReport
    safety: dict[str, Any]
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        self.candidate_universe_report.validate()
        self.trade_score_risk_gate_report.validate()
        self.paper_options_portfolio_report.validate()
        self.daily_position_monitor_report.validate()
        self.analyst_thesis_report.validate()
        _require_safe_label(self.label)
        if self.safety.get("read_only") is not True:
            raise ValueError("local operator dashboard must be read-only")
        if self.safety.get("static_output_only") is not True:
            raise ValueError("local operator dashboard must produce static output only")
        if self.safety.get("live_trading_enabled") is not False:
            raise ValueError("local operator dashboard cannot enable live trading")
        if self.safety.get("broker_order_call_performed") is not False:
            raise ValueError("local operator dashboard cannot perform broker calls")
        if self.safety.get("broker_order_routing_enabled") is not False:
            raise ValueError("local operator dashboard cannot enable broker routing")


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
        "read_only": True,
        "static_output_only": True,
        "local_reports_only": True,
        "operator_dashboard_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_local_operator_dashboard_report(
    candidate_universe_report: CandidateUniverseReport,
    trade_score_risk_gate_report: TradeScoreRiskGateReport,
    paper_options_portfolio_report: PaperOptionsPortfolioReport,
    daily_position_monitor_report: DailyPositionMonitorReport,
    analyst_thesis_report: AnalystThesisReport,
    as_of: datetime | None = None,
) -> LocalOperatorDashboardReport:
    candidate_universe_report.validate()
    trade_score_risk_gate_report.validate()
    paper_options_portfolio_report.validate()
    daily_position_monitor_report.validate()
    analyst_thesis_report.validate()
    report = LocalOperatorDashboardReport(
        as_of=as_of
        or max(
            candidate_universe_report.as_of,
            trade_score_risk_gate_report.as_of,
            paper_options_portfolio_report.as_of,
            daily_position_monitor_report.as_of,
            analyst_thesis_report.as_of,
        ),
        candidate_universe_report=candidate_universe_report,
        trade_score_risk_gate_report=trade_score_risk_gate_report,
        paper_options_portfolio_report=paper_options_portfolio_report,
        daily_position_monitor_report=daily_position_monitor_report,
        analyst_thesis_report=analyst_thesis_report,
        safety=safety_manifest(),
        label=_dashboard_label(daily_position_monitor_report),
    )
    report.validate()
    return report


def local_operator_dashboard_payload(report: LocalOperatorDashboardReport) -> dict[str, Any]:
    report.validate()
    positions_by_symbol = _positions_by_symbol(report.paper_options_portfolio_report)
    alerts_by_symbol = _alerts_by_symbol(report.daily_position_monitor_report)
    thesis_by_symbol = _thesis_by_symbol(report.analyst_thesis_report)
    risk_by_symbol = _risk_by_symbol(report.trade_score_risk_gate_report)
    candidate_rows = [
        _candidate_row(decision, risk_by_symbol, positions_by_symbol, alerts_by_symbol, thesis_by_symbol)
        for decision in sorted(
            report.candidate_universe_report.decisions,
            key=lambda item: (-item.score, item.candidate.symbol),
        )
    ]
    positions = [
        _position_row(position)
        for position in sorted(
            report.paper_options_portfolio_report.positions,
            key=lambda item: (item.underlying_symbol, item.contract_id),
        )
    ]
    alerts = [
        _alert_row(alert)
        for alert in sorted(
            report.daily_position_monitor_report.alerts,
            key=lambda item: (item.severity, item.contract_id, item.category, item.alert_id),
        )
    ]
    thesis_notes = [
        _thesis_row(record)
        for record in sorted(
            report.analyst_thesis_report.thesis_records,
            key=lambda item: (item.symbol, item.thesis_id),
        )
    ]
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "metrics": {
            "candidate_count": len(candidate_rows),
            "included_candidate_count": len(report.candidate_universe_report.included_decisions),
            "paper_position_count": len(positions),
            "alert_count": len(alerts),
            "thesis_note_count": len(thesis_notes),
            "total_pnl": report.paper_options_portfolio_report.total_pnl,
            "unrealized_pnl": report.paper_options_portfolio_report.unrealized_pnl,
            "realized_pnl": report.paper_options_portfolio_report.realized_pnl,
        },
        "candidates": candidate_rows,
        "paper_positions": positions,
        "alerts": alerts,
        "thesis_notes": thesis_notes,
        "portfolio_pnl": {
            "cash": report.paper_options_portfolio_report.cash,
            "realized_pnl": report.paper_options_portfolio_report.realized_pnl,
            "unrealized_pnl": report.paper_options_portfolio_report.unrealized_pnl,
            "total_pnl": report.paper_options_portfolio_report.total_pnl,
            "net_liquidation_value": report.paper_options_portfolio_report.exposure.net_liquidation_value,
        },
        "safety_status": report.safety,
    }


def render_markdown_local_operator_dashboard(report: LocalOperatorDashboardReport) -> str:
    payload = local_operator_dashboard_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Operator Summary",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Candidates"])
    if not payload["candidates"]:
        lines.append("- no_dashboard_candidates")
    for candidate in payload["candidates"]:
        lines.append(
            "- "
            + candidate["symbol"]
            + f": candidate_score={candidate['candidate_score']}, "
            + f"risk_score={candidate['risk_score']}, "
            + f"position_count={candidate['paper_position_count']}, "
            + f"alert_count={candidate['alert_count']}, label={candidate['label']}"
        )

    lines.extend(["", "## Paper Positions"])
    if not payload["paper_positions"]:
        lines.append("- no_open_paper_positions")
    for position in payload["paper_positions"]:
        lines.append(
            "- "
            + position["contract_id"]
            + f": contracts={position['contracts']}, market_value={position['market_value']:.2f}, "
            + f"unrealized_pnl={position['unrealized_pnl']:.2f}, label={position['label']}"
        )

    lines.extend(["", "## Alerts"])
    if not payload["alerts"]:
        lines.append("- no_local_operator_dashboard_alerts")
    for alert in payload["alerts"]:
        lines.append(
            "- "
            + alert["contract_id"]
            + f": severity={alert['severity']}, category={alert['category']}, "
            + f"reason={alert['reason']}, label={alert['label']}"
        )

    lines.extend(["", "## Thesis Notes"])
    if not payload["thesis_notes"]:
        lines.append("- no_thesis_notes")
    for note in payload["thesis_notes"]:
        lines.append(
            "- "
            + note["thesis_id"]
            + f": symbol={note['symbol']}, confidence={note['confidence']}, label={note['label']}"
        )
        lines.append("  summary: " + note["summary"])

    lines.extend(
        [
            "",
            "## Safety Status",
            "- Read-only local operator dashboard; static JSON and Markdown output only.",
            "- Consumes local research, paper, monitor, alert, and thesis reports.",
            "- No broker routing, broker calls, live trading, or order submission.",
        ]
    )
    return "\n".join(lines)


def write_local_operator_dashboard_report(
    report: LocalOperatorDashboardReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "local_operator_dashboard.json"
    md_path = out_dir / "local_operator_dashboard.md"
    json_path.write_text(json.dumps(local_operator_dashboard_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_local_operator_dashboard(report), encoding="utf-8")
    return json_path, md_path


def _dashboard_label(daily_position_monitor_report: DailyPositionMonitorReport) -> str:
    if daily_position_monitor_report.alerts:
        return HUMAN_REVIEW_REQUIRED
    return MONITOR_ONLY


def _candidate_row(
    decision: Any,
    risk_by_symbol: dict[str, dict[str, Any]],
    positions_by_symbol: dict[str, list[Any]],
    alerts_by_symbol: dict[str, list[Any]],
    thesis_by_symbol: dict[str, Any],
) -> dict[str, Any]:
    symbol = decision.candidate.symbol
    risk = risk_by_symbol.get(symbol, {})
    thesis = thesis_by_symbol.get(symbol)
    positions = positions_by_symbol.get(symbol, [])
    alerts = alerts_by_symbol.get(symbol, [])
    return {
        "symbol": symbol,
        "name": decision.candidate.name,
        "included": decision.included,
        "candidate_score": decision.score,
        "risk_score": risk.get("best_score"),
        "risk_label": risk.get("best_label"),
        "paper_position_count": len(positions),
        "paper_market_value": round(sum(position.market_value for position in positions), 2),
        "paper_unrealized_pnl": round(sum(position.unrealized_pnl for position in positions), 2),
        "alert_count": len(alerts),
        "thesis_id": thesis.thesis_id if thesis else None,
        "thesis_confidence": thesis.confidence if thesis else None,
        "label": _combine_label(decision.label, risk.get("best_label"), HUMAN_REVIEW_REQUIRED if alerts else None),
        "human_review_required": True,
    }


def _position_row(position: Any) -> dict[str, Any]:
    return {
        "contract_id": position.contract_id,
        "symbol": position.symbol,
        "underlying_symbol": position.underlying_symbol,
        "contracts": position.contracts,
        "average_price": position.average_price,
        "mark_price": position.mark_price,
        "market_value": position.market_value,
        "unrealized_pnl": position.unrealized_pnl,
        "unrealized_pnl_pct": position.unrealized_pnl_pct,
        "theta_exposure": position.theta_exposure,
        "vega_exposure": position.vega_exposure,
        "label": position.label,
        "human_review_required": position.human_review_required,
    }


def _alert_row(alert: Any) -> dict[str, Any]:
    return {
        "alert_id": alert.alert_id,
        "contract_id": alert.contract_id,
        "underlying_symbol": alert.underlying_symbol,
        "category": alert.category,
        "severity": alert.severity,
        "reason": alert.reason,
        "label": alert.label,
        "human_review_required": alert.human_review_required,
        "live_trading_enabled": alert.live_trading_enabled,
        "broker_order_call_performed": alert.broker_order_call_performed,
    }


def _thesis_row(record: Any) -> dict[str, Any]:
    return {
        "thesis_id": record.thesis_id,
        "symbol": record.symbol,
        "summary": record.thesis_summary,
        "confidence": record.confidence,
        "catalysts": record.catalysts,
        "invalidation_triggers": record.invalidation_triggers,
        "risk_notes": record.risk_notes,
        "label": record.label,
        "research_only": record.research_only,
        "human_review_required": record.human_review_required,
        "live_trading_enabled": record.live_trading_enabled,
        "broker_order_call_performed": record.broker_order_call_performed,
    }


def _positions_by_symbol(report: PaperOptionsPortfolioReport) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for position in report.positions:
        grouped.setdefault(position.underlying_symbol, []).append(position)
    return grouped


def _alerts_by_symbol(report: DailyPositionMonitorReport) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for alert in report.alerts:
        grouped.setdefault(alert.underlying_symbol, []).append(alert)
    return grouped


def _thesis_by_symbol(report: AnalystThesisReport) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for record in sorted(report.thesis_records, key=lambda item: (item.generated_at, item.thesis_id)):
        latest[record.symbol] = record
    return latest


def _risk_by_symbol(report: TradeScoreRiskGateReport) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for decision in report.decisions:
        symbol = decision.risk_context.symbol
        current = grouped.get(symbol)
        if current is None or decision.score > int(current["best_score"]):
            grouped[symbol] = {
                "best_score": decision.score,
                "best_label": decision.label,
                "contract_id": decision.risk_context.contract_id,
            }
    return grouped


def _combine_label(*labels: str | None) -> str:
    clean = {label for label in labels if label is not None}
    if BLOCKED_BY_SAFETY_GATE in clean:
        return BLOCKED_BY_SAFETY_GATE
    if HUMAN_REVIEW_REQUIRED in clean:
        return HUMAN_REVIEW_REQUIRED
    if PAPER_ONLY in clean:
        return PAPER_ONLY
    if MONITOR_ONLY in clean:
        return MONITOR_ONLY
    return RESEARCH_ONLY


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
