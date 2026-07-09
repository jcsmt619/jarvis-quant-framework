from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.candidate_universe_builder import (
    CandidateUniverseReport,
    load_candidate_universe_report,
)
from engines.moonshot.deterministic.daily_position_monitor_alert_engine import (
    DailyPositionMonitorReport,
    PositionMonitorSnapshot,
    build_daily_position_monitor_report,
)
from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    AnalystThesisReport,
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
)
from engines.moonshot.deterministic.local_operator_dashboard import (
    LocalOperatorDashboardReport,
    build_local_operator_dashboard_report,
)
from engines.moonshot.deterministic.options_chain_quality_scanner import (
    OptionsChainQualityReport,
    build_options_chain_quality_report,
    load_options_chain_quality_inputs,
)
from engines.moonshot.deterministic.options_contract_scorer import (
    ContractScoringReport,
    build_contract_scoring_report,
)
from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionFill,
    PaperOptionGreeks,
    PaperOptionMark,
    PaperOptionsConfig,
    PaperOptionsPortfolioReport,
    build_paper_options_portfolio_report,
)
from engines.moonshot.deterministic.trade_score_risk_gate import (
    TradeScoreRiskGateReport,
    build_trade_score_risk_gate_report,
    load_candidate_risk_contexts,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-10"
MODULE_NAME = "Paper Autopilot Loop"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_REPORT_DIR = Path("reports/br10_paper_autopilot_loop")


@dataclass(frozen=True)
class PaperAutopilotLoopConfig:
    max_new_paper_positions: int = 2
    starting_cash: float = 100_000.0
    mark_price_multiplier: float = 1.02

    def validate(self) -> None:
        if self.max_new_paper_positions <= 0:
            raise ValueError("max_new_paper_positions must be positive")
        _require_positive("starting_cash", self.starting_cash)
        _require_positive("mark_price_multiplier", self.mark_price_multiplier)


@dataclass(frozen=True)
class PaperAutopilotLoopReport:
    as_of: datetime
    config: PaperAutopilotLoopConfig
    candidate_universe_report: CandidateUniverseReport
    options_chain_quality_report: OptionsChainQualityReport
    contract_scoring_report: ContractScoringReport
    analyst_thesis_report: AnalystThesisReport
    trade_score_risk_gate_report: TradeScoreRiskGateReport
    paper_options_portfolio_report: PaperOptionsPortfolioReport
    daily_position_monitor_report: DailyPositionMonitorReport
    local_operator_dashboard_report: LocalOperatorDashboardReport
    generated_fills: tuple[PaperOptionFill, ...]
    generated_marks: tuple[PaperOptionMark, ...]
    generated_snapshots: tuple[PositionMonitorSnapshot, ...]
    safety: dict[str, Any]
    label: str = PAPER_ONLY

    def validate(self) -> None:
        self.config.validate()
        self.candidate_universe_report.validate()
        self.options_chain_quality_report.validate()
        self.contract_scoring_report.validate()
        self.analyst_thesis_report.validate()
        self.trade_score_risk_gate_report.validate()
        self.paper_options_portfolio_report.validate()
        self.daily_position_monitor_report.validate()
        self.local_operator_dashboard_report.validate()
        for fill in self.generated_fills:
            fill.validate()
            if fill.label != PAPER_ONLY:
                raise ValueError("autopilot generated fills must be paper-only")
        for mark in self.generated_marks:
            mark.validate()
        for snapshot in self.generated_snapshots:
            snapshot.validate()
        _require_safe_label(self.label)
        _validate_disabled_safety(self.safety, "paper autopilot loop")
        for manifest in _child_safety_manifests(self):
            _validate_disabled_safety(manifest, "paper autopilot child report")


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
        "local_workflow_only": True,
        "candidate_scanning_enabled": True,
        "scoring_enabled": True,
        "paper_portfolio_updates_enabled": True,
        "monitor_alerts_enabled": True,
        "analyst_context_packaging_enabled": True,
        "dashboard_refresh_enabled": True,
        "simulated_fills_only": True,
        "local_marks_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def run_paper_autopilot_loop(
    config: PaperAutopilotLoopConfig | None = None,
    as_of: datetime | None = None,
) -> PaperAutopilotLoopReport:
    cfg = config or PaperAutopilotLoopConfig()
    cfg.validate()

    chains = load_options_chain_quality_inputs()
    chain_quality_report = build_options_chain_quality_report(chains)
    contract_scoring_report = build_contract_scoring_report(chains)
    analyst_thesis_report = build_analyst_thesis_report(
        response_text_by_prompt_id=load_fixture_analyst_responses()
    )
    trade_score_risk_gate_report = build_trade_score_risk_gate_report(
        chain_quality_report=chain_quality_report,
        contract_scoring_report=contract_scoring_report,
        analyst_thesis_report=analyst_thesis_report,
        candidate_risk_contexts=load_candidate_risk_contexts(),
    )
    candidate_universe_report = load_candidate_universe_report()
    report_as_of = as_of or max(
        candidate_universe_report.as_of,
        chain_quality_report.as_of,
        contract_scoring_report.as_of,
        analyst_thesis_report.as_of,
        trade_score_risk_gate_report.as_of,
    )

    fills = _paper_fills_from_gate(
        trade_score_risk_gate_report,
        analyst_thesis_report,
        report_as_of,
        cfg.max_new_paper_positions,
    )
    marks = _paper_marks_from_fills(fills, report_as_of, cfg.mark_price_multiplier)
    portfolio_report = build_paper_options_portfolio_report(
        fills,
        marks,
        report_as_of,
        PaperOptionsConfig(starting_cash=cfg.starting_cash, max_position_premium_pct=0.05),
    )
    snapshots = _monitor_snapshots_from_portfolio(
        portfolio_report,
        chain_quality_report,
        trade_score_risk_gate_report,
        report_as_of,
    )
    monitor_report = build_daily_position_monitor_report(portfolio_report, snapshots, report_as_of)
    dashboard_report = build_local_operator_dashboard_report(
        candidate_universe_report=candidate_universe_report,
        trade_score_risk_gate_report=trade_score_risk_gate_report,
        paper_options_portfolio_report=portfolio_report,
        daily_position_monitor_report=monitor_report,
        analyst_thesis_report=analyst_thesis_report,
        as_of=report_as_of,
    )
    report = PaperAutopilotLoopReport(
        as_of=report_as_of,
        config=cfg,
        candidate_universe_report=candidate_universe_report,
        options_chain_quality_report=chain_quality_report,
        contract_scoring_report=contract_scoring_report,
        analyst_thesis_report=analyst_thesis_report,
        trade_score_risk_gate_report=trade_score_risk_gate_report,
        paper_options_portfolio_report=portfolio_report,
        daily_position_monitor_report=monitor_report,
        local_operator_dashboard_report=dashboard_report,
        generated_fills=fills,
        generated_marks=marks,
        generated_snapshots=snapshots,
        safety=safety_manifest(),
        label=_loop_label(portfolio_report, monitor_report),
    )
    report.validate()
    return report


