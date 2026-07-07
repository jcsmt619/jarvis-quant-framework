from __future__ import annotations

from dataclasses import replace

import pytest

from engines.strategy_cards import STRATEGY_CARDS
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MOONSHOT_RISK_POLICY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    WEALTH_RISK_POLICY,
    PolicyDecision,
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


WEALTH_DETERMINISTIC_CARD = STRATEGY_CARDS[0]
WEALTH_ANALYST_CARD = STRATEGY_CARDS[1]
MOONSHOT_DETERMINISTIC_CARD = STRATEGY_CARDS[2]


def test_11e_blocks_when_policy_gate_fails() -> None:
    policy_decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.20,
            current_positions=1,
            missing_stop=True,
        ),
    )

    decision = evaluate_promotion_gate(
        WEALTH_DETERMINISTIC_CARD,
        policy_decision,
        PromotionGateEvidence(validation_passed=True),
    )

    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.promotion_status == PROMOTION_BLOCKED
    assert decision.live_trading_enabled is False
    assert decision.broker_order_routing_enabled is False
    assert decision.broker_order_call_performed is False
    assert "policy_gate_blocked" in decision.reasons
    assert "missing_stop" in decision.reasons


def test_11e_keeps_unvalidated_or_unresolved_strategy_research_only() -> None:
    policy_decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(proposed_position_pct=0.01, current_positions=1),
    )

    unvalidated = evaluate_promotion_gate(WEALTH_DETERMINISTIC_CARD, policy_decision)
    unresolved = evaluate_promotion_gate(
        WEALTH_DETERMINISTIC_CARD,
        policy_decision,
        PromotionGateEvidence(
            validation_passed=True,
            unresolved_findings=("slippage_stress_unresolved",),
        ),
    )

    assert unvalidated.label == RESEARCH_ONLY
    assert unvalidated.promotion_status == PROMOTION_RESEARCH_ONLY
    assert unvalidated.reasons == ("validation_not_passed",)
    assert unresolved.label == RESEARCH_ONLY
    assert unresolved.promotion_status == PROMOTION_RESEARCH_ONLY
    assert unresolved.reasons == ("unresolved_findings", "slippage_stress_unresolved")


def test_11e_promotes_validated_strategy_to_paper_only_until_paper_history_passes() -> None:
    policy_decision = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=44,
            paper_sessions=30,
            paper_max_drawdown_pct=0.02,
        ),
    )

    decision = evaluate_promotion_gate(
        MOONSHOT_DETERMINISTIC_CARD,
        policy_decision,
        PromotionGateEvidence(validation_passed=True),
    )

    assert decision.label == PAPER_ONLY
    assert decision.promotion_status == PROMOTION_PAPER_ONLY
    assert decision.reasons == ("paper_history_requirement_not_met",)


def test_11e_marks_clean_validated_strategy_eligible_for_human_review() -> None:
    policy_decision = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=45,
            paper_sessions=30,
            paper_max_drawdown_pct=0.04,
        ),
    )

    decision = evaluate_promotion_gate(
        MOONSHOT_DETERMINISTIC_CARD,
        policy_decision,
        PromotionGateEvidence(validation_passed=True),
    )

    assert decision.label == HUMAN_REVIEW_REQUIRED
    assert decision.promotion_status == PROMOTION_HUMAN_REVIEW_REQUIRED
    assert decision.human_review_required is True
    assert decision.reasons == ("eligible_for_human_review",)


def test_11e_non_deterministic_strategy_requires_human_review() -> None:
    policy_decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(proposed_position_pct=0.01, current_positions=1),
    )

    decision = evaluate_promotion_gate(WEALTH_ANALYST_CARD, policy_decision)

    assert decision.label == HUMAN_REVIEW_REQUIRED
    assert decision.promotion_status == PROMOTION_HUMAN_REVIEW_REQUIRED
    assert decision.reasons == ("non_deterministic_trade_relevant_review",)


def test_11e_rejects_forbidden_trade_instruction_labels() -> None:
    policy_decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(proposed_position_pct=0.01, current_positions=1),
    )
    unsafe_policy_decision = replace(policy_decision, label="BUY" + "_NOW")
    unsafe_gate_decision = PromotionGateDecision(
        strategy_id="11E-UNSAFE",
        engine="wealth",
        label="SELL" + "_NOW",
        promotion_status=PROMOTION_RESEARCH_ONLY,
        reasons=("unsafe_label_fixture",),
    )

    with pytest.raises(ValueError, match="unsafe policy label"):
        evaluate_promotion_gate(WEALTH_DETERMINISTIC_CARD, unsafe_policy_decision)
    with pytest.raises(ValueError, match="unsafe promotion gate label"):
        unsafe_gate_decision.validate()


def test_11e_blocks_execution_boundary_flags() -> None:
    policy_decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(proposed_position_pct=0.01, current_positions=1),
    )
    broker_policy_decision = replace(policy_decision, broker_order_routing_enabled=True)

    decision = evaluate_promotion_gate(
        WEALTH_DETERMINISTIC_CARD,
        broker_policy_decision,
        PromotionGateEvidence(validation_passed=True),
    )

    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.promotion_status == PROMOTION_BLOCKED
    assert decision.reasons == ("safety_execution_boundary_breach",)
