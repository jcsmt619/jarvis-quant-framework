from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from automation.approval_gateway import create_approval_record, write_approval_record
from automation.approval_receipt_gate import evaluate_approval_receipt_gate

GMAIL_INBOX_READ_CONFIRMATION = "I_UNDERSTAND_THIS_READS_MY_GMAIL_INBOX"


@dataclass(frozen=True)
class GmailApprovalDrillResult:
    mode: str
    approval_id: str | None
    approval_record_created: bool
    inbox_processor_attempted: bool
    receipt_gate_allowed: bool
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _latest_id_path(approvals_dir: Path) -> Path:
    return approvals_dir / "latest_gmail_approval_drill_id.txt"


def _default_processor_runner(command: list[str]) -> Any:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def _resolve_approval_id(*, approval_id: str | None, approvals_dir: Path) -> str | None:
    cleaned = (approval_id or "").strip()
    if cleaned:
        return cleaned

    latest = _latest_id_path(approvals_dir)
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip()

    return None


def run_gmail_approval_drill(
    *,
    mode: str,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    approval_id: str | None = None,
    enable_real_inbox_read: bool = False,
    confirmation: str | None = None,
    max_results: int = 25,
    now: datetime | None = None,
    injected_processor_runner: Callable[[list[str]], Any] | None = None,
) -> int:
    approvals_dir.mkdir(parents=True, exist_ok=True)
    normalized_mode = mode.strip().lower()

    if normalized_mode == "create":
        record = create_approval_record(
            target="READY_TO_ARM_REVIEW",
            source="gmail_drill",
            note="10B-8 real Gmail approval drill",
            now=now,
        )
        approval_path = write_approval_record(record, output_dir=approvals_dir)
        _latest_id_path(approvals_dir).write_text(record.approval_id, encoding="utf-8")

        pending_gate = evaluate_approval_receipt_gate(
            approval_id=record.approval_id,
            approvals_dir=approvals_dir,
            now=now,
        )

        print("GMAIL APPROVAL DRILL REPORT: PASS")
        print("Mode: create")
        print("Approval record created: true")
        print(f"Approval id: {record.approval_id}")
        print(f"Approval path: {approval_path}")
        print(f"Latest approval id path: {_latest_id_path(approvals_dir)}")
        print(f"Pending gate allowed: {str(pending_gate.allowed).lower()}")
        print(f"Pending gate blocked reasons: {pending_gate.blocked_reasons}")
        print("Send this exact email body from your authorized Gmail to the Jarvis Gmail inbox:")
        print(f"APPROVE {record.approval_id}")
        print("Inbox processor attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    resolved_id = _resolve_approval_id(approval_id=approval_id, approvals_dir=approvals_dir)

    if normalized_mode == "verify":
        gate = evaluate_approval_receipt_gate(
            approval_id=resolved_id,
            approvals_dir=approvals_dir,
            now=now,
        )

        print("GMAIL APPROVAL DRILL REPORT: PASS")
        print("Mode: verify")
        print(f"Approval id: {gate.approval_id}")
        print(f"Approval path: {gate.approval_path}")
        print(f"Receipt gate allowed: {str(gate.allowed).lower()}")
        print(f"Receipt gate status: {gate.approval_status}")
        print(f"Receipt gate blocked reasons: {gate.blocked_reasons}")
        print("Inbox processor attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    if normalized_mode != "process":
        print("GMAIL APPROVAL DRILL REPORT: FAIL")
        print(f"Unsupported mode: {mode}")
        print("Inbox processor attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    before_gate = evaluate_approval_receipt_gate(
        approval_id=resolved_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION

    print("GMAIL APPROVAL DRILL REPORT")
    print("Mode: process")
    print(f"Approval id: {before_gate.approval_id}")
    print(f"Approval path: {before_gate.approval_path}")
    print(f"Receipt gate allowed before inbox processing: {str(before_gate.allowed).lower()}")
    print(f"Receipt gate status before inbox processing: {before_gate.approval_status}")
    print(f"Real inbox read enabled: {str(enable_real_inbox_read).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")

    if not enable_real_inbox_read:
        print("GMAIL APPROVAL DRILL REPORT: PASS")
        print("Gmail inbox processor decision: BLOCKED_REAL_INBOX_READ_DISABLED")
        print("Inbox processor attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    if not confirmation_accepted:
        print("GMAIL APPROVAL DRILL REPORT: PASS")
        print("Gmail inbox processor decision: BLOCKED_CONFIRMATION_NOT_ACCEPTED")
        print("Inbox processor attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    command = [
        sys.executable,
        "-m",
        "scripts.process_gmail_approvals",
        "--max-results",
        str(max_results),
        "--enable-real-inbox-read",
        "--confirmation",
        GMAIL_INBOX_READ_CONFIRMATION,
    ]

    if env_file is not None:
        command.extend(["--env-file", str(env_file)])

    print("Gmail inbox processor decision: PROCESSOR_ALLOWED")
    print("Inbox processor attempted: true")
    print("Inbox processor command:")
    print(" ".join(command))

    runner = injected_processor_runner or _default_processor_runner
    completed = runner(command)

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    returncode = int(getattr(completed, "returncode", 1))

    print(f"Inbox processor return code: {returncode}")
    print("Inbox processor stdout:")
    print(stdout)

    if stderr:
        print("Inbox processor stderr:")
        print(stderr)

    after_gate = evaluate_approval_receipt_gate(
        approval_id=resolved_id,
        approvals_dir=approvals_dir,
        now=now,
    )

    print("GMAIL APPROVAL DRILL REPORT: PASS" if returncode == 0 else "GMAIL APPROVAL DRILL REPORT: FAIL")
    print(f"Receipt gate allowed after inbox processing: {str(after_gate.allowed).lower()}")
    print(f"Receipt gate status after inbox processing: {after_gate.approval_status}")
    print(f"Receipt gate blocked reasons after inbox processing: {after_gate.blocked_reasons}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")

    return returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real Gmail approval drill without broker orders.")
    parser.add_argument("--mode", required=True, choices=["create", "process", "verify"])
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--approval-id", default=None)
    parser.add_argument("--enable-real-inbox-read", action="store_true")
    parser.add_argument("--confirmation", default=None)
    parser.add_argument("--max-results", type=int, default=25)
    args = parser.parse_args()

    return run_gmail_approval_drill(
        mode=args.mode,
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        approval_id=args.approval_id,
        enable_real_inbox_read=args.enable_real_inbox_read,
        confirmation=args.confirmation,
        max_results=args.max_results,
    )


if __name__ == "__main__":
    raise SystemExit(main())
