from __future__ import annotations

import argparse

from automation.orchestrator_paper_arm_bridge import (
    PAPER_ARM_BRIDGE_CONFIRMATION,
    evaluate_orchestrator_paper_arm_bridge,
)


def run_orchestrator_paper_arm_bridge_report(
    *,
    enable_paper_arm: bool = False,
    paper_arm_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
) -> int:
    state = evaluate_orchestrator_paper_arm_bridge(
        enable_paper_arm=enable_paper_arm,
        paper_arm_confirmation=paper_arm_confirmation,
        approval_receipt_gate_allowed=approval_receipt_gate_allowed,
    )

    print("ORCHESTRATOR PAPER ARM BRIDGE REPORT: PASS")
    print(f"Paper arm bridge integrated: {str(state.integrated).lower()}")
    print(f"Paper arm requested: {str(state.paper_arm_requested).lower()}")
    print(f"Paper arm confirmation accepted: {str(state.paper_arm_confirmation_accepted).lower()}")
    print(f"Approval receipt gate allowed: {str(state.approval_receipt_gate_allowed).lower()}")
    print(f"Paper arm callable wired: {str(state.paper_arm_callable_wired).lower()}")
    print(f"Paper arm attempted: {str(state.paper_arm_attempted).lower()}")
    print(f"Paper arm enabled: {str(state.paper_arm_enabled).lower()}")
    print(f"Paper arm return code: {state.paper_arm_return_code}")
    print(f"Paper arm bridge decision: {state.decision}")
    print(f"Paper arm bridge blocked reasons: {state.blocked_reasons}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator paper-arm bridge state.")
    parser.add_argument("--enable-paper-arm", action="store_true")
    parser.add_argument("--paper-arm-confirmation", default=None)
    parser.add_argument("--approval-receipt-gate-allowed", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_paper_arm_bridge_report(
        enable_paper_arm=args.enable_paper_arm,
        paper_arm_confirmation=args.paper_arm_confirmation,
        approval_receipt_gate_allowed=args.approval_receipt_gate_allowed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
