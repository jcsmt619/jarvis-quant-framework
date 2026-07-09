from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    AnalystThesisReport,
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
)
from engines.moonshot.deterministic.options_chain_quality_scanner import (
    ChainQualityDecision,
    OptionsChainQualityReport,
    load_options_chain_quality_report,
)
from engines.moonshot.deterministic.options_contract_scorer import (
    ContractScoreDecision,
    ContractScoringReport,
    load_contract_scoring_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-06"
MODULE_NAME = "Deterministic Trade Score Risk Gate"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br06_trade_score_risk_gate.json")
DEFAULT_REPORT_DIR = Path("reports/br06_trade_score_risk_gate")


@dataclass(frozen=True)
class TradeScoreRiskGateConfig:
    min_chain_quality_score: int = 75
    min_contract_score: int = 75
    min_thesis_quality_score: int = 70
    min_monitor_score: int = 65
    min_human_review_score: int = 80
    min_paper_score: int = 90
    max_proposed_position_pct: float = 0.03
    max_symbol_concentration_pct: float = 0.06
    max_portfolio_drawdown_pct: float = 0.08
    max_candidate_drawdown_pct: float = 0.20
    min_days_to_catalyst: int = 14
    max_days_to_catalyst: int = 540

    def validate(self) -> None:
        for field_name, value in (
            ("min_chain_quality_score", self.min_chain_quality_score),
            ("min_contract_score", self.min_contract_score),
            ("min_thesis_quality_score", self.min_thesis_quality_score),
            ("min_monitor_score", self.min_monitor_score),
            ("min_human_review_score", self.min_human_review_score),
            ("min_paper_score", self.min_paper_score),
        ):
            _require_score(field_name, value)
        if not self.min_monitor_score <= self.min_human_review_score <= self.min_paper_score:
            raise ValueError("risk gate score thresholds must be ordered")
        for field_name, value in (
            ("max_proposed_position_pct", self.max_proposed_position_pct),
            ("max_symbol_concentration_pct", self.max_symbol_concentration_pct),
            ("max_portfolio_drawdown_pct", self.max_portfolio_drawdown_pct),
            ("max_candidate_drawdown_pct", self.max_candidate_drawdown_pct),
        ):
            _require_positive(field_name, value)
        if self.max_symbol_concentration_pct < self.max_proposed_position_pct:
            raise ValueError("max_symbol_concentration_pct cannot be below max_proposed_position_pct")
        if self.min_days_to_catalyst < 0:
            raise ValueError("min_days_to_catalyst cannot be negative")
        if self.max_days_to_catalyst < self.min_days_to_catalyst:
            raise ValueError("max_days_to_catalyst cannot be below min_days_to_catalyst")


@dataclass(frozen=True)
class CandidateRiskContext:
    contract_id: str
    symbol: str
    proposed_position_pct: float
    existing_symbol_exposure_pct: float
    portfolio_drawdown_pct: float
    candidate_drawdown_pct: float
    days_to_next_catalyst: int
    label: str = MONITOR_ONLY

    @property
    def total_symbol_exposure_pct(self) -> float:
        return round(self.proposed_position_pct + self.existing_symbol_exposure_pct, 6)

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        for field_name, value in (
            ("proposed_position_pct", self.proposed_position_pct),
            ("existing_symbol_exposure_pct", self.existing_symbol_exposure_pct),
            ("portfolio_drawdown_pct", self.portfolio_drawdown_pct),
            ("candidate_drawdown_pct", self.candidate_drawdown_pct),
        ):
            _require_non_negative(field_name, value)
        if self.days_to_next_catalyst < 0:
            raise ValueError("days_to_next_catalyst cannot be negative")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class RiskGateComponent:
    name: str
    score: int
    weight: int
    passed: bool
    reason: str

    def validate(self) -> None:
        _require_text("name", self.name)
        _require_score("score", self.score)
        if self.weight <= 0:
            raise ValueError("component weight must be positive")
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class TradeScoreRiskGateDecision:
    contract_decision: ContractScoreDecision
    chain_decision: ChainQualityDecision
    risk_context: CandidateRiskContext
    score: int
    label: str
    component_scores: tuple[RiskGateComponent, ...]
    hard_block_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]
    human_review_required: bool = True
    research_only: bool = True
    live_trading_enabled: bool = False
    broker_order_call_performed: bool = False

    def validate(self) -> None:
        self.contract_decision.validate()
        self.chain_decision.validate()
        self.risk_context.validate()
        if self.contract_decision.contract.contract_id != self.risk_context.contract_id:
            raise ValueError("risk context contract_id must match contract decision")
        if self.chain_decision.chain.underlying_symbol != self.risk_context.symbol:
            raise ValueError("risk context symbol must match chain decision")
        _require_score("score", self.score)
        if not self.component_scores:
            raise ValueError("risk gate decision requires component scores")
        for component in self.component_scores:
            component.validate()
        _require_safe_label(self.label)
        if self.hard_block_reasons and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("hard blocked decisions must be blocked by safety gate")
        if not self.human_review_required or not self.research_only:
            raise ValueError("risk gate decisions must remain research-only and human-review-required")
        if self.live_trading_enabled or self.broker_order_call_performed:
            raise ValueError("risk gate decisions cannot enable trading or broker calls")


