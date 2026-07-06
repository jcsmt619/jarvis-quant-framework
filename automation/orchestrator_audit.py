from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

AUDIT_LEDGER_FILE_NAME = "orchestrator_audit_ledger.jsonl"


@dataclass(frozen=True)
class OrchestratorAuditEvent:
    timestamp_utc: str
    event_type: str
    cycle_number: int | None
    symbol: str
    engine: str
    decision: str
    cycle_return_code: int | None
    stop_requested: bool
    pause_requested: bool
    resume_marker_present: bool
    real_email_send_enabled: bool
    inbox_processing_enabled: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False
    notes: list[str] | None = None


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).isoformat()


def audit_ledger_path(audit_dir: Path = Path("reports/orchestrator/audit")) -> Path:
    return audit_dir / AUDIT_LEDGER_FILE_NAME


def build_audit_event(
    *,
    event_type: str,
    cycle_number: int | None,
    symbol: str,
    engine: str,
    decision: str,
    cycle_return_code: int | None,
    stop_requested: bool,
    pause_requested: bool,
    resume_marker_present: bool,
    real_email_send_enabled: bool,
    notes: list[str] | None = None,
    now: datetime | None = None,
) -> OrchestratorAuditEvent:
    return OrchestratorAuditEvent(
        timestamp_utc=_timestamp(now),
        event_type=event_type,
        cycle_number=cycle_number,
        symbol=symbol,
        engine=engine,
        decision=decision,
        cycle_return_code=cycle_return_code,
        stop_requested=stop_requested,
        pause_requested=pause_requested,
        resume_marker_present=resume_marker_present,
        real_email_send_enabled=real_email_send_enabled,
        inbox_processing_enabled=False,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
        notes=notes or [],
    )


def append_audit_event(
    event: OrchestratorAuditEvent,
    *,
    audit_dir: Path = Path("reports/orchestrator/audit"),
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    ledger = audit_ledger_path(audit_dir)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(event), sort_keys=True) + "\n")
    return ledger


def read_audit_events(
    *,
    audit_dir: Path = Path("reports/orchestrator/audit"),
) -> list[dict]:
    ledger = audit_ledger_path(audit_dir)
    if not ledger.exists():
        return []

    events: list[dict] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            events.append(json.loads(stripped))
    return events