def paper_autopilot_loop_payload(report: PaperAutopilotLoopReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "metrics": {
            "candidate_count": len(report.candidate_universe_report.decisions),
            "included_candidate_count": len(report.candidate_universe_report.included_decisions),
            "chain_count": len(report.options_chain_quality_report.chain_decisions),
            "contract_score_count": len(report.contract_scoring_report.decisions),
            "risk_gate_decision_count": len(report.trade_score_risk_gate_report.decisions),
            "generated_fill_count": len(report.generated_fills),
            "generated_mark_count": len(report.generated_marks),
            "paper_position_count": len(report.paper_options_portfolio_report.positions),
            "monitor_alert_count": len(report.daily_position_monitor_report.alerts),
            "dashboard_candidate_count": len(report.local_operator_dashboard_report.candidate_universe_report.decisions),
            "analyst_prompt_package_count": len(report.analyst_thesis_report.prompt_packages),
            "analyst_thesis_record_count": len(report.analyst_thesis_report.thesis_records),
        },
        "paper_updates": {
            "fills": [_fill_payload(fill) for fill in report.generated_fills],
            "marks": [_mark_payload(mark) for mark in report.generated_marks],
            "snapshots": [_snapshot_payload(snapshot) for snapshot in report.generated_snapshots],
        },
        "workflow_outputs": {
            "candidate_universe_phase": report.candidate_universe_report.safety["phase"],
            "chain_quality_phase": report.options_chain_quality_report.safety["phase"],
            "contract_scoring_phase": report.contract_scoring_report.safety["phase"],
            "analyst_thesis_phase": report.analyst_thesis_report.safety["phase"],
            "risk_gate_phase": report.trade_score_risk_gate_report.safety["phase"],
            "paper_portfolio_phase": report.paper_options_portfolio_report.safety["phase"],
            "monitor_phase": report.daily_position_monitor_report.safety["phase"],
            "dashboard_phase": report.local_operator_dashboard_report.safety["phase"],
        },
        "safety": report.safety,
    }


