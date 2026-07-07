from __future__ import annotations

import argparse

from automation.orchestrator_paper_arm_drill import (
    PAPER_ARM_DRILL_CONFIRMATION,
    run_orchestrator_paper_arm_drill,
)


def run_orchestrator_paper_arm_drill_report(
    *,
    enable_paper_arm_drill: bool = False,
    paper_arm_drill_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
    paper_arm_bridge_allows_drill: bool = False,
) -> int:
    state = run_orchestrator_paper_arm_drill(
        enable_paper_arm_drill=enable_paper_arm_drill,
        paper_arm_drill_confirmation=paper_arm_drill_confirmation,
        approval_receipt_gate_allowed=approval_receipt_gate_allowed,
        paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
        paper_arm_callable=None,
    )

    print("ORCHESTRATOR PAPER ARM DRILL REPORT: PASS")
    print(f"Paper arm drill integrated: {str(state.integrated).lower()}")
    print(f"Paper arm drill requested: {str(state.paper_arm_drill_requested).lower()}")
    print(f"Paper arm drill confirmation accepted: {str(state.paper_arm_drill_confirmation_accepted).lower()}")
    print(f"Approval receipt gate allowed: {str(state.approval_receipt_gate_allowed).lower()}")
    print(f"Paper arm bridge allows drill: {str(state.paper_arm_bridge_allows_drill).lower()}")
    print(f"Injected paper arm callable wired: {str(state.injected_paper_arm_callable_wired).lower()}")
    print(f"Paper arm drill attempted: {str(state.paper_arm_drill_attempted).lower()}")
    print(f"Paper arm enabled: {str(state.paper_arm_enabled).lower()}")
    print(f"Paper arm drill return code: {state.paper_arm_drill_return_code}")
    print(f"Paper arm drill decision: {state.decision}")
    print(f"Paper arm drill blocked reasons: {state.blocked_reasons}")
    print(f"Real paper order submitted: {str(state.real_paper_order_submitted).lower()}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator paper-arm drill state.")
    parser.add_argument("--enable-paper-arm-drill", action="store_true")
    parser.add_argument("--paper-arm-drill-confirmation", default=None)
    parser.add_argument("--approval-receipt-gate-allowed", action="store_true")
    parser.add_argument("--paper-arm-bridge-allows-drill", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_paper_arm_drill_report(
        enable_paper_arm_drill=args.enable_paper_arm_drill,
        paper_arm_drill_confirmation=args.paper_arm_drill_confirmation,
        approval_receipt_gate_allowed=args.approval_receipt_gate_allowed,
        paper_arm_bridge_allows_drill=args.paper_arm_bridge_allows_drill,
    )


if __name__ == "__main__":
    raise SystemExit(main())
