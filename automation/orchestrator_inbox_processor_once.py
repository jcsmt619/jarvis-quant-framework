from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_real_inbox_gate import evaluate_real_gmail_inbox_read_gate


@dataclass(frozen=True)
class OrchestratorInboxProcessorOnceResult:
    hook_present: bool
    processor_callable_wired: bool
    inbox_processing_requested: bool
    real_gmail_inbox_read_requested: bool
    confirmation_accepted: bool
    gate_allowed: bool
    attempted: bool
    processor_return_code: int | None
    decision: str
    blocked_reasons: list[str]
    approval_records_updated: int = 0
    real_gmail_inbox_read_performed: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def parse_approval_records_updated(output: str) -> int:
    match = re.search(r"Approval records updated:\s*(\d+)", output)
    if not match:
        return 0
    return int(match.group(1))


def _default_processor_callable(
    *,
    env_file: Path,
    max_results: int,
) -> tuple[int, str]:
    command = [
        sys.executable,
        "-m",
        "scripts.process_gmail_approvals",
        "--env-file",
        str(env_file),
        "--max-results",
        str(max_results),
        "--enable-real-inbox-read",
        "--confirmation",
        GMAIL_INBOX_READ_CONFIRMATION,
    ]

    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )

    output = completed.stdout
    if completed.stderr:
        output = output + "\nSTDERR:\n" + completed.stderr

    return completed.returncode, output


def run_orchestrator_inbox_processor_once(
    *,
    enable_inbox_processing: bool = False,
    enable_real_gmail_inbox_read: bool = False,
    confirmation: str | None = None,
    env_file: Path | None = Path(".env"),
    max_results: int = 25,
    processor_callable: Callable[[], int] | None = None,
) -> OrchestratorInboxProcessorOnceResult:
    gate = evaluate_real_gmail_inbox_read_gate(
        enable_inbox_processing=enable_inbox_processing,
        enable_real_gmail_inbox_read=enable_real_gmail_inbox_read,
        confirmation=confirmation,
    )

    callable_wired = True

    if not gate.gate_allowed:
        return OrchestratorInboxProcessorOnceResult(
            hook_present=True,
            processor_callable_wired=callable_wired,
            inbox_processing_requested=gate.inbox_processing_requested,
            real_gmail_inbox_read_requested=gate.real_gmail_inbox_read_requested,
            confirmation_accepted=gate.confirmation_accepted,
            gate_allowed=False,
            attempted=False,
            processor_return_code=None,
            decision=gate.decision,
            blocked_reasons=gate.blocked_reasons,
            approval_records_updated=0,
            real_gmail_inbox_read_performed=False,
            paper_arm_enabled=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    if processor_callable is not None:
        updated_count = int(processor_callable())
        return OrchestratorInboxProcessorOnceResult(
            hook_present=True,
            processor_callable_wired=True,
            inbox_processing_requested=True,
            real_gmail_inbox_read_requested=True,
            confirmation_accepted=True,
            gate_allowed=True,
            attempted=True,
            processor_return_code=0,
            decision="PROCESSOR_ATTEMPTED_READ_ONLY",
            blocked_reasons=[],
            approval_records_updated=updated_count,
            real_gmail_inbox_read_performed=True,
            paper_arm_enabled=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    actual_env_file = env_file or Path(".env")
    return_code, output = _default_processor_callable(
        env_file=actual_env_file,
        max_results=max_results,
    )
    updated_count = parse_approval_records_updated(output)

    if return_code != 0:
        return OrchestratorInboxProcessorOnceResult(
            hook_present=True,
            processor_callable_wired=True,
            inbox_processing_requested=True,
            real_gmail_inbox_read_requested=True,
            confirmation_accepted=True,
            gate_allowed=True,
            attempted=True,
            processor_return_code=return_code,
            decision="PROCESSOR_FAILED_READ_ONLY",
            blocked_reasons=["Gmail approval processor returned non-zero exit code"],
            approval_records_updated=updated_count,
            real_gmail_inbox_read_performed=False,
            paper_arm_enabled=False,
            broker_order_call_performed=False,
            live_trading_enabled=False,
        )

    return OrchestratorInboxProcessorOnceResult(
        hook_present=True,
        processor_callable_wired=True,
        inbox_processing_requested=True,
        real_gmail_inbox_read_requested=True,
        confirmation_accepted=True,
        gate_allowed=True,
        attempted=True,
        processor_return_code=0,
        decision="PROCESSOR_ATTEMPTED_READ_ONLY",
        blocked_reasons=[],
        approval_records_updated=updated_count,
        real_gmail_inbox_read_performed=True,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
