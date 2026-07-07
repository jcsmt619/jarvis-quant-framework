from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from automation.orchestrator_audit import (
    AUDIT_LEDGER_FILE_NAME,
    append_audit_event,
    build_audit_event,
)
from automation.orchestrator_controls import read_control_state
from automation.orchestrator_heartbeat import (
    HEARTBEAT_FILE_NAME,
    build_heartbeat,
    write_heartbeat,
)
from automation.orchestrator_session import (
    SESSION_MANIFESTS_DIR_NAME,
    build_session_manifest,
    create_session_id,
    timestamp_utc,
    write_session_manifest,
)
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


def _write_audit(
    *,
    audit_dir: Path,
    event_type: str,
    cycle_number: int | None,
    symbol: str,
    engine: str,
    decision: str,
    cycle_return_code: int | None,
    control_state,
    enable_real_email_send: bool,
    notes: list[str] | None = None,
    now: datetime | None = None,
) -> Path:
    event = build_audit_event(
        event_type=event_type,
        cycle_number=cycle_number,
        symbol=symbol,
        engine=engine,
        decision=decision,
        cycle_return_code=cycle_return_code,
        stop_requested=control_state.stop_requested,
        pause_requested=control_state.pause_requested,
        resume_marker_present=control_state.resume_marker_present,
        real_email_send_enabled=enable_real_email_send,
        notes=notes or [],
        now=now,
    )
    return append_audit_event(event, audit_dir=audit_dir)


def _write_heartbeat(
    *,
    heartbeat_file: Path,
    session_id: str,
    cycle_number: int | None,
    symbol: str,
    engine: str,
    last_decision: str,
    cycles_attempted: int,
    max_cycles: int,
    control_state,
    audit_ledger_path: Path,
    session_manifest_path: Path,
    enable_real_email_send: bool,
    notes: list[str] | None = None,
    now: datetime | None = None,
) -> Path:
    hb = build_heartbeat(
        session_id=session_id,
        cycle_number=cycle_number,
        symbol=symbol,
        engine=engine,
        last_decision=last_decision,
        cycles_attempted=cycles_attempted,
        max_cycles=max_cycles,
        stop_requested=control_state.stop_requested,
        pause_requested=control_state.pause_requested,
        resume_marker_present=control_state.resume_marker_present,
        audit_ledger_path=audit_ledger_path,
        session_manifest_path=session_manifest_path,
        real_email_send_enabled=enable_real_email_send,
        notes=notes or [],
        now=now,
    )
    return write_heartbeat(hb, path=heartbeat_file)