@dataclass(frozen=True)
class TradeScoreRiskGateReport:
    as_of: datetime
    config: TradeScoreRiskGateConfig
    decisions: tuple[TradeScoreRiskGateDecision, ...]
    safety: dict[str, Any]
    label: str = BLOCKED_BY_SAFETY_GATE

    @property
    def blocked_decisions(self) -> tuple[TradeScoreRiskGateDecision, ...]:
        return tuple(decision for decision in self.decisions if decision.label == BLOCKED_BY_SAFETY_GATE)

    @property
    def non_blocked_decisions(self) -> tuple[TradeScoreRiskGateDecision, ...]:
        return tuple(decision for decision in self.decisions if decision.label != BLOCKED_BY_SAFETY_GATE)

    def validate(self) -> None:
        self.config.validate()
        if not self.decisions:
            raise ValueError("trade score risk gate report requires at least one decision")
        for decision in self.decisions:
            decision.validate()
        _require_safe_label(self.label)
        if self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("trade score risk gate report must remain blocked by safety gate")
        if self.safety.get("live_trading_enabled") is not False:
            raise ValueError("risk gate report cannot enable live trading")
        if self.safety.get("broker_order_call_performed") is not False:
            raise ValueError("risk gate report cannot perform broker calls")


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
        "deterministic_gate_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def load_candidate_risk_contexts(path: Path = DEFAULT_FIXTURE_PATH) -> tuple[CandidateRiskContext, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contexts = tuple(_risk_context_from_payload(item) for item in payload["candidate_risk_contexts"])
    if not contexts:
        raise ValueError("BR-06 fixture requires at least one candidate risk context")
    for context in contexts:
        context.validate()
    return contexts


def load_trade_score_risk_gate_report(
    path: Path = DEFAULT_FIXTURE_PATH,
    config: TradeScoreRiskGateConfig | None = None,
) -> TradeScoreRiskGateReport:
    contract_report = load_contract_scoring_report()
    analyst_report = build_analyst_thesis_report(response_text_by_prompt_id=load_fixture_analyst_responses())
    return build_trade_score_risk_gate_report(
        chain_quality_report=load_options_chain_quality_report(),
        contract_scoring_report=contract_report,
        analyst_thesis_report=analyst_report,
        candidate_risk_contexts=load_candidate_risk_contexts(path),
        config=config,
    )


def build_trade_score_risk_gate_report(
    chain_quality_report: OptionsChainQualityReport,
    contract_scoring_report: ContractScoringReport,
    analyst_thesis_report: AnalystThesisReport,
    candidate_risk_contexts: tuple[CandidateRiskContext, ...] | list[CandidateRiskContext],
    config: TradeScoreRiskGateConfig | None = None,
    as_of: datetime | None = None,
) -> TradeScoreRiskGateReport:
    cfg = config or TradeScoreRiskGateConfig()
    cfg.validate()
    chain_quality_report.validate()
    contract_scoring_report.validate()
    analyst_thesis_report.validate()
    contexts = tuple(candidate_risk_contexts)
    if not contexts:
        raise ValueError("trade score risk gate requires at least one candidate risk context")
    for context in contexts:
        context.validate()
    context_by_contract_id = {context.contract_id: context for context in contexts}
    if len(context_by_contract_id) != len(contexts):
        raise ValueError("candidate risk contexts must have unique contract_id values")

    chain_by_symbol = {decision.chain.underlying_symbol: decision for decision in chain_quality_report.chain_decisions}
    thesis_quality_by_symbol = _thesis_quality_by_symbol(analyst_thesis_report)
    decisions = tuple(
        _gate_decision(
            contract_decision=decision,
            chain_decision=chain_by_symbol[decision.contract.underlying_symbol],
            risk_context=context_by_contract_id[decision.contract.contract_id],
            thesis_quality_score=thesis_quality_by_symbol.get(decision.contract.underlying_symbol, 0),
            config=cfg,
        )
        for decision in sorted(contract_scoring_report.decisions, key=lambda item: item.contract.contract_id)
        if decision.contract.contract_id in context_by_contract_id
    )
    if not decisions:
        raise ValueError("trade score risk gate found no contracts matching risk contexts")
    report = TradeScoreRiskGateReport(
        as_of=as_of or max(chain_quality_report.as_of, contract_scoring_report.as_of, analyst_thesis_report.as_of),
        config=cfg,
        decisions=decisions,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def trade_score_risk_gate_payload(report: TradeScoreRiskGateReport) -> dict[str, Any]:
    report.validate()
    ordered = sorted(report.decisions, key=lambda item: (-item.score, item.contract_decision.contract.contract_id))
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "config": _config_payload(report.config),
        "metrics": {
            "candidate_count": len(report.decisions),
            "paper_only_count": len(tuple(item for item in report.decisions if item.label == PAPER_ONLY)),
            "human_review_required_count": len(tuple(item for item in report.decisions if item.label == HUMAN_REVIEW_REQUIRED)),
            "monitor_only_count": len(tuple(item for item in report.decisions if item.label == MONITOR_ONLY)),
            "research_only_count": len(tuple(item for item in report.decisions if item.label == RESEARCH_ONLY)),
            "blocked_count": len(report.blocked_decisions),
        },
        "decisions": [_decision_payload(decision) for decision in ordered],
    }


