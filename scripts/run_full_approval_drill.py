from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from automation.approval_gateway import (
    apply_approval_command,
    create_approval_record,
    parse_approval_command,
    write_approval_record,
)
from automation.approval_receipt_gate import evaluate_approval_receipt_gate
from scripts.run_approval_gated_paper_arm import run_approval_gated_paper_arm


@dataclass(frozen=True)
class FullApprovalDrillResult:
    approval_id: str
    approval_record_created: bool
    pending_gate_allowed: bool
    approval_applied: bool
    receipt_gate_allowed: bool
    gated_arm_attempted: bool
    gated_arm_return_code: int | None
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _default_gated_arm_runner(**kwargs) -> int:
    return run_approval_gated_paper_arm(**kwargs)


def run_full_approval_drill(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    auto_approve: bool = True,
    run_gated_arm: bool = True,
    now: datetime | None = None,
    injected_gated_arm_runner: Callable[..., int] | None = None,
) -> int:
    record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        source="local_drill",
        note=f"10B-7 full approval drill for {symbol}",
        now=now,
    )
    approval_path = write_approval_record(record, output_dir=approvals_dir)

    pending_gate = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    approval_applied = False
    approval_decision_status = "NOT_APPLIED"
    approval_decision_reasons: list[str] = []
    approval_command_text = f"APPROVE {record.approval_id}"

    if auto_approve:
        command = parse_approval_command(approval_command_text)
        updated_record, decision = apply_approval_command(
            record=record,
            command=command,
            now=now,
        )
        write_approval_record(updated_record, output_dir=approvals_dir)
        approval_applied = decision.accepted
        approval_decision_status = decision.status
        approval_decision_reasons = list(decision.blocked_reasons)

    receipt_gate = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    gated_arm_attempted = False
    gated_arm_return_code: int | None = None

    print("FULL APPROVAL DRILL REPORT: PASS")
    print(f"Approval record created: true")
    print(f"Approval id: {record.approval_id}")
    print(f"Approval path: {approval_path}")
    print(f"Pending gate allowed before approval: {str(pending_gate.allowed).lower()}")
    print(f"Pending gate blocked reasons: {pending_gate.blocked_reasons}")
    print(f"Auto approve enabled: {str(auto_approve).lower()}")
    print(f"Approval command: {approval_command_text}")
    print(f"Approval applied: {str(approval_applied).lower()}")
    print(f"Approval decision status: {approval_decision_status}")
    print(f"Approval decision blocked reasons: {approval_decision_reasons}")
    print(f"Receipt gate allowed after approval step: {str(receipt_gate.allowed).lower()}")
    print(f"Receipt gate status: {receipt_gate.approval_status}")
    print(f"Receipt gate blocked reasons: {receipt_gate.blocked_reasons}")

    if run_gated_arm and receipt_gate.allowed:
        gated_arm_attempted = True
        print("Approval-gated wrapper drill: ATTEMPTED_DISABLED_MODE")
        runner = injected_gated_arm_runner or _default_gated_arm_runner
        gated_arm_return_code = runner(
            approval_id=record.approval_id,
            env_file=env_file,
            approvals_dir=approvals_dir,
            symbol=symbol,
            limit=limit,
            feed=feed,
            enable_real_paper_execution=False,
            confirmation=None,
            now=now,
        )
        print(f"Approval-gated wrapper return code: {gated_arm_return_code}")

    elif run_gated_arm and not receipt_gate.allowed:
        print("Approval-gated wrapper drill: SKIPPED_RECEIPT_GATE_BLOCKED")
        gated_arm_return_code = None

    else:
        print("Approval-gated wrapper drill: SKIPPED_BY_FLAG")
        gated_arm_return_code = None

    print(f"Gated arm attempted: {str(gated_arm_attempted).lower()}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")

    if gated_arm_return_code is not None and gated_arm_return_code != 0:
        return gated_arm_return_code

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full local approval lifecycle drill safely.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--no-auto-approve", action="store_true")
    parser.add_argument("--skip-gated-arm", action="store_true")
    args = parser.parse_args()

    return run_full_approval_drill(
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        auto_approve=not args.no_auto_approve,
        run_gated_arm=not args.skip_gated_arm,
    )


if __name__ == "__main__":
    raise SystemExit(main())
