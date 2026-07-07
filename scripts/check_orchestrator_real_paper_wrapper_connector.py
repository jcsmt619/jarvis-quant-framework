from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.orchestrator_real_paper_wrapper_connector import (
    REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION,
    evaluate_orchestrator_real_paper_wrapper_connector,
)


def run_orchestrator_real_paper_wrapper_connector_report(
    *,
    enable_real_paper_wrapper: bool = False,
    real_paper_wrapper_confirmation: str | None = None,
    approval_receipt_gate_allowed: bool = False,
    paper_arm_bridge_allows_drill: bool = False,
    paper_arm_drill_completed: bool = False,
) -> int:
    state = evaluate_orchestrator_real_paper_wrapper_connector(
        enable_real_paper_wrapper=enable_real_paper_wrapper,
        real_paper_wrapper_confirmation=real_paper_wrapper_confirmation,
        approval_receipt_gate_allowed=approval_receipt_gate_allowed,
        paper_arm_bridge_allows_drill=paper_arm_bridge_allows_drill,
        paper_arm_drill_completed=paper_arm_drill_completed,
        real_paper_wrapper_callable=None,
    )

    print("ORCHESTRATOR REAL PAPER WRAPPER CONNECTOR REPORT")
    print(f"real_paper_wrapper_connector_integrated={str(state.integrated).lower()}")
    print(f"real_paper_wrapper_requested={str(state.real_paper_wrapper_requested).lower()}")
    print(f"real_paper_wrapper_confirmation_accepted={str(state.real_paper_wrapper_confirmation_accepted).lower()}")
    print(f"approval_receipt_gate_allowed={str(state.approval_receipt_gate_allowed).lower()}")
    print(f"paper_arm_bridge_allows_drill={str(state.paper_arm_bridge_allows_drill).lower()}")
    print(f"paper_arm_drill_completed={str(state.paper_arm_drill_completed).lower()}")
    print(f"real_paper_wrapper_callable_wired={str(state.real_paper_wrapper_callable_wired).lower()}")
    print(f"real_paper_wrapper_connected={str(state.real_paper_wrapper_connected).lower()}")
    print(f"real_paper_wrapper_attempted={str(state.real_paper_wrapper_attempted).lower()}")
    print(f"paper_arm_enabled={str(state.paper_arm_enabled).lower()}")
    print(f"real_paper_wrapper_decision={state.decision}")
    print(f"real_paper_wrapper_return_code={state.real_paper_wrapper_return_code}")
    print(f"real_paper_order_submitted={str(state.real_paper_order_submitted).lower()}")
    print(f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}")
    print(f"live_trading_enabled={str(state.live_trading_enabled).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check orchestrator real paper wrapper connector state. Phase 10C-21 remains disconnected."
    )
    parser.add_argument("--enable-real-paper-wrapper", action="store_true")
    parser.add_argument(
        "--real-paper-wrapper-confirmation",
        default=None,
        help=f"Expected confirmation phrase: {REAL_PAPER_WRAPPER_CONNECTOR_CONFIRMATION}",
    )
    parser.add_argument("--approval-receipt-gate-allowed", action="store_true")
    parser.add_argument("--paper-arm-bridge-allows-drill", action="store_true")
    parser.add_argument("--paper-arm-drill-completed", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_real_paper_wrapper_connector_report(
        enable_real_paper_wrapper=args.enable_real_paper_wrapper,
        real_paper_wrapper_confirmation=args.real_paper_wrapper_confirmation,
        approval_receipt_gate_allowed=args.approval_receipt_gate_allowed,
        paper_arm_bridge_allows_drill=args.paper_arm_bridge_allows_drill,
        paper_arm_drill_completed=args.paper_arm_drill_completed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
