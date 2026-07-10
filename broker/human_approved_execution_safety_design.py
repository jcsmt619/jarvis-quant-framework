"""BR-12 human-approved execution safety design contracts.

This module documents and validates a future human approval boundary only.
It does not load credentials, construct broker clients, route orders, submit
orders, or enable live trading.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-12"
MODULE_NAME = "Human Approved Execution Safety Design"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REQUIRED_APPROVAL_GATES = (
    "strategy_signal_review",
    "risk_policy_review",
    "position_limit_review",
    "broker_adapter_boundary_review",
    "operator_manual_confirmation",
    "audit_receipt_review",
)
REQUIRED_KILL_SWITCHES = (
    "global_operator_halt",
    "strategy_halt",
    "symbol_halt",
    "broker_adapter_halt",
    "stale_data_halt",
    "audit_write_failure_halt",
)
REQUIRED_MANUAL_CONFIRMATIONS = (
    "operator_identity_confirmed",
    "account_scope_confirmed",
    "symbol_and_quantity_confirmed",
    "risk_limits_confirmed",
    "kill_switches_confirmed_clear",
    "audit_receipt_confirmed",
)
REQUIRED_AUDIT_FIELDS = (
    "request_id",
    "phase",
    "timestamp_utc",
    "operator_id_hash",
    "strategy_id",
    "symbol",
    "approval_gate_results",
    "position_limit_results",
    "manual_confirmation_results",
    "decision",
    "live_trading_status",
)


@dataclass(frozen=True)
class ApprovalGateDesign:
    name: str
    required: bool = True
    human_review_required: bool = True
    blocks_on_failure: bool = True
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        _require_member("approval gate", self.name, REQUIRED_APPROVAL_GATES)
        _require_safe_label(self.label)
        if not self.required:
            raise ValueError("BR-12 approval gates must be required")
        if not self.human_review_required:
            raise ValueError("BR-12 approval gates must require human review")
        if not self.blocks_on_failure:
            raise ValueError("BR-12 approval gates must block on failure")


@dataclass(frozen=True)
class BrokerAdapterBoundaryDesign:
    adapter_name: str
    read_only_snapshot_allowed: bool = True
    paper_intent_allowed: bool = True
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False
    credential_loading_required: bool = False

    def validate(self) -> None:
        _require_text("adapter_name", self.adapter_name)
        if self.broker_order_routing_enabled:
            raise ValueError("BR-12 broker boundaries cannot enable order routing")
        if self.broker_order_call_performed:
            raise ValueError("BR-12 broker boundaries cannot perform broker order calls")
        if self.live_trading_enabled:
            raise ValueError("BR-12 broker boundaries cannot enable live trading")
        if self.credential_loading_required:
            raise ValueError("BR-12 broker boundaries cannot require credential loading")


@dataclass(frozen=True)
class KillSwitchDesign:
    name: str
    required: bool = True
    default_state: str = "ENGAGED_UNTIL_CLEARED"
    label: str = BLOCKED_BY_SAFETY_GATE

    def validate(self) -> None:
        _require_member("kill switch", self.name, REQUIRED_KILL_SWITCHES)
        _require_safe_label(self.label)
        if not self.required:
            raise ValueError("BR-12 kill switches must be required")
        if self.default_state != "ENGAGED_UNTIL_CLEARED":
            raise ValueError("BR-12 kill switches must default to engaged until cleared")


@dataclass(frozen=True)
class PositionLimitDesign:
    name: str
    maximum: float
    unit: str
    required: bool = True
    blocks_on_breach: bool = True

    def validate(self) -> None:
        _require_text("position limit name", self.name)
        _require_text("position limit unit", self.unit)
        if self.maximum <= 0:
            raise ValueError("BR-12 position limits must be positive")
        if not self.required:
            raise ValueError("BR-12 position limits must be required")
        if not self.blocks_on_breach:
            raise ValueError("BR-12 position limits must block on breach")


@dataclass(frozen=True)
class ManualConfirmationDesign:
    name: str
    required: bool = True
    operator_entered: bool = False
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        _require_member("manual confirmation", self.name, REQUIRED_MANUAL_CONFIRMATIONS)
        _require_safe_label(self.label)
        if not self.required:
            raise ValueError("BR-12 manual confirmations must be required")
        if self.operator_entered:
            raise ValueError("BR-12 design phase cannot record live operator confirmations")


@dataclass(frozen=True)
class AuditTrailDesign:
    required_fields: tuple[str, ...] = REQUIRED_AUDIT_FIELDS
    append_only: bool = True
    hashed_operator_identity: bool = True
    secret_values_allowed: bool = False
    broker_account_numbers_allowed: bool = False
    write_failure_blocks: bool = True

    def validate(self) -> None:
        if self.required_fields != REQUIRED_AUDIT_FIELDS:
            raise ValueError("BR-12 audit trail must preserve required fields")
        if not self.append_only:
            raise ValueError("BR-12 audit trail must be append-only")
        if not self.hashed_operator_identity:
            raise ValueError("BR-12 audit trail must use hashed operator identity")
        if self.secret_values_allowed:
            raise ValueError("BR-12 audit trail cannot allow secret values")
        if self.broker_account_numbers_allowed:
            raise ValueError("BR-12 audit trail cannot allow broker account numbers")
        if not self.write_failure_blocks:
            raise ValueError("BR-12 audit write failures must block")


@dataclass(frozen=True)
class HumanApprovedExecutionSafetyState:
    phase: str
    module: str
    labels: tuple[str, ...]
    requested: bool
    approval_gates_defined: bool
    broker_adapter_boundaries_defined: bool
    kill_switches_defined: bool
    position_limits_defined: bool
    audit_trails_defined: bool
    manual_confirmations_defined: bool
    manual_confirmations_recorded: bool
    broker_order_routing_enabled: bool
    broker_order_call_performed: bool
    broker_order_submitted: bool
    live_trading_enabled: bool
    decision: str
    blocked_reasons: tuple[str, ...]
    live_trading_status: str = "LIVE TRADING: DISABLED"

    def validate(self) -> None:
        if self.phase != PHASE_ID:
            raise ValueError("BR-12 safety state has wrong phase")
        if self.labels != REQUIRED_LABELS:
            raise ValueError("BR-12 safety state must preserve required labels")
        if self.manual_confirmations_recorded:
            raise ValueError("BR-12 cannot record live manual confirmations")
        if self.broker_order_routing_enabled:
            raise ValueError("BR-12 cannot enable broker order routing")
        if self.broker_order_call_performed:
            raise ValueError("BR-12 cannot perform broker order calls")
        if self.broker_order_submitted:
            raise ValueError("BR-12 cannot submit broker orders")
        if self.live_trading_enabled:
            raise ValueError("BR-12 cannot enable live trading")
        if self.live_trading_status != "LIVE TRADING: DISABLED":
            raise ValueError("BR-12 must keep live trading disabled")


def safety_manifest() -> dict[str, object]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "approval_design_only": True,
        "approval_gates": REQUIRED_APPROVAL_GATES,
        "kill_switches": REQUIRED_KILL_SWITCHES,
        "manual_confirmations": REQUIRED_MANUAL_CONFIRMATIONS,
        "audit_fields": REQUIRED_AUDIT_FIELDS,
        "manual_confirmations_recorded": False,
        "credential_loading_required": False,
        "broker_connection_attempted": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def default_approval_gates() -> tuple[ApprovalGateDesign, ...]:
    return tuple(ApprovalGateDesign(name=name) for name in REQUIRED_APPROVAL_GATES)


def default_kill_switches() -> tuple[KillSwitchDesign, ...]:
    return tuple(KillSwitchDesign(name=name) for name in REQUIRED_KILL_SWITCHES)


def default_position_limits() -> tuple[PositionLimitDesign, ...]:
    return (
        PositionLimitDesign(name="max_position_notional_pct", maximum=0.03, unit="portfolio_equity_pct"),
        PositionLimitDesign(name="max_daily_loss_pct", maximum=0.02, unit="portfolio_equity_pct"),
        PositionLimitDesign(name="max_open_positions", maximum=6, unit="count"),
        PositionLimitDesign(name="max_symbol_concentration_pct", maximum=0.05, unit="portfolio_equity_pct"),
    )


def default_manual_confirmations() -> tuple[ManualConfirmationDesign, ...]:
    return tuple(ManualConfirmationDesign(name=name) for name in REQUIRED_MANUAL_CONFIRMATIONS)


def evaluate_human_approved_execution_safety_design(
    *,
    request_future_approval_path: bool = False,
    manual_confirmations_recorded: bool = False,
) -> HumanApprovedExecutionSafetyState:
    """Evaluate the BR-12 design boundary without performing broker work."""

    _validate_design_components()
    if manual_confirmations_recorded:
        state = HumanApprovedExecutionSafetyState(
            phase=PHASE_ID,
            module=MODULE_NAME,
            labels=REQUIRED_LABELS,
            requested=request_future_approval_path,
            approval_gates_defined=True,
            broker_adapter_boundaries_defined=True,
            kill_switches_defined=True,
            position_limits_defined=True,
            audit_trails_defined=True,
            manual_confirmations_defined=True,
            manual_confirmations_recorded=True,
            broker_order_routing_enabled=False,
            broker_order_call_performed=False,
            broker_order_submitted=False,
            live_trading_enabled=False,
            decision="BLOCKED_LIVE_CONFIRMATIONS_NOT_ALLOWED_IN_BR_12",
            blocked_reasons=("BR-12 is design-only and cannot record live operator confirmations",),
        )
        state.validate()
        return state

    decision = (
        "DESIGN_READY_APPROVAL_PATH_DISABLED"
        if request_future_approval_path
        else "DESIGN_ONLY_DISABLED_BY_DEFAULT"
    )
    state = HumanApprovedExecutionSafetyState(
        phase=PHASE_ID,
        module=MODULE_NAME,
        labels=REQUIRED_LABELS,
        requested=request_future_approval_path,
        approval_gates_defined=True,
        broker_adapter_boundaries_defined=True,
        kill_switches_defined=True,
        position_limits_defined=True,
        audit_trails_defined=True,
        manual_confirmations_defined=True,
        manual_confirmations_recorded=False,
        broker_order_routing_enabled=False,
        broker_order_call_performed=False,
        broker_order_submitted=False,
        live_trading_enabled=False,
        decision=decision,
        blocked_reasons=("future approval path remains disabled in BR-12",),
    )
    state.validate()
    return state


def runtime_notes(state: HumanApprovedExecutionSafetyState) -> tuple[str, ...]:
    state.validate()
    return (
        f"br12_requested={str(state.requested).lower()}",
        f"approval_gates_defined={str(state.approval_gates_defined).lower()}",
        f"broker_adapter_boundaries_defined={str(state.broker_adapter_boundaries_defined).lower()}",
        f"kill_switches_defined={str(state.kill_switches_defined).lower()}",
        f"position_limits_defined={str(state.position_limits_defined).lower()}",
        f"audit_trails_defined={str(state.audit_trails_defined).lower()}",
        f"manual_confirmations_defined={str(state.manual_confirmations_defined).lower()}",
        f"manual_confirmations_recorded={str(state.manual_confirmations_recorded).lower()}",
        f"broker_order_routing_enabled={str(state.broker_order_routing_enabled).lower()}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"broker_order_submitted={str(state.broker_order_submitted).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
        state.live_trading_status,
        f"br12_decision={state.decision}",
    )


def _validate_design_components() -> None:
    for gate in default_approval_gates():
        gate.validate()
    BrokerAdapterBoundaryDesign(adapter_name="future_human_approved_boundary").validate()
    for kill_switch in default_kill_switches():
        kill_switch.validate()
    for position_limit in default_position_limits():
        position_limit.validate()
    for confirmation in default_manual_confirmations():
        confirmation.validate()
    AuditTrailDesign().validate()


def _require_text(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_member(field_name: str, value: str, allowed: tuple[str, ...]) -> None:
    _require_text(field_name, value)
    if value not in allowed:
        raise ValueError(f"{field_name} is not part of the BR-12 design")


def _require_safe_label(label: str) -> None:
    if label not in REQUIRED_LABELS:
        raise ValueError("label must be a safe BR-12 research, monitor, paper, review, or blocked label")
