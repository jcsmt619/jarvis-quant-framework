from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

SESSION_MANIFESTS_DIR_NAME = "sessions"


@dataclass(frozen=True)
class OrchestratorSessionManifest:
    session_id: str
    started_at_utc: str
    ended_at_utc: str
    symbol: str
    engine: str
    max_cycles: int
    sleep_seconds: float
    cycles_attempted: int
    final_decision: str
    final_return_code: int
    approvals_dir: str
    orchestrator_dir: str
    audit_ledger_path: str
    stop_requested_at_end: bool
    pause_requested_at_end: bool
    resume_marker_present_at_end: bool
    real_email_send_enabled: bool
    inbox_processing_enabled: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False
    notes: list[str] | None = None


def timestamp_utc(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).isoformat()


def create_session_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(tz=UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"orchestrator_{stamp}_{uuid4().hex[:8]}"


def session_manifest_path(
    *,
    session_id: str,
    session_dir: Path = Path("reports/orchestrator/sessions"),
) -> Path:
    return session_dir / f"{session_id}.json"


def build_session_manifest(
    *,
    session_id: str,
    started_at_utc: str,
    ended_at_utc: str,
    symbol: str,
    engine: str,
    max_cycles: int,
    sleep_seconds: float,
    cycles_attempted: int,
    final_decision: str,
    final_return_code: int,
    approvals_dir: Path,
    orchestrator_dir: Path,
    audit_ledger_path: Path,
    stop_requested_at_end: bool,
    pause_requested_at_end: bool,
    resume_marker_present_at_end: bool,
    real_email_send_enabled: bool,
    notes: list[str] | None = None,
) -> OrchestratorSessionManifest:
    return OrchestratorSessionManifest(
        session_id=session_id,
        started_at_utc=started_at_utc,
        ended_at_utc=ended_at_utc,
        symbol=symbol,
        engine=engine,
        max_cycles=max_cycles,
        sleep_seconds=sleep_seconds,
        cycles_attempted=cycles_attempted,
        final_decision=final_decision,
        final_return_code=final_return_code,
        approvals_dir=str(approvals_dir),
        orchestrator_dir=str(orchestrator_dir),
        audit_ledger_path=str(audit_ledger_path),
        stop_requested_at_end=stop_requested_at_end,
        pause_requested_at_end=pause_requested_at_end,
        resume_marker_present_at_end=resume_marker_present_at_end,
        real_email_send_enabled=real_email_send_enabled,
        inbox_processing_enabled=False,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
        notes=notes or [],
    )


def write_session_manifest(
    manifest: OrchestratorSessionManifest,
    *,
    session_dir: Path = Path("reports/orchestrator/sessions"),
) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_manifest_path(session_id=manifest.session_id, session_dir=session_dir)
    path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_session_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_session_manifests(
    *,
    session_dir: Path = Path("reports/orchestrator/sessions"),
) -> list[dict]:
    if not session_dir.exists():
        return []

    manifests: list[dict] = []
    for path in sorted(session_dir.glob("orchestrator_*.json")):
        item = read_session_manifest(path)
        item["_path"] = str(path)
        manifests.append(item)

    return manifests
