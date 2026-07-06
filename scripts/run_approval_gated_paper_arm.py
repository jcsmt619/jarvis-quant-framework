from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from automation.approval_receipt_gate import evaluate_approval_receipt_gate

PAPER_ORDER_CONFIRMATION = "I_UNDERSTAND_THIS_SUBMITS_A_REAL_ALPACA_PAPER_ORDER"


@dataclass(frozen=True)
class ApprovalGatedPaperArmResult:
    approval_gate_allowed: bool
    approval_status: str
    workflow_attempted: bool
    workflow_return_code: int | None
    armed_paper_execution_requested: bool
    paper_confirmation_accepted: bool
    broker_order_call_performed: bool
    live_trading_enabled: bool
    blocked_reasons: list[str]


def _default_workflow_runner(command: list[str]) -> Any:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def _workflow_indicates_broker_order(stdout: str) -> bool:
    text = stdout.lower()
    return (
        "real paper order submitted: true" in text
        or "paper client used: true" in text
        or "real broker client used: true" in text
    )


def run_approval_gated_paper_arm(
    *,
    approval_id: str | None,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    enable_real_paper_execution: bool = False,
    confirmation: str | None = None,
    injected_workflow_runner: Callable[[list[str]], Any] | None = None,
    now: datetime | None = None,
) -> int:
    receipt_gate = evaluate_approval_receipt_gate(
        approval_id=approval_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    paper_confirmation_accepted = confirmation == PAPER_ORDER_CONFIRMATION

    print("APPROVAL-GATED PAPER ARM REPORT")
    print(f"Approval id: {receipt_gate.approval_id}")
    print(f"Approval path: {receipt_gate.approval_path}")
    print(f"Approval status: {receipt_gate.approval_status}")
    print(f"Approval gate allowed: {str(receipt_gate.allowed).lower()}")
    print(f"Approval gate blocked reasons: {receipt_gate.blocked_reasons}")
    print(f"Armed paper execution requested: {str(enable_real_paper_execution).lower()}")
    print(f"Paper confirmation accepted: {str(paper_confirmation_accepted).lower()}")

    if not receipt_gate.allowed:
        print("Approval-gated decision: BLOCKED_BY_APPROVAL_RECEIPT_GATE")
        print("Wrapped workflow attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    if enable_real_paper_execution and not paper_confirmation_accepted:
        print("Approval-gated decision: BLOCKED_BY_PAPER_CONFIRMATION")
        print("Wrapped workflow attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    command = [
        sys.executable,
        "-m",
        "scripts.run_fetch_then_real_paper_executor",
        "--symbol",
        symbol,
        "--limit",
        str(limit),
        "--feed",
        feed,
    ]

    if env_file is not None:
        command.extend(["--env-file", str(env_file)])

    if enable_real_paper_execution and paper_confirmation_accepted:
        command.extend(
            [
                "--enable-real-paper-execution",
                "--confirmation",
                PAPER_ORDER_CONFIRMATION,
            ]
        )

    print("Approval-gated decision: WORKFLOW_ALLOWED")
    print("Wrapped workflow attempted: true")
    print("Wrapped command:")
    print(" ".join(command))

    workflow_runner = injected_workflow_runner or _default_workflow_runner
    completed = workflow_runner(command)

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    returncode = int(getattr(completed, "returncode", 1))

    print(f"Wrapped workflow return code: {returncode}")
    print("Wrapped workflow stdout:")
    print(stdout)

    if stderr:
        print("Wrapped workflow stderr:")
        print(stderr)

    broker_order_call_performed = _workflow_indicates_broker_order(stdout)

    print(f"Broker order call performed: {str(broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")

    return returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paper arming workflow only after approval receipt gate passes.")
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--enable-real-paper-execution", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_approval_gated_paper_arm(
        approval_id=args.approval_id,
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        enable_real_paper_execution=args.enable_real_paper_execution,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
