from __future__ import annotations

from dataclasses import replace

import pytest

from engines.strategy_cards import STRATEGY_CARDS
from risk.champion_challenger import (
    CHALLENGER_BLOCKED,
    CHALLENGER_HUMAN_REVIEW_REQUIRED,
    CHALLENGER_MONITOR_ONLY,
    CHALLENGER_PAPER_ONLY,
    CHALLENGER_RESEARCH_ONLY,
    ChampionChallengerDecision,
    StrategyOosMetrics,
    evaluate_champion_challenger,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    WEALTH_RISK_POLICY,
    PolicyState,
)


INCUMBENT = STRATEGY_CARDS[0]
CHALLENGER = replace(
    STRATEGY_CARDS[0],
    card_id="14A-WEALTH-DET-RESIDUAL-MOMENTUM-CHALLENGER",
)
ANALYST_CHALLENGER = replace(
    STRATEGY_CARDS[1],
    card_id="14A-WEALTH-ANALYST-CHALLENGER",
)


def _incumbent_metrics() -> StrategyOosMetrics:
    return StrategyOosMetrics(
        in_sample_sharpe=1.10,
        oos_sharpe=0.70,
        oos_max_drawdown=-0.12,
        oos_total_return=0.08,
        trade_count=45,
        oos_windows=4,
        positive_oos_windows=3,
    )


def _strong_challenger_metrics() -> StrategyOosMetrics:
    return StrategyOosMetrics(
        in_sample_sharpe=1.20,
        oos_sharpe=0.92,
        oos_max_drawdown=-0.10,
        oos_total_return=0.12,
        trade_count=52,
        oos_windows=4,
        positive_oos_windows=4,
    )


def test_14a_blocks_challenger_when_risk_policy_fails() -> None:
    decision = evaluate_champion_challenger(
        incumbent=INCUMBENT,
        challenger=CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=_strong_challenger_metrics(),
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.20,
            current_positions=1,
            missing_stop=True,
        ),
    )

    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.challenger_status == CHALLENGER_BLOCKED
    assert decision.risk_policy_compatible is False
    assert decision.live_trading_enabled is False
    assert decision.broker_order_routing_enabled is False
    assert decision.broker_order_call_performed is False
    assert "policy_gate_blocked" in decision.reasons
    assert "missing_stop" in decision.reasons


def test_14a_keeps_failed_oos_challenger_research_only() -> None:
    weak_metrics = StrategyOosMetrics(
        in_sample_sharpe=1.00,
        oos_sharpe=0.20,
        oos_max_drawdown=-0.08,
        oos_total_return=0.02,
        trade_count=50,
        oos_windows=4,
        positive_oos_windows=3,
    )

    decision = evaluate_champion_challenger(
        incumbent=INCUMBENT,
        challenger=CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=weak_metrics,
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
        ),
    )

    assert decision.label == RESEARCH_ONLY
    assert decision.challenger_status == CHALLENGER_RESEARCH_ONLY
    assert decision.challenger_summary.funnel_survived is False
    assert decision.challenger_summary.funnel_failure == "min_oos_sharpe"
    assert "unresolved_findings" in decision.reasons
    assert "oos_funnel_failed_min_oos_sharpe" in decision.reasons


def test_14a_keeps_non_superior_challenger_monitor_only() -> None:
    close_but_not_better = StrategyOosMetrics(
        in_sample_sharpe=1.20,
        oos_sharpe=0.76,
        oos_max_drawdown=-0.11,
        oos_total_return=0.09,
        trade_count=50,
        oos_windows=4,
        positive_oos_windows=4,
    )

    decision = evaluate_champion_challenger(
        incumbent=INCUMBENT,
        challenger=CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=close_but_not_better,
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=WEALTH_RISK_POLICY.promotion_min_paper_days,
            paper_sessions=WEALTH_RISK_POLICY.promotion_min_paper_sessions,
            paper_max_drawdown_pct=WEALTH_RISK_POLICY.promotion_max_drawdown_pct,
        ),
    )

    assert decision.label == MONITOR_ONLY
    assert decision.challenger_status == CHALLENGER_MONITOR_ONLY
    assert decision.risk_policy_compatible is True
    assert decision.oos_sharpe_delta == pytest.approx(0.06)
    assert decision.reasons == ("challenger_oos_sharpe_delta_below_minimum",)


