from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_controls import (
    clear_controls,
    read_control_state,
    request_pause,
    request_resume,
    request_stop,
)


def print_state(action: str, state) -> None:
    print("ORCHESTRATOR CONTROL REPORT: PASS")
    print(f"Action: {action}")
    print(f"Orchestrator dir: {state.orchestrator_dir}")
    print(f"Stop file: {state.stop_file}")
    print(f"Pause file: {state.pause_file}")
    print(f"Resume file: {state.resume_file}")
    print(f"Stop requested: {str(state.stop_requested).lower()}")
    print(f"Pause requested: {str(state.pause_requested).lower()}")
    print(f"Resume marker present: {str(state.resume_marker_present).lower()}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")


def run_orchestrator_control(
    *,
    action: str,
    orchestrator_dir: Path = Path("reports/orchestrator"),
    note: str = "",
) -> int:
    normalized = action.strip().lower()

    if normalized == "status":
        state = read_control_state(orchestrator_dir)
    elif normalized == "stop":
        state = request_stop(orchestrator_dir, note=note)
    elif normalized == "pause":
        state = request_pause(orchestrator_dir, note=note)
    elif normalized == "resume":
        state = request_resume(orchestrator_dir, note=note)
    elif normalized == "clear":
        state = clear_controls(orchestrator_dir)
    else:
        print("ORCHESTRATOR CONTROL REPORT: FAIL")
        print(f"Unsupported action: {action}")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 2

    print_state(normalized, state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or clear local orchestrator control files.")
    parser.add_argument("--action", required=True, choices=["status", "stop", "pause", "resume", "clear"])
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    return run_orchestrator_control(
        action=args.action,
        orchestrator_dir=args.orchestrator_dir,
        note=args.note,
    )


if __name__ == "__main__":
    raise SystemExit(main())
