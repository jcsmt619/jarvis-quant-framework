from __future__ import annotations

import json
from pathlib import Path

from automation.roadmap_queue_extender import (
    append_next_block,
    build_phase_item,
    next_block_after,
    phase_letter,
    phase_number,
    slugify,
)


def test_phase_number_and_letter_parse_phase_name() -> None:
    assert phase_number("30B") == 30
    assert phase_letter("30B") == "B"


def test_slugify_builds_branch_safe_text() -> None:
    assert slugify("Next Cycle Records Review Gate 31") == "next-cycle-records-review-gate-31"


def test_build_phase_item_has_required_safety_boundary() -> None:
    item = build_phase_item("31A", "Next Cycle Records Review Gate 31")

    assert item["phase"] == "31A"
    assert item["branch"] == "agent/31a-next-cycle-records-review-gate-31"
    assert "LIVE TRADING: DISABLED" in item["spec"]
    assert "It must not use secrets" in item["spec"]
    assert "It must not execute commands" in item["spec"]


def test_next_block_after_30b_returns_31a_31b() -> None:
    phase_a, phase_b = next_block_after(
        [
            {
                "phase": "30A",
                "title": "Existing A",
                "branch": "agent/30a-existing-a",
                "commit_message": "feat: existing a",
                "spec": "Existing spec.",
            },
            {
                "phase": "30B",
                "title": "Existing B",
                "branch": "agent/30b-existing-b",
                "commit_message": "feat: existing b",
                "spec": "Existing spec.",
            },
        ]
    )

    assert phase_a["phase"] == "31A"
    assert phase_b["phase"] == "31B"


def test_append_next_block_writes_two_new_items(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            [
                {
                    "phase": "30A",
                    "title": "Existing A",
                    "branch": "agent/30a-existing-a",
                    "commit_message": "feat: existing a",
                    "spec": "Existing spec.",
                },
                {
                    "phase": "30B",
                    "title": "Existing B",
                    "branch": "agent/30b-existing-b",
                    "commit_message": "feat: existing b",
                    "spec": "Existing spec.",
                },
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    queue, added = append_next_block(queue_path)

    assert [item["phase"] for item in added] == ["31A", "31B"]
    assert [item["phase"] for item in queue[-2:]] == ["31A", "31B"]
