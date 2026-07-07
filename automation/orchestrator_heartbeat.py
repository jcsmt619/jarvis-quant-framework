from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

HEARTBEAT_FILE_NAME = "orchestrator_heartbeat.json"


@dataclass(frozen=True)
class OrchestratorHeartbeat:
    session_id: str
    timestamp_utc: str
    cycle_number: int | None
    symbol: str
    engine: str
    last_decision: str
    cycles_attempted: int
    max_cycles: int
    stop_requested: bool
    pause_requested: bool
    resume_marker_present: bool
    audit_ledger_path: str
    session_manifest_path: str
    real_email_send_enabled: bool
    inbox_processing_enabled: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False
    notes: list[str] | None = None


def timestamp_utc(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).isoformat()


def heartbeat_path(orchestrator_dir: Path = Path("reports/orchestrator")) -> Path:
    return orchestrator_dir / HEARTBEAT_FILE_NAME


def build_heartbeat(
    *,
    session_id: str,
    cycle_number: int | None,
    symbol: str,
    engine: str,
    last_decision: str,
    cycles_attempted: int,
    max_cycles: int,
    stop_requested: bool,
    pause_requested: bool,
    resume_marker_present: bool,
    audit_ledger_path: Path,
    session_manifest_path: Path,
    real_email_send_enabled: bool,
    notes: list[str] | None = None,
    now: datetime | None = None,
) -> OrchestratorHeartbeat:
    return OrchestratorHeartbeat(
        session_id=session_id,
        timestamp_utc=timestamp_utc(now),
        cycle_number=cycle_number,
        symbol=symbol,
        engine=engine,
        last_decision=last_decision,
        cycles_attempted=cycles_attempted,
        max_cycles=max_cycles,
        stop_requested=stop_requested,
        pause_requested=pause_requested,
        resume_marker_present=resume_marker_present,
        audit_ledger_path=str(audit_ledger_path),
        session_manifest_path=str(session_manifest_path),
        real_email_send_enabled=real_email_send_enabled,
        inbox_processing_enabled=False,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
        notes=notes or [],
    )


def write_heartbeat(
    heartbeat: OrchestratorHeartbeat,
    *,
    path: Path = Path("reports/orchestrator/orchestrator_heartbeat.json"),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(heartbeat), indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_heartbeat(path: Path = Path("reports/orchestrator/orchestrator_heartbeat.json")) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
