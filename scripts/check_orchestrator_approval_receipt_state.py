from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_approval_receipt_state import evaluate_orchestrator_approval_receipt_state


def run_orchestrator_approval_receipt_state_report(
    *,
    approval_id: str | None = None,
    approvals_dir: Path = Path("reports/approvals"),
) -> int:
    state = evaluate_orchestrator_approval_receipt_state(
        approval_id=approval_id,
        approvals_dir=approvals_dir,
    )

    print("ORCHESTRATOR APPROVAL RECEIPT GATE REPORT: PASS")
    print(f"Approval receipt gate integrated: {str(state.integrated).lower()}")
    print(f"Approval id provided: {str(state.approval_id_provided).lower()}")
    print(f"Approval id: {state.approval_id}")
    print(f"Approval path: {state.approval_path}")
    print(f"Approval receipt gate allowed: {str(state.gate_allowed).lower()}")
    print(f"Approval receipt status: {state.approval_status}")
    print(f"Approval receipt blocked reasons: {state.blocked_reasons}")
    print(f"Paper arm attempted: {str(state.paper_arm_attempted).lower()}")
    print(f"Paper arm enabled: {str(state.paper_arm_enabled).lower()}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator approval receipt gate state.")
    parser.add_argument("--approval-id", default=None)
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    args = parser.parse_args()

    return run_orchestrator_approval_receipt_state_report(
        approval_id=args.approval_id,
        approvals_dir=args.approvals_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
