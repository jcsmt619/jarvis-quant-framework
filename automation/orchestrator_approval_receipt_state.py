from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from automation.approval_receipt_gate import evaluate_approval_receipt_gate


@dataclass(frozen=True)
class OrchestratorApprovalReceiptState:
    integrated: bool
    approval_id_provided: bool
    approval_id: str | None
    approval_path: str | None
    gate_allowed: bool
    approval_status: str
    blocked_reasons: list[str]
    paper_arm_attempted: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_orchestrator_approval_receipt_state(
    *,
    approval_id: str | None = None,
    approvals_dir: Path = Path("reports/approvals"),
    now: datetime | None = None,
) -> OrchestratorApprovalReceiptState:
    receipt_gate = evaluate_approval_receipt_gate(
        approval_id=approval_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    return OrchestratorApprovalReceiptState(
        integrated=True,
        approval_id_provided=approval_id is not None and str(approval_id).strip() != "",
        approval_id=receipt_gate.approval_id,
        approval_path=receipt_gate.approval_path,
        gate_allowed=receipt_gate.allowed,
        approval_status=receipt_gate.approval_status,
        blocked_reasons=receipt_gate.blocked_reasons,
        paper_arm_attempted=False,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_approval_receipt_runtime_notes(state: OrchestratorApprovalReceiptState) -> list[str]:
    return [
        f"approval_receipt_gate_integrated={str(state.integrated).lower()}",
        f"approval_id_provided={str(state.approval_id_provided).lower()}",
        f"approval_receipt_gate_allowed={str(state.gate_allowed).lower()}",
        f"approval_receipt_status={state.approval_status}",
        f"paper_arm_attempted={str(state.paper_arm_attempted).lower()}",
        f"paper_arm_enabled={str(state.paper_arm_enabled).lower()}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
    ]
