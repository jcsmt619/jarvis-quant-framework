from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automation.orchestrator_audit import read_audit_events
from automation.orchestrator_controls import read_control_state
from automation.orchestrator_heartbeat import HEARTBEAT_FILE_NAME, read_heartbeat
from automation.orchestrator_session import SESSION_MANIFESTS_DIR_NAME, list_session_manifests


@dataclass(frozen=True)
class OrchestratorHealthResult:
    env_file: str
    env_file_present: bool
    orchestrator_dir: str
    stop_requested: bool
    pause_requested: bool
    resume_marker_present: bool
    heartbeat_path: str
    heartbeat_present: bool
    heartbeat_readable: bool
    sessions_dir: str
    sessions_count: int
    sessions_readable: bool
    audit_dir: str
    audit_events_count: int
    audit_readable: bool
    safe_to_run: bool
    blocked_reasons: list[str]
    real_email_send_enabled: bool = False
    inbox_processing_enabled: bool = False
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def evaluate_orchestrator_health(
    *,
    env_file: Path = Path(".env"),
    orchestrator_dir: Path = Path("reports/orchestrator"),
    require_env_file: bool = True,
) -> OrchestratorHealthResult:
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    blocked_reasons: list[str] = []

    env_file_present = env_file.exists()
    if require_env_file and not env_file_present:
        blocked_reasons.append(f"env file not found: {env_file}")

    controls = read_control_state(orchestrator_dir)
    if controls.stop_requested:
        blocked_reasons.append("JARVIS_STOP is present")

    if controls.pause_requested:
        blocked_reasons.append("JARVIS_PAUSE is present")

    heartbeat_path = orchestrator_dir / HEARTBEAT_FILE_NAME
    heartbeat_present = heartbeat_path.exists()
    heartbeat_readable = True

    if heartbeat_present:
        try:
            read_heartbeat(heartbeat_path)
        except Exception as exc:
            heartbeat_readable = False
            blocked_reasons.append(f"heartbeat is not readable: {exc}")

    sessions_dir = orchestrator_dir / SESSION_MANIFESTS_DIR_NAME
    sessions_count = 0
    sessions_readable = True

    try:
        sessions_count = len(list_session_manifests(session_dir=sessions_dir))
    except Exception as exc:
        sessions_readable = False
        blocked_reasons.append(f"session manifests are not readable: {exc}")

    audit_dir = orchestrator_dir / "audit"
    audit_events_count = 0
    audit_readable = True

    try:
        audit_events_count = len(read_audit_events(audit_dir=audit_dir))
    except Exception as exc:
        audit_readable = False
        blocked_reasons.append(f"audit ledger is not readable: {exc}")

    safe_to_run = len(blocked_reasons) == 0

    return OrchestratorHealthResult(
        env_file=str(env_file),
        env_file_present=env_file_present,
        orchestrator_dir=str(orchestrator_dir),
        stop_requested=controls.stop_requested,
        pause_requested=controls.pause_requested,
        resume_marker_present=controls.resume_marker_present,
        heartbeat_path=str(heartbeat_path),
        heartbeat_present=heartbeat_present,
        heartbeat_readable=heartbeat_readable,
        sessions_dir=str(sessions_dir),
        sessions_count=sessions_count,
        sessions_readable=sessions_readable,
        audit_dir=str(audit_dir),
        audit_events_count=audit_events_count,
        audit_readable=audit_readable,
        safe_to_run=safe_to_run,
        blocked_reasons=blocked_reasons,
        real_email_send_enabled=False,
        inbox_processing_enabled=False,
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
