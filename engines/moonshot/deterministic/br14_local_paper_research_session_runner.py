from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.br10c_config_driven_screener_pipeline import (
    ScreenerPipelineReport,
    load_screener_pipeline_report,
    screener_pipeline_payload,
    write_screener_pipeline_report,
)
from engines.moonshot.deterministic.candidate_universe_builder import (
    CandidateUniverseReport,
    load_candidate_universe_report,
    write_candidate_universe_report,
)
from engines.moonshot.deterministic.daily_position_monitor_alert_engine import (
    DailyPositionMonitorReport,
    PositionMonitorSnapshot,
    build_daily_position_monitor_report,
    write_daily_position_monitor_report,
)
from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    AnalystThesisReport,
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
    write_analyst_thesis_report,
)
from engines.moonshot.deterministic.local_operator_dashboard import (
    LocalOperatorDashboardReport,
    build_local_operator_dashboard_report,
    write_local_operator_dashboard_report,
)
from engines.moonshot.deterministic.options_chain_quality_scanner import (
    OptionsChainQualityReport,
    load_options_chain_quality_inputs,
    build_options_chain_quality_report,
    write_options_chain_quality_report,
)
from engines.moonshot.deterministic.options_contract_scorer import (
    ContractScoringReport,
    build_contract_scoring_report,
    write_contract_scoring_report,
)
from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionFill,
    PaperOptionGreeks,
    PaperOptionMark,
    PaperOptionsConfig,
    PaperOptionsPortfolioReport,
    build_paper_options_portfolio_report,
    write_paper_options_portfolio_report,
)
from engines.moonshot.deterministic.trade_score_risk_gate import (
    TradeScoreRiskGateReport,
    load_candidate_risk_contexts,
    build_trade_score_risk_gate_report,
    write_trade_score_risk_gate_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-14"
MODULE_NAME = "Local Paper Research Session Runner"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_REPORT_DIR = Path("reports/br14_local_paper_research_session_runner")
FORBIDDEN_RUNTIME_FLAGS = (
    "credential_loading_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class LocalPaperResearchSessionArtifacts:
    screener_pipeline_report: ScreenerPipelineReport
    candidate_universe_report: CandidateUniverseReport
    options_chain_quality_report: OptionsChainQualityReport
    contract_scoring_report: ContractScoringReport
    analyst_thesis_report: AnalystThesisReport
    trade_score_risk_gate_report: TradeScoreRiskGateReport
    paper_options_portfolio_report: PaperOptionsPortfolioReport
    daily_position_monitor_report: DailyPositionMonitorReport
    local_operator_dashboard_report: LocalOperatorDashboardReport

    def validate(self) -> None:
        self.screener_pipeline_report.validate()
        self.candidate_universe_report.validate()
        self.options_chain_quality_report.validate()
        self.contract_scoring_report.validate()
        self.analyst_thesis_report.validate()
        self.trade_score_risk_gate_report.validate()
        self.paper_options_portfolio_report.validate()
        self.daily_position_monitor_report.validate()
        self.local_operator_dashboard_report.validate()


@dataclass(frozen=True)
class LocalPaperResearchSessionReport:
    as_of: datetime
    artifacts: LocalPaperResearchSessionArtifacts
    written_artifacts: dict[str, tuple[str, str]]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        self.artifacts.validate()
        _require_safe_label(self.label)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("local paper research session runner must require human review")
        _validate_disabled_safety(self.safety)
        if self.written_artifacts and "session" not in self.written_artifacts:
            raise ValueError("written artifacts must include session report paths")


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
        "local_fixture_data_default": True,
        "end_to_end_dry_run_only": True,
        "static_artifacts_only": True,
        "paper_portfolio_updates_simulated": True,
        "credential_loading_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def run_local_paper_research_session(
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> LocalPaperResearchSessionReport:
    chains = load_options_chain_quality_inputs()
    report_as_of = as_of or max(chain.as_of for chain in chains)

    screener_report = load_screener_pipeline_report()
    candidate_report = load_candidate_universe_report()
    chain_report = build_options_chain_quality_report(chains, as_of=report_as_of)
    scoring_report = build_contract_scoring_report(chains, as_of=report_as_of)
    analyst_report = build_analyst_thesis_report(
        prompt_packages=None,
        response_text_by_prompt_id=load_fixture_analyst_responses(),
        as_of=report_as_of,
    )
    risk_report = build_trade_score_risk_gate_report(
        chain_quality_report=chain_report,
        contract_scoring_report=scoring_report,
        analyst_thesis_report=analyst_report,
        candidate_risk_contexts=load_candidate_risk_contexts(),
        as_of=report_as_of,
    )
    portfolio_report = build_paper_options_portfolio_report(
        fills=_paper_fills_from_risk_gate(risk_report, analyst_report, report_as_of),
        marks=_paper_marks_from_risk_gate(risk_report, report_as_of),
        as_of=report_as_of,
        config=PaperOptionsConfig(max_position_premium_pct=0.06),
    )
    monitor_report = build_daily_position_monitor_report(
        portfolio_report=portfolio_report,
        snapshots=_monitor_snapshots_from_portfolio(portfolio_report, risk_report, report_as_of),
        as_of=report_as_of,
    )
    dashboard_report = build_local_operator_dashboard_report(
        candidate_universe_report=candidate_report,
        trade_score_risk_gate_report=risk_report,
        paper_options_portfolio_report=portfolio_report,
        daily_position_monitor_report=monitor_report,
        analyst_thesis_report=analyst_report,
        as_of=report_as_of,
    )
    artifacts = LocalPaperResearchSessionArtifacts(
        screener_pipeline_report=screener_report,
        candidate_universe_report=candidate_report,
        options_chain_quality_report=chain_report,
        contract_scoring_report=scoring_report,
        analyst_thesis_report=analyst_report,
        trade_score_risk_gate_report=risk_report,
        paper_options_portfolio_report=portfolio_report,
        daily_position_monitor_report=monitor_report,
        local_operator_dashboard_report=dashboard_report,
    )
    report = LocalPaperResearchSessionReport(
        as_of=report_as_of,
        artifacts=artifacts,
        written_artifacts={},
        safety=safety_manifest(),
    )
    report.validate()
    written = write_local_paper_research_session_report(report, out_dir)
    final_report = LocalPaperResearchSessionReport(
        as_of=report.as_of,
        artifacts=report.artifacts,
        written_artifacts=written,
        safety=report.safety,
        label=report.label,
    )
    final_report.validate()
    return final_report


def local_paper_research_session_payload(report: LocalPaperResearchSessionReport) -> dict[str, Any]:
    report.validate()
    portfolio = report.artifacts.paper_options_portfolio_report
    monitor = report.artifacts.daily_position_monitor_report
    risk = report.artifacts.trade_score_risk_gate_report
    screener_payload = screener_pipeline_payload(report.artifacts.screener_pipeline_report)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "metrics": {
            "screener_queue_count": len(screener_payload["research_queue"]),
            "candidate_count": len(report.artifacts.candidate_universe_report.decisions),
            "chain_count": len(report.artifacts.options_chain_quality_report.chain_decisions),
            "contract_count": len(report.artifacts.contract_scoring_report.decisions),
            "analyst_prompt_package_count": len(report.artifacts.analyst_thesis_report.prompt_packages),
            "risk_gate_decision_count": len(risk.decisions),
            "simulated_paper_fill_count": len(portfolio.fills),
            "paper_position_count": len(portfolio.positions),
            "monitor_alert_count": len(monitor.alerts),
            "dashboard_candidate_count": len(report.artifacts.candidate_universe_report.decisions),
        },
        "session_flow": (
            "BR-10C",
            "BR-02",
            "BR-03",
            "BR-04",
            "BR-05",
            "BR-06",
            "BR-07",
            "BR-08",
            "BR-09",
        ),
        "paper_contract_ids": tuple(fill.contract_id for fill in portfolio.fills),
        "monitor_alert_ids": tuple(alert.alert_id for alert in monitor.alerts),
        "written_artifacts": report.written_artifacts,
        "safety": report.safety,
    }


def render_markdown_local_paper_research_session(report: LocalPaperResearchSessionReport) -> str:
    payload = local_paper_research_session_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Session Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Session Flow"])
    for phase in payload["session_flow"]:
        lines.append(f"- {phase}")

    lines.extend(["", "## Simulated Paper Contracts"])
    if payload["paper_contract_ids"]:
        for contract_id in payload["paper_contract_ids"]:
            lines.append(f"- {contract_id}")
    else:
        lines.append("- no_simulated_paper_contracts")

    lines.extend(["", "## Monitor Alerts"])
    if payload["monitor_alert_ids"]:
        for alert_id in payload["monitor_alert_ids"]:
            lines.append(f"- {alert_id}")
    else:
        lines.append("- no_monitor_alerts")

    lines.extend(
        [
            "",
            "## Safety",
            "- Local paper-only research session using fixture/sample data by default.",
            "- No credentials are loaded, requested, printed, modified, or exposed.",
            "- No broker connection, broker routing, broker calls, live trading, or order submission.",
            "- Trade-relevant artifacts remain HUMAN_REVIEW_REQUIRED.",
        ]
    )
    return "\n".join(lines)


def write_local_paper_research_session_report(
    report: LocalPaperResearchSessionReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> dict[str, tuple[str, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, tuple[Path, Path]] = {
        "screener": write_screener_pipeline_report(report.artifacts.screener_pipeline_report, out_dir / "br10c_screener"),
        "candidate_universe": write_candidate_universe_report(report.artifacts.candidate_universe_report, out_dir / "br02_candidate_universe"),
        "chain_quality": write_options_chain_quality_report(report.artifacts.options_chain_quality_report, out_dir / "br03_options_chain_quality"),
        "contract_scoring": write_contract_scoring_report(report.artifacts.contract_scoring_report, out_dir / "br04_contract_scoring"),
        "analyst_thesis": write_analyst_thesis_report(report.artifacts.analyst_thesis_report, out_dir / "br05_analyst_thesis"),
        "risk_gate": write_trade_score_risk_gate_report(report.artifacts.trade_score_risk_gate_report, out_dir / "br06_risk_gate"),
        "paper_portfolio": write_paper_options_portfolio_report(report.artifacts.paper_options_portfolio_report, out_dir / "br07_paper_portfolio"),
        "position_monitor": write_daily_position_monitor_report(report.artifacts.daily_position_monitor_report, out_dir / "br08_position_monitor"),
        "operator_dashboard": write_local_operator_dashboard_report(report.artifacts.local_operator_dashboard_report, out_dir / "br09_operator_dashboard"),
    }
    session_json = out_dir / "local_paper_research_session.json"
    session_md = out_dir / "local_paper_research_session.md"
    session_json.write_text(
        json.dumps(local_paper_research_session_payload(report), indent=2, default=str),
        encoding="utf-8",
    )
    session_md.write_text(render_markdown_local_paper_research_session(report), encoding="utf-8")
    written["session"] = (session_json, session_md)
    return {name: (str(paths[0]), str(paths[1])) for name, paths in written.items()}


def _paper_fills_from_risk_gate(
    risk_report: TradeScoreRiskGateReport,
    analyst_report: AnalystThesisReport,
    as_of: datetime,
) -> tuple[PaperOptionFill, ...]:
    thesis_by_symbol = {
        record.symbol: record.thesis_id
        for record in sorted(analyst_report.thesis_records, key=lambda item: (item.generated_at, item.thesis_id))
    }
    fills: list[PaperOptionFill] = []
    for index, decision in enumerate(
        (item for item in risk_report.decisions if item.label == PAPER_ONLY),
        start=1,
    ):
        contract = decision.contract_decision.contract
        fills.append(
            PaperOptionFill(
                fill_id=f"BR-14-PAPER-FILL-{index:03d}",
                contract_id=contract.contract_id,
                symbol=contract.symbol,
                underlying_symbol=contract.underlying_symbol,
                contract_type=contract.contract_type,
                strike=contract.strike,
                expiration=contract.expiration,
                filled_at=as_of,
                side="entry",
                contracts=1,
                fill_price=contract.mid,
                thesis_id=thesis_by_symbol.get(contract.underlying_symbol, f"BR-14-{contract.underlying_symbol}-HUMAN-REVIEW"),
                label=PAPER_ONLY,
            )
        )
    return tuple(fills)


def _paper_marks_from_risk_gate(
    risk_report: TradeScoreRiskGateReport,
    as_of: datetime,
) -> tuple[PaperOptionMark, ...]:
    marks: list[PaperOptionMark] = []
    for decision in risk_report.decisions:
        if decision.label != PAPER_ONLY:
            continue
        contract = decision.contract_decision.contract
        greeks = contract.greeks
        marks.append(
            PaperOptionMark(
                contract_id=contract.contract_id,
                marked_at=as_of,
                mark_price=round(contract.mid * 1.02, 4),
                greeks=PaperOptionGreeks(
                    delta=greeks.delta or 0.0,
                    gamma=greeks.gamma or 0.0,
                    theta=greeks.theta or 0.0,
                    vega=greeks.vega or 0.0,
                    rho=greeks.rho or 0.0,
                ),
                label=MONITOR_ONLY,
            )
        )
    return tuple(marks)


def _monitor_snapshots_from_portfolio(
    portfolio_report: PaperOptionsPortfolioReport,
    risk_report: TradeScoreRiskGateReport,
    as_of: datetime,
) -> tuple[PositionMonitorSnapshot, ...]:
    decision_by_contract = {
        decision.contract_decision.contract.contract_id: decision
        for decision in risk_report.decisions
    }
    snapshots: list[PositionMonitorSnapshot] = []
    for position in portfolio_report.positions:
        decision = decision_by_contract[position.contract_id]
        contract = decision.contract_decision.contract
        previous_underlying_price = decision.contract_decision.underlying_price
        snapshots.append(
            PositionMonitorSnapshot(
                contract_id=position.contract_id,
                observed_at=as_of,
                previous_underlying_price=previous_underlying_price,
                current_underlying_price=round(previous_underlying_price * 1.02, 4),
                previous_bid_ask_spread_pct=contract.spread_pct,
                current_bid_ask_spread_pct=round(contract.spread_pct + 0.005, 6),
                previous_implied_volatility=contract.implied_volatility or 0.01,
                current_implied_volatility=round((contract.implied_volatility or 0.01) * 1.04, 6),
                thesis_valid=True,
                thesis_status_note="local_fixture_thesis_still_valid",
                previous_risk_gate_label=decision.label,
                current_risk_gate_label=decision.label,
                risk_gate_reasons=decision.hard_block_reasons,
                label=MONITOR_ONLY,
            )
        )
    return tuple(snapshots)


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in FORBIDDEN_RUNTIME_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"local paper research session cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("local paper research session must keep LIVE TRADING disabled")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
