from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

STOP_FILE_NAME = "JARVIS_STOP"
PAUSE_FILE_NAME = "JARVIS_PAUSE"
RESUME_FILE_NAME = "JARVIS_RESUME"


@dataclass(frozen=True)
class OrchestratorControlState:
    orchestrator_dir: str
    stop_file: str
    pause_file: str
    resume_file: str
    stop_requested: bool
    pause_requested: bool
    resume_marker_present: bool
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


def _ensure_dir(orchestrator_dir: Path) -> None:
    orchestrator_dir.mkdir(parents=True, exist_ok=True)


def read_control_state(orchestrator_dir: Path = Path("reports/orchestrator")) -> OrchestratorControlState:
    _ensure_dir(orchestrator_dir)
    stop_file = orchestrator_dir / STOP_FILE_NAME
    pause_file = orchestrator_dir / PAUSE_FILE_NAME
    resume_file = orchestrator_dir / RESUME_FILE_NAME

    return OrchestratorControlState(
        orchestrator_dir=str(orchestrator_dir),
        stop_file=str(stop_file),
        pause_file=str(pause_file),
        resume_file=str(resume_file),
        stop_requested=stop_file.exists(),
        pause_requested=pause_file.exists(),
        resume_marker_present=resume_file.exists(),
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def request_stop(orchestrator_dir: Path = Path("reports/orchestrator"), *, note: str = "") -> OrchestratorControlState:
    _ensure_dir(orchestrator_dir)
    text = f"STOP requested at {_timestamp()}"
    if note:
        text += f"\n{note}"
    (orchestrator_dir / STOP_FILE_NAME).write_text(text, encoding="utf-8")
    return read_control_state(orchestrator_dir)


def request_pause(orchestrator_dir: Path = Path("reports/orchestrator"), *, note: str = "") -> OrchestratorControlState:
    _ensure_dir(orchestrator_dir)
    text = f"PAUSE requested at {_timestamp()}"
    if note:
        text += f"\n{note}"
    (orchestrator_dir / PAUSE_FILE_NAME).write_text(text, encoding="utf-8")
    return read_control_state(orchestrator_dir)


def request_resume(orchestrator_dir: Path = Path("reports/orchestrator"), *, note: str = "") -> OrchestratorControlState:
    _ensure_dir(orchestrator_dir)
    pause_file = orchestrator_dir / PAUSE_FILE_NAME
    if pause_file.exists():
        pause_file.unlink()

    text = f"RESUME requested at {_timestamp()}"
    if note:
        text += f"\n{note}"
    (orchestrator_dir / RESUME_FILE_NAME).write_text(text, encoding="utf-8")
    return read_control_state(orchestrator_dir)


def clear_controls(orchestrator_dir: Path = Path("reports/orchestrator")) -> OrchestratorControlState:
    _ensure_dir(orchestrator_dir)
    for name in (STOP_FILE_NAME, PAUSE_FILE_NAME, RESUME_FILE_NAME):
        path = orchestrator_dir / name
        if path.exists():
            path.unlink()
    return read_control_state(orchestrator_dir)
