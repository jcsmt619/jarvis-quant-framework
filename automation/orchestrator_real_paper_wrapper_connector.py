from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION = (
    "I_UNDERSTAND_THIS_CONNECTS_REAL_PAPER_WRAPPER_BUT_DOES_NOT_SUBMIT_ORDER"
)


@dataclass(frozen=True)
class OrchestratorRealPaperWrapperConnectorState:
    integrated: bool
    real_paper_wrapper_requested: bool
    real_paper_wrapper_confirmation_accepted: bool
    approval_receipt_gate_allowed: bool
    paper_arm_bridge_allows_drill: bool
    paper_arm_drill_completed: bool
    real_paper_wrapper_callable_wired: bool
    real_paper_wrapper_connected: bool
    real_paper_wrapper_attempted: bool
    paper_arm_enabled: bool
    decision: str
    blocked_reasons: list[str]
    real_paper_wrapper_return_code: int | None = None
    real_paper_order_submitted: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_orchestrator_real_paper_wrapper_connector(
    *,
    enable_real_paper_wrapper: bool = False,
    real_paper_wrapper_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
    paper_arm_bridge_allows_drill: bool = False,
    paper_arm_drill_completed: bool = False,
    real_paper_wrapper_callable: Callable[[], int] | None = None,
) -> OrchestratorRealPaperWrapperConnectorState:
    """Evaluate the disabled-by-default real paper wrapper connector.

    Phase 10C-21 intentionally creates only the connector shape. It must never
    call the wrapper callable, connect a real wrapper, submit an order, perform
    a broker call, or enable live trading.
    """
    confirmation_accepted = (
        real_paper_wrapper_confirmation == REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION
    )
    callable_wired = callable(real_paper_wrapper_callable)

    if not enable_real_paper_wrapper:
        return OrchestratorRealPaperWrapperConnectorState(
            integrated=True,
            real_paper_wrapper_requested=False,
            real_paper_wrapper_confirmation_accepted=confirmation_accepted,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            paper_arm_drill_completed=paper_arm_drill_completed,
            real_paper_wrapper_callable_wired=callable_wired,
            real_paper_wrapper_connected=False,
            real_paper_wrapper_attempted=False,
            paper_arm_enabled=False,
            decision="DISABLED_BY_DEFAULT",
            blocked_reasons=["real paper wrapper connector disabled by default"],
            real_paper_wrapper_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not confirmation_accepted:
        return OrchestratorRealPaperWrapperConnectorState(
            integrated=True,
            real_paper_wrapper_requested=True,
            real_paper_wrapper_confirmation_accepted=False,
            approval_receipt_gate_allowed=approval_receipt_gate_allowed,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            paper_arm_drill_completed=paper_arm_drill_completed,
            real_paper_wrapper_callable_wired=callable_wired,
            real_paper_wrapper_connected=False,
            real_paper_wrapper_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_CONFIRMATION_NOT_ACCEPTED",
            blocked_reasons=["real paper wrapper connector confirmation phrase was not accepted"],
            real_paper_wrapper_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not approval_receipt_gate_allowed:
        return OrchestratorRealPaperWrapperConnectorState(
            integrated=True,
            real_paper_wrapper_requested=True,
            real_paper_wrapper_confirmation_accepted=True,
            approval_receipt_gate_allowed=False,
            paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
            paper_arm_drill_completed=paper_arm_drill_completed,
            real_paper_wrapper_callable_wired=callable_wired,
            real_paper_wrapper_connected=False,
            real_paper_wrapper_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_APPROVAL_RECEIPT_GATE",
            blocked_reasons=["approval receipt gate is not allowed"],
            real_paper_wrapper_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not paper_arm_bridge_allows_drill:
        return OrchestratorRealPaperWrapperConnectorState(
            integrated=True,
            real_paper_wrapper_requested=True,
            real_paper_wrapper_confirmation_accepted=True,
            approval_receipt_gate_allowed=True,
            paper_arm_bridge_allows_drill=False,
            paper_arm_drill_completed=paper_arm_drill_completed,
            real_paper_wrapper_callable_wired=callable_wired,
            real_paper_wrapper_connected=False,
            real_paper_wrapper_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_PAPER_ARM_BRIDGE",
            blocked_reasons=["paper arm bridge does not allow real wrapper connector"],
            real_paper_wrapper_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if not paper_arm_drill_completed:
        return OrchestratorRealPaperWrapperConnectorState(
            integrated=True,
            real_paper_wrapper_requested=True,
            real_paper_wrapper_confirmation_accepted=True,
            approval_receipt_gate_allowed=True,
            paper_arm_bridge_allows_drill=True,
            paper_arm_drill_completed=False,
            real_paper_wrapper_callable_wired=callable_wired,
            real_paper_wrapper_connected=False,
            real_paper_wrapper_attempted=False,
            paper_arm_enabled=False,
            decision="BLOCKED_PAPER_ARM_DRILL_NOT_COMPLETED",
            blocked_reasons=["paper arm drill did not complete successfully"],
            real_paper_wrapper_return_code=None,
            real_paper_order_submitted=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorRealPaperWrapperConnectorState(
        integrated=True,
        real_paper_wrapper_requested=True,
        real_paper_wrapper_confirmation_accepted=True,
        approval_receipt_gate_allowed=True,
        paper_arm_bridge_allows_drill=True,
        paper_arm_drill_completed=True,
        real_paper_wrapper_callable_wired=callable_wired,
        real_paper_wrapper_connected=False,
        real_paper_wrapper_attempted=False,
        paper_arm_enabled=False,
        decision="CONNECTOR_SHAPE_READY_REAL_WRAPPER_DISCONNECTED_IN_PHASE_10C_21",
        blocked_reasons=["real approval-gated paper wrapper remains disconnected in Phase 10C-21"],
        real_paper_wrapper_return_code=None,
        real_paper_order_submitted=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_real_paper_wrapper_connector_runtime_notes(
    state: OrchestratorRealPaperWrapperConnectorState,
) -> list[str]:
    return [
        f"real_paper_wrapper_connector_integrated={str(state.integrated).lower()}",
        f"real_paper_wrapper_requested={str(state.real_paper_wrapper_requested).lower()}",
        f"real_paper_wrapper_confirmation_accepted={str(state.real_paper_wrapper_confirmation_accepted).lower()}",
        f"approval_receipt_gate_allowed={str(state.approval_receipt_gate_allowed).lower()}",
        f"paper_arm_bridge_allows_drill={str(state.paper_arm_bridge_allows_drill).lower()}",
        f"paper_arm_drill_completed={str(state.paper_arm_drill_completed).lower()}",
        f"real_paper_wrapper_callable_wired={str(state.real_paper_wrapper_callable_wired).lower()}",
        f"real_paper_wrapper_connected={str(state.real_paper_wrapper_connected).lower()}",
        f"real_paper_wrapper_attempted={str(state.real_paper_wrapper_attempted).lower()}",
        f"paper_arm_enabled={str(state.paper_arm_enabled).lower()}",
        f"real_paper_wrapper_decision={state.decision}",
        f"real_paper_wrapper_return_code={state.real_paper_wrapper_return_code}",
        f"real_paper_order_submitted={str(state.real_paper_order_submitted).lower()}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
    ]
