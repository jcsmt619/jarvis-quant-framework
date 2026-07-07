from __future__ import annotations

import math
from dataclasses import dataclass, field

from edge_hunting.funnel import FunnelThresholds, evaluate_funnel
from engines.strategy_cards import StrategyCard
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    ENGINE_RISK_POLICIES,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    EngineRiskPolicy,
    PolicyState,
    evaluate_policy,
)
from risk.promotion_gate import (
    PROMOTION_BLOCKED,
    PROMOTION_HUMAN_REVIEW_REQUIRED,
    PROMOTION_PAPER_ONLY,
    PROMOTION_RESEARCH_ONLY,
    PromotionGateDecision,
    PromotionGateEvidence,
    evaluate_promotion_gate,
)


CHALLENGER_BLOCKED = "challenger_blocked"
CHALLENGER_RESEARCH_ONLY = "challenger_research_only"
CHALLENGER_MONITOR_ONLY = "challenger_monitor_only"
CHALLENGER_PAPER_ONLY = "challenger_paper_only"
CHALLENGER_HUMAN_REVIEW_REQUIRED = "challenger_human_review_required"

SAFE_CHAMPION_CHALLENGER_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_CHAMPION_CHALLENGER_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)


@dataclass(frozen=True)
class StrategyOosMetrics:
    in_sample_sharpe: float
    oos_sharpe: float
    oos_max_drawdown: float
    oos_total_return: float
    trade_count: int
    oos_windows: int = 1
    positive_oos_windows: int = 1

    def validate(self) -> None:
        for field_name, value in (
            ("in_sample_sharpe", self.in_sample_sharpe),
            ("oos_sharpe", self.oos_sharpe),
            ("oos_max_drawdown", self.oos_max_drawdown),
            ("oos_total_return", self.oos_total_return),
        ):
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")
        if self.oos_max_drawdown > 0:
            raise ValueError("oos_max_drawdown must be zero or negative")
        if self.trade_count < 0:
            raise ValueError("trade_count must be non-negative")
        if self.oos_windows <= 0:
            raise ValueError("oos_windows must be positive")
        if self.positive_oos_windows < 0:
            raise ValueError("positive_oos_windows must be non-negative")
        if self.positive_oos_windows > self.oos_windows:
            raise ValueError("positive_oos_windows cannot exceed oos_windows")


@dataclass(frozen=True)
class ChampionChallengerThresholds:
    min_oos_sharpe_delta: float = 0.10
    min_total_return_delta: float = 0.0
    max_drawdown_tolerance: float = 0.0
    min_positive_oos_window_rate: float = 0.50
    funnel_thresholds: FunnelThresholds = field(default_factory=FunnelThresholds)

    def validate(self) -> None:
        if self.min_oos_sharpe_delta < 0:
            raise ValueError("min_oos_sharpe_delta cannot be negative")
        if self.min_positive_oos_window_rate < 0 or self.min_positive_oos_window_rate > 1:
            raise ValueError("min_positive_oos_window_rate must be between 0 and 1")
        if self.max_drawdown_tolerance < 0:
            raise ValueError("max_drawdown_tolerance cannot be negative")


@dataclass(frozen=True)
class OosPerformanceSummary:
    strategy_id: str
    in_sample_sharpe: float
    oos_sharpe: float
    oos_max_drawdown: float
    oos_total_return: float
    trade_count: int
    positive_oos_window_rate: float
    funnel_survived: bool
    funnel_failure: str


@dataclass(frozen=True)
class ChampionChallengerDecision:
    incumbent_strategy_id: str
    challenger_strategy_id: str
    engine: str
    label: str
    challenger_status: str
    reasons: tuple[str, ...]
    incumbent_summary: OosPerformanceSummary
    challenger_summary: OosPerformanceSummary
    oos_sharpe_delta: float
    oos_total_return_delta: float
    max_drawdown_delta: float
    promotion_gate: PromotionGateDecision
    risk_policy_compatible: bool
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False

    def validate(self) -> None:
        if not self.incumbent_strategy_id.strip():
            raise ValueError("decision requires incumbent_strategy_id")
        if not self.challenger_strategy_id.strip():
            raise ValueError("decision requires challenger_strategy_id")
        if not self.engine.strip():
            raise ValueError("decision requires engine")
        if self.label not in SAFE_CHAMPION_CHALLENGER_LABELS:
            raise ValueError(f"unsafe champion/challenger label: {self.label}")
        if self.label in DISALLOWED_CHAMPION_CHALLENGER_LABELS:
            raise ValueError(f"disallowed champion/challenger label: {self.label}")
        if self.challenger_status not in {
            CHALLENGER_BLOCKED,
            CHALLENGER_RESEARCH_ONLY,
            CHALLENGER_MONITOR_ONLY,
            CHALLENGER_PAPER_ONLY,
            CHALLENGER_HUMAN_REVIEW_REQUIRED,
        }:
            raise ValueError(f"unknown challenger status: {self.challenger_status}")
        if not self.reasons or any(not reason.strip() for reason in self.reasons):
            raise ValueError("decision requires non-empty reasons")
        if not self.human_review_required:
            raise ValueError("champion/challenger decisions must preserve human review")
        if self.live_trading_enabled:
            raise ValueError("champion/challenger cannot enable live trading")
        if self.broker_order_routing_enabled or self.broker_order_call_performed:
            raise ValueError("champion/challenger cannot enable or perform broker routing")