def render_markdown_trade_score_risk_gate(report: TradeScoreRiskGateReport) -> str:
    payload = trade_score_risk_gate_payload(report)
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

    lines.extend(["", "## Gate Decisions"])
    for decision in payload["decisions"]:
        lines.append(
            "- "
            + decision["contract_id"]
            + f": score={decision['score']}, label={decision['label']}, "
            + "hard_blocks="
            + ", ".join(decision["hard_block_reasons"])
        )

    lines.extend(["", "## Component Scores"])
    for decision in payload["decisions"]:
        lines.append("- " + decision["contract_id"])
        for component in decision["component_scores"]:
            lines.append(
                "  - "
                + component["name"]
                + f": score={component['score']}, weight={component['weight']}, reason={component['reason']}"
            )

    lines.extend(
        [
            "",
            "## Safety",
            "- Deterministic trade score risk gate only; no broker routing or order submission.",
            "- Candidate outputs remain research-only, monitor-only, paper-only, or human-review-required.",
            "- Report-level state remains blocked by safety gate.",
        ]
    )
    return "\n".join(lines)


def write_trade_score_risk_gate_report(
    report: TradeScoreRiskGateReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "trade_score_risk_gate.json"
    md_path = out_dir / "trade_score_risk_gate.md"
    json_path.write_text(json.dumps(trade_score_risk_gate_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_trade_score_risk_gate(report), encoding="utf-8")
    return json_path, md_path


def _gate_decision(
    contract_decision: ContractScoreDecision,
    chain_decision: ChainQualityDecision,
    risk_context: CandidateRiskContext,
    thesis_quality_score: int,
    config: TradeScoreRiskGateConfig,
) -> TradeScoreRiskGateDecision:
    components = (
        _component("chain_quality", chain_decision.score, 15, "chain_quality_score"),
        _component("contract_score", contract_decision.total_score, 20, "contract_total_score"),
        _component("greeks", _greeks_component_score(contract_decision), 15, "delta_theta_vega_iv_score"),
        _component("liquidity", _liquidity_component_score(contract_decision), 15, "spread_volume_open_interest_score"),
        _component("thesis_quality", thesis_quality_score, 15, "source_grounded_analyst_thesis_score"),
        _component("concentration", _concentration_score(risk_context, config), 8, "position_and_symbol_exposure_score"),
        _component("drawdown", _drawdown_score(risk_context, config), 7, "portfolio_and_candidate_drawdown_score"),
        _component("catalyst_timing", _catalyst_score(risk_context, config), 5, "days_to_next_catalyst_score"),
    )
    weighted_score = sum(component.score * component.weight for component in components)
    total_weight = sum(component.weight for component in components)
    score = int(round(weighted_score / total_weight))
    hard_blocks = _hard_block_reasons(
        contract_decision,
        chain_decision,
        risk_context,
        config,
    )
    review_reasons = _review_reasons(
        chain_decision,
        contract_decision,
        thesis_quality_score,
        risk_context,
        config,
    )
    label = _label_for_decision(score, hard_blocks, review_reasons, config)
    return TradeScoreRiskGateDecision(
        contract_decision=contract_decision,
        chain_decision=chain_decision,
        risk_context=risk_context,
        score=score,
        label=label,
        component_scores=components,
        hard_block_reasons=hard_blocks,
        review_reasons=review_reasons,
    )


def _label_for_decision(
    score: int,
    hard_blocks: tuple[str, ...],
    review_reasons: tuple[str, ...],
    config: TradeScoreRiskGateConfig,
) -> str:
    if hard_blocks:
        return BLOCKED_BY_SAFETY_GATE
    if review_reasons:
        return HUMAN_REVIEW_REQUIRED
    if score >= config.min_paper_score:
        return PAPER_ONLY
    if score >= config.min_human_review_score:
        return HUMAN_REVIEW_REQUIRED
    if score >= config.min_monitor_score:
        return MONITOR_ONLY
    return RESEARCH_ONLY


def _hard_block_reasons(
    contract_decision: ContractScoreDecision,
    chain_decision: ChainQualityDecision,
    risk_context: CandidateRiskContext,
    config: TradeScoreRiskGateConfig,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not chain_decision.passed or chain_decision.score < config.min_chain_quality_score:
        reasons.append("chain_quality_failed")
    if not contract_decision.suitable or contract_decision.total_score < config.min_contract_score:
        reasons.append("contract_score_failed")
    if risk_context.proposed_position_pct > config.max_proposed_position_pct:
        reasons.append("proposed_position_pct_above_maximum")
    if risk_context.total_symbol_exposure_pct > config.max_symbol_concentration_pct:
        reasons.append("symbol_concentration_above_maximum")
    if risk_context.portfolio_drawdown_pct > config.max_portfolio_drawdown_pct:
        reasons.append("portfolio_drawdown_above_maximum")
    if risk_context.candidate_drawdown_pct > config.max_candidate_drawdown_pct:
        reasons.append("candidate_drawdown_above_maximum")
    return tuple(reasons)


def _review_reasons(
    chain_decision: ChainQualityDecision,
    contract_decision: ContractScoreDecision,
    thesis_quality_score: int,
    risk_context: CandidateRiskContext,
    config: TradeScoreRiskGateConfig,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if chain_decision.score < config.min_chain_quality_score + 10:
        reasons.append("chain_quality_near_minimum")
    if contract_decision.total_score < config.min_contract_score + 10:
        reasons.append("contract_score_near_minimum")
    if thesis_quality_score < config.min_thesis_quality_score:
        reasons.append("thesis_quality_below_minimum")
    if risk_context.days_to_next_catalyst < config.min_days_to_catalyst:
        reasons.append("catalyst_too_near_for_new_risk")
    if risk_context.days_to_next_catalyst > config.max_days_to_catalyst:
        reasons.append("catalyst_too_distant_for_thesis")
    return tuple(reasons)


def _thesis_quality_by_symbol(report: AnalystThesisReport) -> dict[str, int]:
    scores: dict[str, int] = {}
    for record in report.thesis_records:
        confidence_score = {"high": 100, "medium": 80, "low": 60}.get(record.confidence.lower(), 40)
        evidence_bonus = min(10, len(record.source_citations) * 2)
        risk_bonus = 5 if record.risk_notes else 0
        catalyst_bonus = 5 if record.catalysts else 0
        score = min(100, confidence_score + evidence_bonus + risk_bonus + catalyst_bonus)
        scores[record.symbol] = max(scores.get(record.symbol, 0), score)
    return scores


def _greeks_component_score(contract_decision: ContractScoreDecision) -> int:
    components = {
        component.name: component.score
        for component in contract_decision.component_scores
        if component.name in {"delta", "theta", "vega", "implied_volatility"}
    }
    if not components:
        return 0
    return int(round(sum(components.values()) / len(components)))


def _liquidity_component_score(contract_decision: ContractScoreDecision) -> int:
    components = {
        component.name: component.score
        for component in contract_decision.component_scores
        if component.name in {"spread", "liquidity"}
    }
    if not components:
        return 0
    return int(round(sum(components.values()) / len(components)))


def _concentration_score(context: CandidateRiskContext, config: TradeScoreRiskGateConfig) -> int:
    if (
        context.proposed_position_pct > config.max_proposed_position_pct
        or context.total_symbol_exposure_pct > config.max_symbol_concentration_pct
    ):
        return 0
    exposure_ratio = context.total_symbol_exposure_pct / config.max_symbol_concentration_pct
    return max(50, int(round(100 - exposure_ratio * 40)))


def _drawdown_score(context: CandidateRiskContext, config: TradeScoreRiskGateConfig) -> int:
    if (
        context.portfolio_drawdown_pct > config.max_portfolio_drawdown_pct
        or context.candidate_drawdown_pct > config.max_candidate_drawdown_pct
    ):
        return 0
    portfolio_ratio = context.portfolio_drawdown_pct / config.max_portfolio_drawdown_pct
    candidate_ratio = context.candidate_drawdown_pct / config.max_candidate_drawdown_pct
    return max(50, int(round(100 - max(portfolio_ratio, candidate_ratio) * 40)))


def _catalyst_score(context: CandidateRiskContext, config: TradeScoreRiskGateConfig) -> int:
    if context.days_to_next_catalyst < config.min_days_to_catalyst:
        return 40
    if context.days_to_next_catalyst > config.max_days_to_catalyst:
        return 45
    midpoint = (config.min_days_to_catalyst + config.max_days_to_catalyst) / 2
    distance_ratio = abs(context.days_to_next_catalyst - midpoint) / max(midpoint, 1)
    return max(60, int(round(100 - distance_ratio * 25)))


def _component(name: str, score: int, weight: int, reason: str) -> RiskGateComponent:
    return RiskGateComponent(
        name=name,
        score=max(0, min(100, score)),
        weight=weight,
        passed=score >= 50,
        reason=reason,
    )


def _risk_context_from_payload(payload: dict[str, Any]) -> CandidateRiskContext:
    return CandidateRiskContext(
        contract_id=payload["contract_id"],
        symbol=payload["symbol"],
        proposed_position_pct=float(payload["proposed_position_pct"]),
        existing_symbol_exposure_pct=float(payload["existing_symbol_exposure_pct"]),
        portfolio_drawdown_pct=float(payload["portfolio_drawdown_pct"]),
        candidate_drawdown_pct=float(payload["candidate_drawdown_pct"]),
        days_to_next_catalyst=int(payload["days_to_next_catalyst"]),
        label=payload.get("label", MONITOR_ONLY),
    )


def _config_payload(config: TradeScoreRiskGateConfig) -> dict[str, Any]:
    return {
        "min_chain_quality_score": config.min_chain_quality_score,
        "min_contract_score": config.min_contract_score,
        "min_thesis_quality_score": config.min_thesis_quality_score,
        "min_monitor_score": config.min_monitor_score,
        "min_human_review_score": config.min_human_review_score,
        "min_paper_score": config.min_paper_score,
        "max_proposed_position_pct": config.max_proposed_position_pct,
        "max_symbol_concentration_pct": config.max_symbol_concentration_pct,
        "max_portfolio_drawdown_pct": config.max_portfolio_drawdown_pct,
        "max_candidate_drawdown_pct": config.max_candidate_drawdown_pct,
        "min_days_to_catalyst": config.min_days_to_catalyst,
        "max_days_to_catalyst": config.max_days_to_catalyst,
    }


def _decision_payload(decision: TradeScoreRiskGateDecision) -> dict[str, Any]:
    contract = decision.contract_decision.contract
    context = decision.risk_context
    return {
        "contract_id": contract.contract_id,
        "symbol": context.symbol,
        "score": decision.score,
        "label": decision.label,
        "component_scores": [_component_payload(component) for component in decision.component_scores],
        "hard_block_reasons": decision.hard_block_reasons,
        "review_reasons": decision.review_reasons,
        "chain_quality_score": decision.chain_decision.score,
        "contract_total_score": decision.contract_decision.total_score,
        "proposed_position_pct": context.proposed_position_pct,
        "existing_symbol_exposure_pct": context.existing_symbol_exposure_pct,
        "total_symbol_exposure_pct": context.total_symbol_exposure_pct,
        "portfolio_drawdown_pct": context.portfolio_drawdown_pct,
        "candidate_drawdown_pct": context.candidate_drawdown_pct,
        "days_to_next_catalyst": context.days_to_next_catalyst,
        "human_review_required": decision.human_review_required,
        "research_only": decision.research_only,
        "live_trading_enabled": decision.live_trading_enabled,
        "broker_order_call_performed": decision.broker_order_call_performed,
    }


def _component_payload(component: RiskGateComponent) -> dict[str, Any]:
    return {
        "name": component.name,
        "score": component.score,
        "weight": component.weight,
        "passed": component.passed,
        "reason": component.reason,
    }


def _require_score(field_name: str, value: int) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100")


def _require_symbol(symbol: str) -> None:
    _require_text("symbol", symbol)
    if symbol.strip() != symbol.strip().upper():
        raise ValueError("symbol must be uppercase")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float | int) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
