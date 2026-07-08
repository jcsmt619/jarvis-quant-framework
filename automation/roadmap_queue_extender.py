from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


REQUIRED_KEYS = ("phase", "title", "branch", "commit_message", "spec")

SAFETY_SUFFIX = (
    "It must be read-only and records-only. "
    "It must not execute commands, run the next cycle, mutate artifacts, delete artifacts, "
    "create broker actions, create trade instructions, enable live trading, grant execution permissions, "
    "route broker orders, call broker endpoints, or submit any order path. "
    "Required labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, "
    "BLOCKED_BY_SAFETY_GATE, LIVE TRADING: DISABLED. "
    "It must not use secrets, credential files, broker routing, broker calls, live trading, or order execution. "
    "Include tests."
)


def phase_number(phase: str) -> int:
    digits = "".join(ch for ch in phase if ch.isdigit())
    if not digits:
        raise ValueError(f"Phase has no number: {phase}")
    return int(digits)


def phase_letter(phase: str) -> str:
    letters = "".join(ch for ch in phase if ch.isalpha())
    if not letters:
        raise ValueError(f"Phase has no letter: {phase}")
    return letters.upper()


def slugify(value: str) -> str:
    result: list[str] = []
    previous_dash = False
    for ch in value.lower():
        if ch.isalnum():
            result.append(ch)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True
    return "".join(result).strip("-")


def default_block_titles(block_number: int) -> tuple[str, str]:
    return (
        f"Next Cycle Records Review Gate {block_number}",
        f"Next Cycle Records Evidence Packet {block_number}",
    )


def build_phase_item(phase: str, title: str) -> dict[str, str]:
    branch = f"agent/{phase.lower()}-{slugify(title)}"
    commit_title = title[0].lower() + title[1:] if title else phase.lower()
    spec = (
        f"Build {phase} {title} from the Jarvis Quant master roadmap. "
        "It should generate deterministic JSON and Markdown records from the latest prior next-cycle "
        "operator packets, evidence packets, gates, report index, safe workflow catalog, queue status, "
        "and safety scanner status. It should summarize source artifact status, blocked prerequisites, "
        "unresolved review items, required refreshed artifacts, safety findings, inert command hints, "
        "queue next phase, operator checklist items, evidence references, and required human-review actions. "
        + SAFETY_SUFFIX
    )
    return {
        "phase": phase,
        "title": title,
        "branch": branch,
        "commit_message": f"feat: add {commit_title}",
        "spec": spec,
    }


def next_block_after(queue: list[dict[str, object]]) -> tuple[dict[str, str], dict[str, str]]:
    phases = [str(item.get("phase")) for item in queue if isinstance(item, dict) and item.get("phase")]
    numeric_phases = [phase for phase in phases if phase[:-1].isdigit() and phase[-1:].isalpha()]
    if not numeric_phases:
        raise ValueError("No numbered phases found in queue.")

    latest_number = max(phase_number(phase) for phase in numeric_phases)
    next_number = latest_number + 1

    title_a, title_b = default_block_titles(next_number)
    return (
        build_phase_item(f"{next_number}A", title_a),
        build_phase_item(f"{next_number}B", title_b),
    )


def validate_queue_item(item: dict[str, object]) -> None:
    for key in REQUIRED_KEYS:
        if key not in item or not isinstance(item[key], str) or not item[key].strip():
            raise ValueError(f"Queue item missing valid {key}: {item}")


def append_next_block(queue_path: Path) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    if not isinstance(queue, list):
        raise ValueError(f"Expected queue to be a list at {queue_path}")

    for item in queue:
        if isinstance(item, dict):
            validate_queue_item(item)

    additions = list(next_block_after(queue))
    existing = {item.get("phase") for item in queue if isinstance(item, dict)}

    added: list[dict[str, str]] = []
    for item in additions:
        if item["phase"] not in existing:
            queue.append(item)
            added.append(item)

    queue_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    return queue, added


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append the next two Jarvis roadmap phases.")
    parser.add_argument("--queue-path", default="config/jarvis_master_plan_queue.json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    queue, added = append_next_block(Path(args.queue_path))

    print(f"QUEUE_ITEM_COUNT {len(queue)}")
    if not added:
        print("NO_PHASES_ADDED")
    else:
        for item in added:
            print(f"ADDED {item['phase']} - {item['title']}")
        print(f"NEXT_START_PHASE {added[0]['phase']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