def test_14a_strong_challenger_stays_paper_only_until_paper_history_passes() -> None:
    decision = evaluate_champion_challenger(
        incumbent=INCUMBENT,
        challenger=CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=_strong_challenger_metrics(),
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=WEALTH_RISK_POLICY.promotion_min_paper_days - 1,
            paper_sessions=WEALTH_RISK_POLICY.promotion_min_paper_sessions,
            paper_max_drawdown_pct=0.02,
        ),
    )

    assert decision.label == PAPER_ONLY
    assert decision.challenger_status == CHALLENGER_PAPER_ONLY
    assert decision.reasons == ("beats_incumbent_but_paper_history_incomplete",)
    assert decision.promotion_gate.label == PAPER_ONLY


def test_14a_strong_challenger_requires_human_review_when_promotion_ready() -> None:
    decision = evaluate_champion_challenger(
        incumbent=INCUMBENT,
        challenger=CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=_strong_challenger_metrics(),
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=WEALTH_RISK_POLICY.promotion_min_paper_days,
            paper_sessions=WEALTH_RISK_POLICY.promotion_min_paper_sessions,
            paper_max_drawdown_pct=WEALTH_RISK_POLICY.promotion_max_drawdown_pct,
        ),
    )

    assert decision.label == HUMAN_REVIEW_REQUIRED
    assert decision.challenger_status == CHALLENGER_HUMAN_REVIEW_REQUIRED
    assert decision.human_review_required is True
    assert decision.reasons == ("beats_incumbent_and_requires_human_review",)
    assert decision.oos_total_return_delta == pytest.approx(0.04)
    assert decision.max_drawdown_delta == pytest.approx(0.02)


def test_14a_non_deterministic_challenger_is_human_review_required() -> None:
    decision = evaluate_champion_challenger(
        incumbent=STRATEGY_CARDS[1],
        challenger=ANALYST_CHALLENGER,
        incumbent_metrics=_incumbent_metrics(),
        challenger_metrics=_strong_challenger_metrics(),
        challenger_policy_state=PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
        ),
    )

    assert decision.label == HUMAN_REVIEW_REQUIRED
    assert decision.challenger_status == CHALLENGER_HUMAN_REVIEW_REQUIRED
    assert decision.reasons == ("non_deterministic_challenger_requires_human_review",)


def test_14a_rejects_unsafe_decision_label_and_execution_flags() -> None:
    decision = ChampionChallengerDecision(
        incumbent_strategy_id=INCUMBENT.card_id,
        challenger_strategy_id=CHALLENGER.card_id,
        engine="wealth",
        label="EXECUTE" + "_TRADE",
        challenger_status=CHALLENGER_HUMAN_REVIEW_REQUIRED,
        reasons=("unsafe_label_fixture",),
        incumbent_summary=evaluate_champion_challenger(
            incumbent=INCUMBENT,
            challenger=CHALLENGER,
            incumbent_metrics=_incumbent_metrics(),
            challenger_metrics=_strong_challenger_metrics(),
            challenger_policy_state=PolicyState(
                proposed_position_pct=0.01,
                current_positions=1,
            ),
        ).incumbent_summary,
        challenger_summary=evaluate_champion_challenger(
            incumbent=INCUMBENT,
            challenger=CHALLENGER,
            incumbent_metrics=_incumbent_metrics(),
            challenger_metrics=_strong_challenger_metrics(),
            challenger_policy_state=PolicyState(
                proposed_position_pct=0.01,
                current_positions=1,
            ),
        ).challenger_summary,
        oos_sharpe_delta=0.1,
        oos_total_return_delta=0.1,
        max_drawdown_delta=0.1,
        promotion_gate=evaluate_champion_challenger(
            incumbent=INCUMBENT,
            challenger=CHALLENGER,
            incumbent_metrics=_incumbent_metrics(),
            challenger_metrics=_strong_challenger_metrics(),
            challenger_policy_state=PolicyState(
                proposed_position_pct=0.01,
                current_positions=1,
            ),
        ).promotion_gate,
        risk_policy_compatible=True,
        **{"live_trading_" + "enabled": True},
    )

    with pytest.raises(ValueError, match="unsafe champion/challenger label"):
        decision.validate()
