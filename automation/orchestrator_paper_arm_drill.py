from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


PAPER_ARM_DRILL_CONFIRMATION = "I_UNDERSTAND_THIS_RUNS_APPROVAL_GATED_PAPER_ARM_DRILL_WITHOUT_BROKER_ORDER"


@dataclass(frozen=True)
class OrchestratorPaperArmDrillState:
    integrated: bool
    paper_arm_drill_requested: bool
    paper_arm_drill_confirmation_accepted: bool
    approval_receipt_gate_allowed: bool
    paper_arm_bridge_allows_drill: bool
    injected_paper_arm_callable_wired: bool
    paper_arm_drill_attempted: bool
    paper_arm_enabled: bool
    decision: str
    blocked_reasons: list[str]
    paper_arm_drill_return_code: int | None = None
    real_paper_order_submitted: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def run_orchestrator_paper_arm_drill(
    *,
    enable_paper_arm_drill: bool = False,
    paper_arm_drill_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
    paper_arm_bridge_allows_drill: bool = False,
    paper_arm_callable: Callable[[], int] | None = None,
) -> OrchestratorPaperArmDrillState:
    confirmation_accepted = paper_arm_drill_confirmation == PAPER_ARM_DRILL_CONFIRMATION
    callable_wired = callable(paper_arm_callable)

    if not enable_paper_arm_drill:
        return OrchestratorPaperArmDrillState(
            integrated=True,
            paper_arm_drill_requested=False,
            paper_arm_drill_confirmation_accepted=confirmation_accepted,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            injected_paper_arm_callable_wired=callable_wired,
            paper_arm_drill_attempted=False,
            paper_arm_enabled=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["paper arm drill disabled by default"],
            paper_arm_drill_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorPaperArmDrillState(
            integrated=True,
            paper_arm_drill_requested=True,
            paper_arm_drill_confirmation_accepted=False,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            injected_paper_arm_callable_wired=callable_wired,
            paper_arm_drill_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["paper arm drill confirmation phrase was not accepted"],
            paper_arm_drill_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not approval_receipt_gate_allowed:
        return OrchestratorPaperArmDrillState(
            integrated=True,
            paper_arm_drill_requested=True,
            paper_arm_drill_confirmation_accepted=True,
            approval_receipt_gate_allowed=False,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            injected_paper_arm_callable_wired=callable_wired,
            paper_arm_drill_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_APPROVAL_RECEIPT_GATE",
            blocked_reasons=["approval receipt gate is not allowed"],
            paper_arm_drill_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not paper_arm_bridge_allows_drill:
        return OrchestratorPaperArmDrillState(
            integrated=True,
            paper_arm_drill_requested=True,
            paper_arm_drill_confirmation_accepted=True,
            approval_receipt_gate_allowed=True,
            paper_arm_bridge_allows_drill=False,
            injected_paper_arm_callable_wired=callable_wired,
            paper_arm_drill_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_PAPER_ARM_BRIDGE",
            blocked_reasons=["paper arm bridge does not allow the drill"],
            paper_arm_drill_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not callable_wired:
        return OrchestratorPaperArmDrillState(
            integrated=True,
            paper_arm_drill_requested=True,
            paper_arm_drill_confirmation_accepted=True,
            approval_receipt_gate_allowed=True,
            paper_arm_bridge_allows_drill=True,
            injected_paper_arm_callable_wired=False,
            paper_arm_drill_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_NO_INJECTED_DRY_RUN_CALLABLE",
            blocked_reasons=["no injected dry-run paper arm callable is wired; real wrapper remains disconnected"],
            paper_arm_drill_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return_code = int(paper_arm_callable())

    return OrchestratorPaperArmDrillState(
        integrated=True,
        paper_arm_drill_requested=True,
        paper_arm_drill_confirmation_accepted=True,
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        injected_paper_arm_callable_wired=True,
        paper_arm_drill_attempted=True,
        paper_arm_enabled=False,
        decision="DRILL_COMPLETED_WITH_INJECTED_CALLABLE_ONLY",
        blocked_reasons=[],
        paper_arm_drill_return_code=return_code,
        real_paper_order_submitted=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_paper_arm_drill_runtime_notes(state: OrchestratorPaperArmDrillState) -> list[str]:
    return [
        f"paper_arm_drill_integrated={str(state.integrated).lower()}",
        f"paper_arm_drill_requested={str(state.paper_arm_drill_requested).lower()}",
        f"paper_arm_drill_confirmation_accepted={str(state.paper_arm_drill_confirmation_accepted).lower()}",
        f"approval_receipt_gate_allowed={str(state.approval_receipt_gate_allowed).lower()}",
        f"paper_arm_bridge_allows_drill={str(state.paper_arm_bridge_allows_drill).lower()}",
        f"injected_paper_arm_callable_wired={str(state.injected_paper_arm_callable_wired).lower()}",
        f"paper_arm_drill_attempted={str(state.paper_arm_drill_attempted).lower()}",
        f"paper_arm_enabled={str(state.paper_arm_enabled).lower()}",
        f"paper_arm_drill_decision={state.decision}",
        f"paper_arm_drill_return_code={state.paper_arm_drill_return_code}",
        f"real_paper_order_submitted={str(state.real_paper_order_submitted).lower()}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
    ]
