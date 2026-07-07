from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from scripts.run_local_autonomous_orchestrator import run_local_autonomous_orchestrator

SAFE_MULTI_CYCLE_CONFIRMATION = "I_UNDERSTAND_THIS_RUNS_MULTIPLE_SAFE_CYCLES"
MIN_SAFE_MULTI_CYCLES = 2
MAX_SAFE_MULTI_CYCLES = 20
MAX_SAFE_SLEEP_SECONDS = 3600.0


def _default_orchestrator_runner(**kwargs) -> int:
    return run_local_autonomous_orchestrator(**kwargs)


def run_safe_multi_cycle_orchestrator(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    orchestrator_dir: Path = Path("reports/orchestrator"),
    audit_dir: Path | None = None,
    session_dir: Path | None = None,
    session_id: str | None = None,
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    engine: str = "Wealth",
    max_cycles: int = 2,
    sleep_seconds: float = 0.0,
    confirmation: str | None = None,
    injected_orchestrator_runner: Callable[..., int] | None = None,
) -> int:
    confirmation_accepted = confirmation == SAFE_MULTI_CYCLE_CONFIRMATION

    print("SAFE MULTI-CYCLE ORCHESTRATOR REPORT")
    print(f"Symbol: {symbol}")
    print(f"Engine: {engine}")
    print(f"Requested max cycles: {max_cycles}")
    print(f"Requested sleep seconds: {sleep_seconds}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"Minimum safe cycles: {MIN_SAFE_MULTI_CYCLES}")
    print(f"Maximum safe cycles: {MAX_SAFE_MULTI_CYCLES}")
    print(f"Maximum safe sleep seconds: {MAX_SAFE_SLEEP_SECONDS}")
    print("Real email send enabled: false")
    print("Inbox processing enabled: false")
    print("Paper arm enabled: false")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")

    if not confirmation_accepted:
        print("SAFE MULTI-CYCLE DECISION: BLOCKED_CONFIRMATION_NOT_ACCEPTED")
        print("Underlying orchestrator attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    if max_cycles < MIN_SAFE_MULTI_CYCLES:
        print("SAFE MULTI-CYCLE DECISION: BLOCKED_TOO_FEW_CYCLES")
        print("Underlying orchestrator attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    if max_cycles > MAX_SAFE_MULTI_CYCLES:
        print("SAFE MULTI-CYCLE DECISION: BLOCKED_TOO_MANY_CYCLES")
        print("Underlying orchestrator attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    if sleep_seconds < 0:
        print("SAFE MULTI-CYCLE DECISION: BLOCKED_NEGATIVE_SLEEP")
        print("Underlying orchestrator attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    if sleep_seconds > MAX_SAFE_SLEEP_SECONDS:
        print("SAFE MULTI-CYCLE DECISION: BLOCKED_SLEEP_TOO_LONG")
        print("Underlying orchestrator attempted: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    runner = injected_orchestrator_runner or _default_orchestrator_runner

    print("SAFE MULTI-CYCLE DECISION: ORCHESTRATOR_ALLOWED")
    print("Underlying orchestrator attempted: true")

    code = runner(
        env_file=env_file,
        approvals_dir=approvals_dir,
        orchestrator_dir=orchestrator_dir,
        audit_dir=audit_dir,
        session_dir=session_dir,
        session_id=session_id,
        symbol=symbol,
        limit=limit,
        feed=feed,
        engine=engine,
        max_cycles=max_cycles,
        sleep_seconds=sleep_seconds,
        enable_real_email_send=False,
        email_confirmation=None,
    )

    print(f"Underlying orchestrator return code: {code}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multiple local orchestrator cycles with hard safety caps.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--audit-dir", type=Path, default=None)
    parser.add_argument("--session-dir", type=Path, default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--engine", default="Wealth")
    parser.add_argument("--max-cycles", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_safe_multi_cycle_orchestrator(
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        orchestrator_dir=args.orchestrator_dir,
        audit_dir=args.audit_dir,
        session_dir=args.session_dir,
        session_id=args.session_id,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        engine=args.engine,
        max_cycles=args.max_cycles,
        sleep_seconds=args.sleep_seconds,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