def run_local_autonomous_orchestrator(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    orchestrator_dir: Path = Path("reports/orchestrator"),
    audit_dir: Path | None = None,
    session_dir: Path | None = None,
    heartbeat_file: Path | None = None,
    session_id: str | None = None,
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    engine: str = "Wealth",
    max_cycles: int = 1,
    sleep_seconds: float = 0.0,
    enable_real_email_send: bool = False,
    email_confirmation: str | None = None,
    injected_cycle_runner: Callable[..., int] | None = None,
    now: datetime | None = None,
) -> int:
    approvals_dir.mkdir(parents=True, exist_ok=True)
    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = audit_dir or (orchestrator_dir / "audit")
    session_dir = session_dir or (orchestrator_dir / SESSION_MANIFESTS_DIR_NAME)
    heartbeat_file = heartbeat_file or (orchestrator_dir / HEARTBEAT_FILE_NAME)
    audit_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    actual_session_id = session_id or create_session_id(now)
    started_at_utc = timestamp_utc(now)
    control_state = read_control_state(orchestrator_dir)
    email_confirmation_accepted = email_confirmation == GMAIL_EMAIL_CONFIRMATION
    ledger_path = audit_dir / AUDIT_LEDGER_FILE_NAME
    session_manifest_path = session_dir / f"{actual_session_id}.json"

    def finalize(final_decision: str, final_return_code: int, cycles_attempted: int, notes: list[str] | None = None) -> int:
        end_state = read_control_state(orchestrator_dir)
        manifest = build_session_manifest(
            session_id=actual_session_id,
            started_at_utc=started_at_utc,
            ended_at_utc=timestamp_utc(now),
            symbol=symbol,
            engine=engine,
            max_cycles=max_cycles,
            sleep_seconds=sleep_seconds,
            cycles_attempted=cycles_attempted,
            final_decision=final_decision,
            final_return_code=final_return_code,
            approvals_dir=approvals_dir,
            orchestrator_dir=orchestrator_dir,
            audit_ledger_path=ledger_path,
            stop_requested_at_end=end_state.stop_requested,
            pause_requested_at_end=end_state.pause_requested,
            resume_marker_present_at_end=end_state.resume_marker_present,
            real_email_send_enabled=enable_real_email_send,
            notes=notes or [],
        )
        path = write_session_manifest(manifest, session_dir=session_dir)
        _write_heartbeat(
            heartbeat_file=heartbeat_file,
            session_id=actual_session_id,
            cycle_number=None,
            symbol=symbol,
            engine=engine,
            last_decision=final_decision,
            cycles_attempted=cycles_attempted,
            max_cycles=max_cycles,
            control_state=end_state,
            audit_ledger_path=ledger_path,
            session_manifest_path=session_manifest_path,
            enable_real_email_send=enable_real_email_send,
            notes=notes or [],
            now=now,
        )
        print(f"Session manifest written: {path}")
        print(f"Heartbeat written: {heartbeat_file}")
        return final_return_code

    _write_heartbeat(
        heartbeat_file=heartbeat_file,
        session_id=actual_session_id,
        cycle_number=None,
        symbol=symbol,
        engine=engine,
        last_decision="SESSION_STARTED",
        cycles_attempted=0,
        max_cycles=max_cycles,
        control_state=control_state,
        audit_ledger_path=ledger_path,
        session_manifest_path=session_manifest_path,
        enable_real_email_send=enable_real_email_send,
        notes=["session started"],
        now=now,
    )

    print("LOCAL AUTONOMOUS ORCHESTRATOR REPORT")
    print(f"Session id: {actual_session_id}")
    print(f"Session manifest path: {session_manifest_path}")
    print(f"Heartbeat path: {heartbeat_file}")
    print(f"Symbol: {symbol}")
    print(f"Engine: {engine}")
    print(f"Max cycles: {max_cycles}")
    print(f"Sleep seconds: {sleep_seconds}")
    print(f"Stop file: {control_state.stop_file}")
    print(f"Pause file: {control_state.pause_file}")
    print(f"Resume file: {control_state.resume_file}")
    print(f"Audit ledger path: {ledger_path}")
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
        _write_audit(
            audit_dir=audit_dir,
            event_type="orchestrator_blocked",
            cycle_number=None,
            symbol=symbol,
            engine=engine,
            decision="BLOCKED_INVALID_MAX_CYCLES",
            cycle_return_code=2,
            control_state=control_state,
            enable_real_email_send=enable_real_email_send,
            notes=["max_cycles must be greater than zero"],
            now=now,
        )
        print("ORCHESTRATOR DECISION: BLOCKED_INVALID_MAX_CYCLES")
        print("Cycles attempted: 0")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return finalize("BLOCKED_INVALID_MAX_CYCLES", 2, 0, ["max_cycles must be greater than zero"])

    runner = injected_cycle_runner or _default_cycle_runner
    cycles_attempted = 0

    for cycle_number in range(1, max_cycles + 1):
        control_state = read_control_state(orchestrator_dir)

        if control_state.stop_requested:
            decision = f"STOP_FILE_PRESENT_BEFORE_CYCLE_{cycle_number}"
            _write_audit(
                audit_dir=audit_dir,
                event_type="orchestrator_control_block",
                cycle_number=cycle_number,
                symbol=symbol,
                engine=engine,
                decision=decision,
                cycle_return_code=0,
                control_state=control_state,
                enable_real_email_send=enable_real_email_send,
                notes=["stop requested before cycle"],
                now=now,
            )
            print(f"ORCHESTRATOR DECISION: {decision}")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return finalize(decision, 0, cycles_attempted, ["stop requested before cycle"])

        if control_state.pause_requested:
            decision = f"PAUSE_FILE_PRESENT_BEFORE_CYCLE_{cycle_number}"
            _write_audit(
                audit_dir=audit_dir,
                event_type="orchestrator_control_block",
                cycle_number=cycle_number,
                symbol=symbol,
                engine=engine,
                decision=decision,
                cycle_return_code=0,
                control_state=control_state,
                enable_real_email_send=enable_real_email_send,
                notes=["pause requested before cycle"],
                now=now,
            )
            print(f"ORCHESTRATOR DECISION: {decision}")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return finalize(decision, 0, cycles_attempted, ["pause requested before cycle"])

        _write_heartbeat(
            heartbeat_file=heartbeat_file,
            session_id=actual_session_id,
            cycle_number=cycle_number,
            symbol=symbol,
            engine=engine,
            last_decision="CYCLE_STARTED",
            cycles_attempted=cycles_attempted,
            max_cycles=max_cycles,
            control_state=control_state,
            audit_ledger_path=ledger_path,
            session_manifest_path=session_manifest_path,
            enable_real_email_send=enable_real_email_send,
            notes=[f"cycle {cycle_number} started"],
            now=now,
        )

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

        decision = "CYCLE_COMPLETED" if code == 0 else "STOPPED_ON_CYCLE_FAILURE"
        _write_audit(
            audit_dir=audit_dir,
            event_type="orchestrator_cycle",
            cycle_number=cycle_number,
            symbol=symbol,
            engine=engine,
            decision=decision,
            cycle_return_code=code,
            control_state=control_state,
            enable_real_email_send=enable_real_email_send,
            notes=["cycle runner returned"],
            now=now,
        )
        _write_heartbeat(
            heartbeat_file=heartbeat_file,
            session_id=actual_session_id,
            cycle_number=cycle_number,
            symbol=symbol,
            engine=engine,
            last_decision=decision,
            cycles_attempted=cycles_attempted,
            max_cycles=max_cycles,
            control_state=control_state,
            audit_ledger_path=ledger_path,
            session_manifest_path=session_manifest_path,
            enable_real_email_send=enable_real_email_send,
            notes=["cycle runner returned"],
            now=now,
        )

        print(f"--- ORCHESTRATOR CYCLE {cycle_number} END ---")
        print(f"Cycle return code: {code}")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")

        if code != 0:
            print("ORCHESTRATOR DECISION: STOPPED_ON_CYCLE_FAILURE")
            print(f"Cycles attempted: {cycles_attempted}")
            print("Broker order call performed: false")
            print("LIVE TRADING: DISABLED")
            return finalize("STOPPED_ON_CYCLE_FAILURE", code, cycles_attempted, ["cycle runner failed"])

        if cycle_number < max_cycles and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    control_state = read_control_state(orchestrator_dir)
    _write_audit(
        audit_dir=audit_dir,
        event_type="orchestrator_completed",
        cycle_number=None,
        symbol=symbol,
        engine=engine,
        decision="COMPLETED_MAX_CYCLES",
        cycle_return_code=0,
        control_state=control_state,
        enable_real_email_send=enable_real_email_send,
        notes=[f"cycles attempted: {cycles_attempted}"],
        now=now,
    )

    print("ORCHESTRATOR DECISION: COMPLETED_MAX_CYCLES")
    print(f"Cycles attempted: {cycles_attempted}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return finalize("COMPLETED_MAX_CYCLES", 0, cycles_attempted, [f"cycles attempted: {cycles_attempted}"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local autonomous orchestrator in safe approval-request mode.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--audit-dir", type=Path, default=None)
    parser.add_argument("--session-dir", type=Path, default=None)
    parser.add_argument("--heartbeat-file", type=Path, default=None)
    parser.add_argument("--session-id", default=None)
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
        audit_dir=args.audit_dir,
        session_dir=args.session_dir,
        heartbeat_file=args.heartbeat_file,
        session_id=args.session_id,
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