def evaluate_champion_challenger(
    *,
    incumbent: StrategyCard,
    challenger: StrategyCard,
    incumbent_metrics: StrategyOosMetrics,
    challenger_metrics: StrategyOosMetrics,
    challenger_policy_state: PolicyState,
    policy: EngineRiskPolicy | None = None,
    thresholds: ChampionChallengerThresholds | None = None,
) -> ChampionChallengerDecision:
    incumbent.validate()
    challenger.validate()
    incumbent_metrics.validate()
    challenger_metrics.validate()

    t = thresholds or ChampionChallengerThresholds()
    t.validate()

    selected_policy = policy or ENGINE_RISK_POLICIES.get(challenger.engine)
    if selected_policy is None:
        raise ValueError(f"missing risk policy for engine: {challenger.engine}")
    selected_policy.validate_static_safety()

    incumbent_summary = _build_summary(incumbent.card_id, incumbent_metrics, t)
    challenger_summary = _build_summary(challenger.card_id, challenger_metrics, t)
    sharpe_delta = challenger_metrics.oos_sharpe - incumbent_metrics.oos_sharpe
    return_delta = challenger_metrics.oos_total_return - incumbent_metrics.oos_total_return
    drawdown_delta = challenger_metrics.oos_max_drawdown - incumbent_metrics.oos_max_drawdown

    policy_decision = evaluate_policy(selected_policy, challenger_policy_state)
    gate_reasons = _gate_evidence_reasons(challenger_summary, challenger_metrics, t)
    gate_evidence = PromotionGateEvidence(
        validation_passed=not gate_reasons,
        unresolved_findings=gate_reasons,
    )
    promotion_gate = evaluate_promotion_gate(
        challenger,
        policy_decision,
        gate_evidence,
    )

    if incumbent.engine != challenger.engine:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=BLOCKED_BY_SAFETY_GATE,
            challenger_status=CHALLENGER_BLOCKED,
            reasons=("engine_mismatch_blocks_comparison",),
            risk_policy_compatible=False,
        )

    if selected_policy.engine != challenger.engine:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=BLOCKED_BY_SAFETY_GATE,
            challenger_status=CHALLENGER_BLOCKED,
            reasons=("risk_policy_engine_mismatch",),
            risk_policy_compatible=False,
        )

    if promotion_gate.promotion_status == PROMOTION_BLOCKED:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=BLOCKED_BY_SAFETY_GATE,
            challenger_status=CHALLENGER_BLOCKED,
            reasons=promotion_gate.reasons,
            risk_policy_compatible=False,
        )

    if promotion_gate.promotion_status == PROMOTION_RESEARCH_ONLY:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=RESEARCH_ONLY,
            challenger_status=CHALLENGER_RESEARCH_ONLY,
            reasons=promotion_gate.reasons,
        )

    if challenger.candidate_type == "non_deterministic":
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=HUMAN_REVIEW_REQUIRED,
            challenger_status=CHALLENGER_HUMAN_REVIEW_REQUIRED,
            reasons=("non_deterministic_challenger_requires_human_review",),
        )

    comparison_reasons = _comparison_reasons(
        incumbent_metrics,
        challenger_metrics,
        t,
    )
    if comparison_reasons:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=MONITOR_ONLY,
            challenger_status=CHALLENGER_MONITOR_ONLY,
            reasons=comparison_reasons,
        )

    if promotion_gate.promotion_status == PROMOTION_PAPER_ONLY:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=PAPER_ONLY,
            challenger_status=CHALLENGER_PAPER_ONLY,
            reasons=("beats_incumbent_but_paper_history_incomplete",),
        )

    if promotion_gate.promotion_status == PROMOTION_HUMAN_REVIEW_REQUIRED:
        return _decision(
            incumbent,
            challenger,
            incumbent_summary,
            challenger_summary,
            sharpe_delta,
            return_delta,
            drawdown_delta,
            promotion_gate,
            label=HUMAN_REVIEW_REQUIRED,
            challenger_status=CHALLENGER_HUMAN_REVIEW_REQUIRED,
            reasons=("beats_incumbent_and_requires_human_review",),
        )

    return _decision(
        incumbent,
        challenger,
        incumbent_summary,
        challenger_summary,
        sharpe_delta,
        return_delta,
        drawdown_delta,
        promotion_gate,
        label=BLOCKED_BY_SAFETY_GATE,
        challenger_status=CHALLENGER_BLOCKED,
        reasons=("unhandled_promotion_gate_status",),
        risk_policy_compatible=False,
    )


