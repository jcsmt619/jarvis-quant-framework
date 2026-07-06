from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from automation.approval_receipt_gate import evaluate_approval_receipt_gate


def run_approval_receipt_gate_report(
    *,
    approval_id: str | None,
    approvals_dir: Path = Path("reports/approvals"),
    now: datetime | None = None,
) -> int:
    result = evaluate_approval_receipt_gate(
        approval_id=approval_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    print("APPROVAL RECEIPT GATE REPORT: PASS")
    print(f"Approval id: {result.approval_id}")
    print(f"Approval path: {result.approval_path}")
    print(f"Approval status: {result.approval_status}")
    print(f"Gate allowed: {str(result.allowed).lower()}")
    print(f"Blocked reasons: {result.blocked_reasons}")
    print(f"Broker order call performed: {str(result.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether an approval receipt gate allows continuation.")
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    args = parser.parse_args()

    return run_approval_receipt_gate_report(
        approval_id=args.approval_id,
        approvals_dir=args.approvals_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
