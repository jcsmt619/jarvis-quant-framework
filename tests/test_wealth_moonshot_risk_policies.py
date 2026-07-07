from __future__ import annotations

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    ENGINE_RISK_POLICIES,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    MOONSHOT_RISK_POLICY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    WEALTH_RISK_POLICY,
    PolicyState,
    evaluate_policy,
)


def test_11b_defines_wealth_and_moonshot_research_paper_policies() -> None:
    assert set(ENGINE_RISK_POLICIES) == {"wealth", "moonshot"}

    for policy in ENGINE_RISK_POLICIES.values():
        policy.validate_static_safety()
        assert policy.research_only is True
        assert policy.paper_only is True
        assert policy.monitor_only is True
        assert policy.human_review_required is True
        assert policy.live_trading_enabled is False
        assert policy.broker_order_routing_enabled is False
        assert policy.labels == (
            RESEARCH_ONLY,
            MONITOR_ONLY,
            PAPER_ONLY,
            HUMAN_REVIEW_REQUIRED,
        )


def test_11b_policy_limits_are_engine_specific() -> None:
    assert WEALTH_RISK_POLICY.max_position_pct == 0.10
    assert WEALTH_RISK_POLICY.max_total_drawdown_pct == 0.10
    assert WEALTH_RISK_POLICY.max_positions == 12

    assert MOONSHOT_RISK_POLICY.max_position_pct == 0.03
    assert MOONSHOT_RISK_POLICY.max_total_drawdown_pct == 0.08
    assert MOONSHOT_RISK_POLICY.max_positions == 6
    assert "theta_decay_breach" in MOONSHOT_RISK_POLICY.stop_conditions
    assert "iv_spike_review" in MOONSHOT_RISK_POLICY.stop_conditions


def test_11b_policy_blocks_loss_drawdown_sizing_and_stop_breaches() -> None:
    decision = evaluate_policy(
        WEALTH_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.12,
            current_positions=12,
            max_position_loss_pct=0.03,
            daily_loss_pct=0.04,
            total_drawdown_pct=0.11,
            missing_stop=True,
        ),
    )

    assert decision.allowed is False
    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.live_trading_enabled is False
    assert decision.broker_order_routing_enabled is False
    assert set(decision.reasons) >= {
        "missing_stop",
        "position_loss_breach",
        "daily_loss_breach",
        "total_drawdown_breach",
        "position_size_breach",
        "max_positions_breach",
    }


def test_11b_policy_blocks_kill_switch_stale_data_and_analyst_override() -> None:
    decision = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            stale_data=True,
            kill_switch_engaged=True,
            analyst_override_requested=True,
            extra_stop_flags=("theta_decay_breach",),
        ),
    )

    assert decision.allowed is False
    assert decision.label == BLOCKED_BY_SAFETY_GATE
    assert decision.human_review_required is True
    assert set(decision.reasons) == {
        "stale_data",
        "kill_switch_engaged",
        "analyst_override_requested",
        "theta_decay_breach",
    }


def test_11b_promotion_gates_require_clean_paper_history() -> None:
    blocked = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=44,
            paper_sessions=30,
            paper_max_drawdown_pct=0.02,
        ),
    )
    eligible = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=45,
            paper_sessions=30,
            paper_max_drawdown_pct=0.04,
        ),
    )
    drawdown_blocked = evaluate_policy(
        MOONSHOT_RISK_POLICY,
        PolicyState(
            proposed_position_pct=0.01,
            current_positions=1,
            paper_days=90,
            paper_sessions=60,
            paper_max_drawdown_pct=0.05,
        ),
    )

    assert blocked.allowed is True
    assert blocked.promotion_eligible is False
    assert eligible.allowed is True
    assert eligible.label == RESEARCH_ONLY
    assert eligible.promotion_eligible is True
    assert drawdown_blocked.allowed is True
    assert drawdown_blocked.promotion_eligible is False