def _build_summary(
    strategy_id: str,
    metrics: StrategyOosMetrics,
    thresholds: ChampionChallengerThresholds,
) -> OosPerformanceSummary:
    verdict = evaluate_funnel(
        metrics.in_sample_sharpe,
        metrics.oos_sharpe,
        metrics.oos_max_drawdown,
        metrics.trade_count,
        thresholds.funnel_thresholds,
    )
    return OosPerformanceSummary(
        strategy_id=strategy_id,
        in_sample_sharpe=metrics.in_sample_sharpe,
        oos_sharpe=metrics.oos_sharpe,
        oos_max_drawdown=metrics.oos_max_drawdown,
        oos_total_return=metrics.oos_total_return,
        trade_count=metrics.trade_count,
        positive_oos_window_rate=metrics.positive_oos_windows / metrics.oos_windows,
        funnel_survived=verdict.survived,
        funnel_failure=verdict.failure_reason,
    )


def _gate_evidence_reasons(
    summary: OosPerformanceSummary,
    metrics: StrategyOosMetrics,
    thresholds: ChampionChallengerThresholds,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not summary.funnel_survived:
        reasons.append(f"oos_funnel_failed_{summary.funnel_failure}")
    if summary.positive_oos_window_rate < thresholds.min_positive_oos_window_rate:
        reasons.append("positive_oos_window_rate_below_minimum")
    if metrics.oos_total_return <= 0:
        reasons.append("non_positive_oos_total_return")
    return tuple(reasons)


def _comparison_reasons(
    incumbent_metrics: StrategyOosMetrics,
    challenger_metrics: StrategyOosMetrics,
    thresholds: ChampionChallengerThresholds,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        challenger_metrics.oos_sharpe - incumbent_metrics.oos_sharpe
        < thresholds.min_oos_sharpe_delta
    ):
        reasons.append("challenger_oos_sharpe_delta_below_minimum")
    if (
        challenger_metrics.oos_total_return - incumbent_metrics.oos_total_return
        < thresholds.min_total_return_delta
    ):
        reasons.append("challenger_oos_total_return_delta_below_minimum")
    if (
        challenger_metrics.oos_max_drawdown
        < incumbent_metrics.oos_max_drawdown - thresholds.max_drawdown_tolerance
    ):
        reasons.append("challenger_oos_drawdown_worse_than_incumbent")
    return tuple(reasons)


def _decision(
    incumbent: StrategyCard,
    challenger: StrategyCard,
    incumbent_summary: OosPerformanceSummary,
    challenger_summary: OosPerformanceSummary,
    sharpe_delta: float,
    return_delta: float,
    drawdown_delta: float,
    promotion_gate: PromotionGateDecision,
    *,
    label: str,
    challenger_status: str,
    reasons: tuple[str, ...],
    risk_policy_compatible: bool = True,
) -> ChampionChallengerDecision:
    decision = ChampionChallengerDecision(
        incumbent_strategy_id=incumbent.card_id,
        challenger_strategy_id=challenger.card_id,
        engine=challenger.engine,
        label=label,
        challenger_status=challenger_status,
        reasons=reasons,
        incumbent_summary=incumbent_summary,
        challenger_summary=challenger_summary,
        oos_sharpe_delta=sharpe_delta,
        oos_total_return_delta=return_delta,
        max_drawdown_delta=drawdown_delta,
        promotion_gate=promotion_gate,
        risk_policy_compatible=risk_policy_compatible,
    )
    decision.validate()
    return decision
