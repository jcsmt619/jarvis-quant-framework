from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable

from automation.orchestrator_controls import read_control_state
from paper_trading.email_alerts import GMAIL_EMAIL_CONFIRMATION
from scripts.run_ready_to_arm_approval_request import run_ready_to_arm_approval_request


def _default_cycle_runner(
    *,
    env_file: Path | None,
    approvals_dir: Path,
    symbol: str,
    limit: int,
    feed: str,
    engine: str,
    enable_real_email_send: bool,
    email_confirmation: str | None,
) -> int:
    return run_ready_to_arm_approval_request(
        env_file=env_file,
        approvals_dir=approvals_dir,
        symbol=symbol,
        limit=limit,
        feed=feed,
        engine=engine,
        enable_real_email_send=enable_real_email_send,
        confirmation=email_confirmation,
    )


def run_local_autonomous_orchestrator(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    orchestrator_dir: Path = Path("reports/orchestrator"),
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    engine: str = "Wealth",
    max_cycles: int = 1,
    sleep_seconds: float = 0.0,
    enable_real_email_send: bool = False,
    email_confirmation: str | None = None,
    injected_cycle_runner: Callable[..., int] | None = None,
) -> int:
    approvals_dir.mkdir(parents=True, exist_ok=True)
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    control_state = read_control_state(orchestrator_dir)
    email_confirmation_accepted = email_confirmation == GMAIL_EMAIL_CONFIRMATION

    print("LOCAL AUTONOMOUS ORCHESTRATOR REPORT")
    print(f"Symbol: {symbol}")
    print(f"Engine: {engine}")
    print(f"Max cycles: {max_cycles}")
    print(f"Sleep seconds: {sleep_seconds}")
    print(f"Stop file: {control_state.stop_file}")
    print(f"Pause file: {control_state.pause_file}")
    print(f"Resume file: {control_state.resume_file}")
    print(f"Stop requested: {str(control_state.stop_requested).lower()}")
    print(f"Pause requested: {str(control_state.pause_requested).lower()}")
    print(f"Resume marker present: {str(control_state.resume_marker_present).lower()}")
    print(f"Real email send enabled: {str(enable_real_email_send).lower()}")
    print(f"Email confirmation accepted: {str(email_confirmation_accepted).lower()}")
    print("Inbox processing enabled: false")
    print("Paper arm enabled: false")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")

    if max_cycles <= 0:
        print("ORCHESTRATOR DECISION: BLOCKED_INVALID_MAX_CYCLES")
        print("Cycles attempted: 0")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    runner = injected_cycle_runner or _default_cycle_runner
    cycles_attempted = 0

    for cycle_number in range(1, max_cycles + 1):
        control_state = read_control_state(orchestrator_dir)

        if control_state.stop_requested:
            print(f"ORCHESTRATOR DECISION: STOP_FILE_PRESENT_BEFORE_CYCLE_{cycle_number}")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return 0

        if control_state.pause_requested:
            print(f"ORCHESTRATOR DECISION: PAUSE_FILE_PRESENT_BEFORE_CYCLE_{cycle_number}")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return 0

        print(f"--- ORCHESTRATOR CYCLE {cycle_number} START ---")
        code = runner(
            env_file=env_file,
            approvals_dir=approvals_dir,
            symbol=symbol,
            limit=limit,
            feed=feed,
            engine=engine,
            enable_real_email_send=enable_real_email_send,
            email_confirmation=email_confirmation,
        )
        cycles_attempted += 1

        print(f"--- ORCHESTRATOR CYCLE {cycle_number} END ---")
        print(f"Cycle return code: {code}")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")

        if code != 0:
            print("ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return code

        if cycle_number < max_cycles and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    print("ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES")
    print(f"Cycles attempted: {cycles_attempted}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local autonomous orchestrator in safe approval-request mode.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--engine", default="Wealth")
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--enable-real-email-send", action="store_true")
    parser.add_argument("--email-confirmation", default=None)
    args = parser.parse_args()

    return run_local_autonomous_orchestrator(
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        orchestrator_dir=args.orchestrator_dir,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        engine=args.engine,
        max_cycles=args.max_cycles,
        sleep_seconds=args.sleep_seconds,
        enable_real_email_send=args.enable_real_email_send,
        email_confirmation=args.email_confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
