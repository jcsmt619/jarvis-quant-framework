from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


PAPER_ARM_BRIDGE_CONFIRMATION = "I_UNDERSTAND_THIS_WOULD_CONNECT_APPROVAL_TO_PAPER_ARM"


@dataclass(frozen=True)
class OrchestratorPaperArmBridgeState:
    integrated: bool
    paper_arm_requested: bool
    paper_arm_confirmation_accepted: bool
    approval_receipt_gate_allowed: bool
    paper_arm_callable_wired: bool
    paper_arm_attempted: bool
    paper_arm_enabled: bool
    decision: str
    blocked_reasons: list[str]
    paper_arm_return_code: int | None = None
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def disabled_paper_arm_callable() -> int:
    raise RuntimeError("disabled paper-arm bridge must not execute in Phase 10C-17")


def evaluate_orchestrator_paper_arm_bridge(
    *,
    enable_paper_arm: bool = False,
    paper_arm_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
    paper_arm_callable: Callable[[], int] | None = disabled_paper_arm_callable,
) -> OrchestratorPaperArmBridgeState:
    confirmation_accepted = paper_arm_confirmation == PAPER_ARM_BRIDGE_CONFIRMATION
    callable_wired = callable(paper_arm_callable)

    if not enable_paper_arm:
        return OrchestratorPaperArmBridgeState(
            integrated=True,
            paper_arm_requested=False,
            paper_arm_confirmation_accepted=confirmation_accepted,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_callable_wired=callable_wired,
            paper_arm_attempted=False,
            paper_arm_enabled=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["paper arm bridge disabled by default"],
            paper_arm_return_code=None,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorPaperArmBridgeState(
            integrated=True,
            paper_arm_requested=True,
            paper_arm_confirmation_accepted=False,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_callable_wired=callable_wired,
            paper_arm_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["paper arm bridge confirmation phrase was not accepted"],
            paper_arm_return_code=None,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not approval_receipt_gate_allowed:
        return OrchestratorPaperArmBridgeState(
            integrated=True,
            paper_arm_requested=True,
            paper_arm_confirmation_accepted=True,
            approval_receipt_gate_allowed=False,
            paper_arm_callable_wired=callable_wired,
            paper_arm_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_APPROVAL_RECEIPT_GATE",
            blocked_reasons=["approval receipt gate is not allowed"],
            paper_arm_return_code=None,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorPaperArmBridgeState(
        integrated=True,
        paper_arm_requested=True,
        paper_arm_confirmation_accepted=True,
        approval_receipt_gate_allowed=True,
        paper_arm_callable_wired=callable_wired,
        paper_arm_attempted=False,
        paper_arm_enabled=False,
        decision="BRIDGE_WIRED_BUT_EXECUTION_DISABLED_IN_PHASE_10C_17",
        blocked_reasons=["paper-arm wrapper execution remains disabled in Phase 10C-17"],
        paper_arm_return_code=None,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_paper_arm_bridge_runtime_notes(state: OrchestratorPaperArmBridgeState) -> list[str]:
    return [
        f"paper_arm_bridge_integrated={str(state.integrated).lower()}",
        f"paper_arm_requested={str(state.paper_arm_requested).lower()}",
        f"paper_arm_confirmation_accepted={str(state.paper_arm_confirmation_accepted).lower()}",
        f"approval_receipt_gate_allowed={str(state.approval_receipt_gate_allowed).lower()}",
        f"paper_arm_callable_wired={str(state.paper_arm_callable_wired).lower()}",
        f"paper_arm_attempted={str(state.paper_arm_attempted).lower()}",
        f"paper_arm_enabled={str(state.paper_arm_enabled).lower()}",
        f"paper_arm_decision={state.decision}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
    ]
