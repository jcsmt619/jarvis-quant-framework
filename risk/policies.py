from __future__ import annotations

from dataclasses import dataclass, field


RESEARCH_ONLY = "RESEARCH_ONLY"
MONITOR_ONLY = "MONITOR_ONLY"
PAPER_ONLY = "PAPER_ONLY"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
BLOCKED_BY_SAFETY_GATE = "BLOCKED_BY_SAFETY_GATE"

SAFE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
)


@dataclass(frozen=True)
class EngineRiskPolicy:
    engine: str
    max_loss_per_position_pct: float
    max_daily_loss_pct: float
    max_total_drawdown_pct: float
    max_position_pct: float
    max_positions: int
    promotion_min_paper_days: int
    promotion_min_paper_sessions: int
    promotion_max_drawdown_pct: float
    stop_conditions: tuple[str, ...]
    labels: tuple[str, ...] = SAFE_LABELS
    research_only: bool = True
    monitor_only: bool = True
    paper_only: bool = True
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False

    def validate_static_safety(self) -> None:
        if not self.research_only or not self.paper_only:
            raise ValueError("risk policies must remain research-only and paper-only")
        if self.live_trading_enabled or self.broker_order_routing_enabled:
            raise ValueError("risk policies cannot enable live trading or broker routing")
        if self.max_position_pct <= 0 or self.max_positions <= 0:
            raise ValueError("position sizing limits must be positive")
        for pct in (
            self.max_loss_per_position_pct,
            self.max_daily_loss_pct,
            self.max_total_drawdown_pct,
            self.promotion_max_drawdown_pct,
        ):
            if pct <= 0:
                raise ValueError("loss and drawdown limits must be positive")


@dataclass(frozen=True)
class PolicyState:
    proposed_position_pct: float
    current_positions: int
    max_position_loss_pct: float = 0.0
    daily_loss_pct: float = 0.0
    total_drawdown_pct: float = 0.0
    paper_days: int = 0
    paper_sessions: int = 0
    paper_max_drawdown_pct: float = 0.0
    missing_stop: bool = False
    stale_data: bool = False
    kill_switch_engaged: bool = False
    policy_breach: bool = False
    analyst_override_requested: bool = False
    extra_stop_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    label: str
    reasons: tuple[str, ...]
    promotion_eligible: bool
    required_labels: tuple[str, ...]
    human_review_required: bool
    live_trading_enabled: bool
    broker_order_routing_enabled: bool


WEALTH_RISK_POLICY = EngineRiskPolicy(
    engine="wealth",
    max_loss_per_position_pct=0.02,
    max_daily_loss_pct=0.03,
    max_total_drawdown_pct=0.10,
    max_position_pct=0.10,
    max_positions=12,
    promotion_min_paper_days=30,
    promotion_min_paper_sessions=20,
    promotion_max_drawdown_pct=0.05,
    stop_conditions=(
        "missing_stop",
        "position_loss_breach",
        "daily_loss_breach",
        "total_drawdown_breach",
        "position_size_breach",
        "max_positions_breach",
        "stale_data",
        "kill_switch_engaged",
        "policy_breach",
        "analyst_override_requested",
    ),
)

MOONSHOT_RISK_POLICY = EngineRiskPolicy(
    engine="moonshot",
    max_loss_per_position_pct=0.01,
    max_daily_loss_pct=0.02,
    max_total_drawdown_pct=0.08,
    max_position_pct=0.03,
    max_positions=6,
    promotion_min_paper_days=45,
    promotion_min_paper_sessions=30,
    promotion_max_drawdown_pct=0.04,
    stop_conditions=(
        "missing_stop",
        "position_loss_breach",
        "daily_loss_breach",
        "total_drawdown_breach",
        "position_size_breach",
        "max_positions_breach",
        "stale_data",
        "kill_switch_engaged",
        "policy_breach",
        "analyst_override_requested",
        "option_chain_stale",
        "theta_decay_breach",
        "iv_spike_review",
    ),
)

ENGINE_RISK_POLICIES = {
    WEALTH_RISK_POLICY.engine: WEALTH_RISK_POLICY,
    MOONSHOT_RISK_POLICY.engine: MOONSHOT_RISK_POLICY,
}


def evaluate_policy(policy: EngineRiskPolicy, state: PolicyState) -> PolicyDecision:
    policy.validate_static_safety()

    reasons: list[str] = []
    if state.missing_stop:
        reasons.append("missing_stop")
    if state.max_position_loss_pct > policy.max_loss_per_position_pct:
        reasons.append("position_loss_breach")
    if state.daily_loss_pct > policy.max_daily_loss_pct:
        reasons.append("daily_loss_breach")
    if state.total_drawdown_pct > policy.max_total_drawdown_pct:
        reasons.append("total_drawdown_breach")
    if state.proposed_position_pct > policy.max_position_pct:
        reasons.append("position_size_breach")
    if state.current_positions >= policy.max_positions:
        reasons.append("max_positions_breach")
    if state.stale_data:
        reasons.append("stale_data")
    if state.kill_switch_engaged:
        reasons.append("kill_switch_engaged")
    if state.policy_breach:
        reasons.append("policy_breach")
    if state.analyst_override_requested:
        reasons.append("analyst_override_requested")

    for flag in state.extra_stop_flags:
        if flag in policy.stop_conditions:
            reasons.append(flag)

    promotion_eligible = (
        state.paper_days >= policy.promotion_min_paper_days
        and state.paper_sessions >= policy.promotion_min_paper_sessions
        and state.paper_max_drawdown_pct <= policy.promotion_max_drawdown_pct
    )

    allowed = not reasons
    return PolicyDecision(
        allowed=allowed,
        label=RESEARCH_ONLY if allowed else BLOCKED_BY_SAFETY_GATE,
        reasons=tuple(reasons),
        promotion_eligible=promotion_eligible,
        required_labels=policy.labels,
        human_review_required=policy.human_review_required,
        live_trading_enabled=policy.live_trading_enabled,
        broker_order_routing_enabled=policy.broker_order_routing_enabled,
    )