def render_markdown_paper_autopilot_loop(report: PaperAutopilotLoopReport) -> str:
    payload = paper_autopilot_loop_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Workflow Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Paper Updates"])
    if not payload["paper_updates"]["fills"]:
        lines.append("- no_paper_autopilot_fills_generated")
    for fill in payload["paper_updates"]["fills"]:
        lines.append(
            "- "
            + fill["contract_id"]
            + f": contracts={fill['contracts']}, fill_price={fill['fill_price']:.2f}, "
            + f"label={fill['label']}"
        )

    lines.extend(
        [
            "",
            "## Safety",
            "- Local paper-only workflow for scanning, scoring, paper portfolio updates, alerts, analyst context, and dashboard refresh.",
            "- Generated fills are simulated paper fills only.",
            "- No broker routing, broker calls, live trading, or order submission.",
        ]
    )
    return "\n".join(lines)


def write_paper_autopilot_loop_report(
    report: PaperAutopilotLoopReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "paper_autopilot_loop.json"
    md_path = out_dir / "paper_autopilot_loop.md"
    json_path.write_text(json.dumps(paper_autopilot_loop_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_paper_autopilot_loop(report), encoding="utf-8")
    return json_path, md_path


def _paper_fills_from_gate(
    report: TradeScoreRiskGateReport,
    analyst_report: AnalystThesisReport,
    as_of: datetime,
    max_new_positions: int,
) -> tuple[PaperOptionFill, ...]:
    thesis_by_symbol = {
        record.symbol: record.thesis_id
        for record in sorted(analyst_report.thesis_records, key=lambda item: (item.generated_at, item.thesis_id))
    }
    selected = tuple(
        decision
        for decision in sorted(report.decisions, key=lambda item: (-item.score, item.risk_context.contract_id))
        if decision.label == PAPER_ONLY
    )[:max_new_positions]
    return tuple(
        PaperOptionFill(
            fill_id=f"BR-10-paper-fill-{index:03d}",
            contract_id=decision.contract_decision.contract.contract_id,
            symbol=decision.contract_decision.contract.symbol,
            underlying_symbol=decision.contract_decision.contract.underlying_symbol,
            contract_type=decision.contract_decision.contract.contract_type,
            strike=decision.contract_decision.contract.strike,
            expiration=decision.contract_decision.contract.expiration,
            filled_at=as_of,
            side="entry",
            contracts=1,
            fill_price=decision.contract_decision.contract.mid,
            thesis_id=thesis_by_symbol.get(decision.risk_context.symbol, "HUMAN_REVIEW_REQUIRED"),
            label=PAPER_ONLY,
        )
        for index, decision in enumerate(selected, start=1)
    )


def _paper_marks_from_fills(
    fills: tuple[PaperOptionFill, ...],
    as_of: datetime,
    mark_price_multiplier: float,
) -> tuple[PaperOptionMark, ...]:
    return tuple(
        PaperOptionMark(
            contract_id=fill.contract_id,
            marked_at=as_of,
            mark_price=round(fill.fill_price * mark_price_multiplier, 4),
            greeks=PaperOptionGreeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0),
            label=MONITOR_ONLY,
        )
        for fill in fills
    )


def _monitor_snapshots_from_portfolio(
    portfolio_report: PaperOptionsPortfolioReport,
    chain_quality_report: OptionsChainQualityReport,
    gate_report: TradeScoreRiskGateReport,
    as_of: datetime,
) -> tuple[PositionMonitorSnapshot, ...]:
    chain_by_symbol = {
        decision.chain.underlying_symbol: decision.chain
        for decision in chain_quality_report.chain_decisions
    }
    gate_by_contract = {
        decision.contract_decision.contract.contract_id: decision
        for decision in gate_report.decisions
    }
    snapshots: list[PositionMonitorSnapshot] = []
    for position in portfolio_report.positions:
        chain = chain_by_symbol[position.underlying_symbol]
        gate = gate_by_contract[position.contract_id]
        contract = gate.contract_decision.contract
        iv = contract.implied_volatility or 0.01
        snapshots.append(
            PositionMonitorSnapshot(
                contract_id=position.contract_id,
                observed_at=as_of,
                previous_underlying_price=chain.underlying_price,
                current_underlying_price=round(chain.underlying_price * 1.01, 4),
                previous_bid_ask_spread_pct=contract.spread_pct,
                current_bid_ask_spread_pct=contract.spread_pct,
                previous_implied_volatility=iv,
                current_implied_volatility=iv,
                thesis_valid=True,
                thesis_status_note="paper_autopilot_context_still_valid",
                previous_risk_gate_label=gate.label,
                current_risk_gate_label=gate.label,
                risk_gate_reasons=gate.hard_block_reasons,
                label=MONITOR_ONLY,
            )
        )
    return tuple(snapshots)


def _loop_label(
    portfolio_report: PaperOptionsPortfolioReport,
    monitor_report: DailyPositionMonitorReport,
) -> str:
    if portfolio_report.label == BLOCKED_BY_SAFETY_GATE:
        return BLOCKED_BY_SAFETY_GATE
    if monitor_report.label == HUMAN_REVIEW_REQUIRED:
        return HUMAN_REVIEW_REQUIRED
    return PAPER_ONLY


def _child_safety_manifests(report: PaperAutopilotLoopReport) -> tuple[dict[str, Any], ...]:
    return (
        report.candidate_universe_report.safety,
        report.options_chain_quality_report.safety,
        report.contract_scoring_report.safety,
        report.analyst_thesis_report.safety,
        report.trade_score_risk_gate_report.safety,
        report.paper_options_portfolio_report.safety,
        report.daily_position_monitor_report.safety,
        report.local_operator_dashboard_report.safety,
    )


def _validate_disabled_safety(manifest: dict[str, Any], owner: str) -> None:
    for field_name in (
        "real_paper_wrapper_connected",
        "real_paper_wrapper_attempted",
        "real_paper_order_submitted",
        "broker_order_call_performed",
        "broker_order_submitted",
        "broker_order_routing_enabled",
        "live_trading_enabled",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"{owner} cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError(f"{owner} must keep LIVE TRADING disabled")


def _fill_payload(fill: PaperOptionFill) -> dict[str, Any]:
    return {
        "fill_id": fill.fill_id,
        "contract_id": fill.contract_id,
        "symbol": fill.symbol,
        "underlying_symbol": fill.underlying_symbol,
        "contract_type": fill.contract_type,
        "strike": fill.strike,
        "expiration": fill.expiration.isoformat(),
        "filled_at": fill.filled_at.isoformat(),
        "side": fill.side,
        "contracts": fill.contracts,
        "fill_price": fill.fill_price,
        "premium": fill.premium,
        "thesis_id": fill.thesis_id,
        "label": fill.label,
        "simulated_fill": True,
    }


def _mark_payload(mark: PaperOptionMark) -> dict[str, Any]:
    return {
        "contract_id": mark.contract_id,
        "marked_at": mark.marked_at.isoformat(),
        "mark_price": mark.mark_price,
        "label": mark.label,
        "local_mark": True,
    }


def _snapshot_payload(snapshot: PositionMonitorSnapshot) -> dict[str, Any]:
    return {
        "contract_id": snapshot.contract_id,
        "observed_at": snapshot.observed_at.isoformat(),
        "previous_underlying_price": snapshot.previous_underlying_price,
        "current_underlying_price": snapshot.current_underlying_price,
        "previous_risk_gate_label": snapshot.previous_risk_gate_label,
        "current_risk_gate_label": snapshot.current_risk_gate_label,
        "thesis_valid": snapshot.thesis_valid,
        "label": snapshot.label,
    }


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
