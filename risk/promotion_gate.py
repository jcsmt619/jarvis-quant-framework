from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    PolicyDecision,
)

if TYPE_CHECKING:
    from engines.strategy_cards import StrategyCard


PROMOTION_BLOCKED = "blocked_by_safety_gate"
PROMOTION_RESEARCH_ONLY = "research_only"
PROMOTION_PAPER_ONLY = "paper_only"
PROMOTION_HUMAN_REVIEW_REQUIRED = "human_review_required"

SAFE_PROMOTION_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_PROMOTION_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)


@dataclass(frozen=True)
class PromotionGateEvidence:
    validation_passed: bool = False
    unresolved_findings: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not isinstance(self.validation_passed, bool):
            raise ValueError("validation_passed must be a bool")
        if not isinstance(self.unresolved_findings, tuple):
            raise ValueError("unresolved_findings must be a tuple")
        if any(
            not isinstance(finding, str) or not finding.strip()
            for finding in self.unresolved_findings
        ):
            raise ValueError("unresolved_findings values must be non-empty strings")


@dataclass(frozen=True)
class PromotionGateDecision:
    strategy_id: str
    engine: str
    label: str
    promotion_status: str
    reasons: tuple[str, ...]
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False

    def validate(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("promotion gate decision requires strategy_id")
        if not self.engine.strip():
            raise ValueError("promotion gate decision requires engine")
        if self.label not in SAFE_PROMOTION_LABELS:
            raise ValueError(f"unsafe promotion gate label: {self.label}")
        if self.label in DISALLOWED_PROMOTION_LABELS:
            raise ValueError(f"disallowed promotion gate label: {self.label}")
        if self.promotion_status not in {
            PROMOTION_BLOCKED,
            PROMOTION_RESEARCH_ONLY,
            PROMOTION_PAPER_ONLY,
            PROMOTION_HUMAN_REVIEW_REQUIRED,
        }:
            raise ValueError(f"unknown promotion status: {self.promotion_status}")
        if not self.reasons:
            raise ValueError("promotion gate decision requires reasons")
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("promotion gate reasons must be non-empty")
        if not self.human_review_required:
            raise ValueError("promotion gate must preserve human review")
        if self.live_trading_enabled:
            raise ValueError("promotion gate cannot enable live trading")
        if self.broker_order_routing_enabled or self.broker_order_call_performed:
            raise ValueError("promotion gate cannot enable or perform broker routing")


def evaluate_promotion_gate(
    strategy: StrategyCard,
    policy_decision: PolicyDecision,
    evidence: PromotionGateEvidence | None = None,
) -> PromotionGateDecision:
    strategy.validate()
    gate_evidence = evidence or PromotionGateEvidence()
    gate_evidence.validate()

    if policy_decision.label not in SAFE_PROMOTION_LABELS:
        raise ValueError(f"unsafe policy label: {policy_decision.label}")
    if policy_decision.label in DISALLOWED_PROMOTION_LABELS:
        raise ValueError(f"disallowed policy label: {policy_decision.label}")

    if (
        strategy.live_trading_enabled
        or policy_decision.live_trading_enabled
        or strategy.broker_order_routing_enabled
        or strategy.broker_order_call_performed
        or policy_decision.broker_order_routing_enabled
    ):
        return _decision(
            strategy,
            label=BLOCKED_BY_SAFETY_GATE,
            promotion_status=PROMOTION_BLOCKED,
            reasons=("safety_execution_boundary_breach",),
        )

    if not policy_decision.allowed:
        return _decision(
            strategy,
            label=BLOCKED_BY_SAFETY_GATE,
            promotion_status=PROMOTION_BLOCKED,
            reasons=("policy_gate_blocked", *policy_decision.reasons),
        )

    if gate_evidence.unresolved_findings:
        return _decision(
            strategy,
            label=RESEARCH_ONLY,
            promotion_status=PROMOTION_RESEARCH_ONLY,
            reasons=("unresolved_findings", *gate_evidence.unresolved_findings),
        )

    if strategy.candidate_type == "non_deterministic":
        return _decision(
            strategy,
            label=HUMAN_REVIEW_REQUIRED,
            promotion_status=PROMOTION_HUMAN_REVIEW_REQUIRED,
            reasons=("non_deterministic_trade_relevant_review",),
        )

    if not gate_evidence.validation_passed:
        return _decision(
            strategy,
            label=RESEARCH_ONLY,
            promotion_status=PROMOTION_RESEARCH_ONLY,
            reasons=("validation_not_passed",),
        )

    if not policy_decision.promotion_eligible:
        return _decision(
            strategy,
            label=PAPER_ONLY,
            promotion_status=PROMOTION_PAPER_ONLY,
            reasons=("paper_history_requirement_not_met",),
        )

    return _decision(
        strategy,
        label=HUMAN_REVIEW_REQUIRED,
        promotion_status=PROMOTION_HUMAN_REVIEW_REQUIRED,
        reasons=("eligible_for_human_review",),
    )


def _decision(
    strategy: StrategyCard,
    *,
    label: str,
    promotion_status: str,
    reasons: tuple[str, ...],
) -> PromotionGateDecision:
    decision = PromotionGateDecision(
        strategy_id=strategy.card_id,
        engine=strategy.engine,
        label=label,
        promotion_status=promotion_status,
        reasons=reasons,
    )
    decision.validate()
    return decision
