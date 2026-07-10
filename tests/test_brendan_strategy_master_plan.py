from __future__ import annotations

import json
from pathlib import Path


BR_PLAN_PATH = Path("config/jarvis_brendan_master_plan.json")
MAIN_QUEUE_PATH = Path("config/jarvis_master_plan_queue.json")
SUMMARY_PATH = Path("docs/brendan_strategy/brendan_strategy_import.md")
ARCH_PATH = Path("docs/brendan_strategy/jarvis_brendan_architecture_review.md")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_brendan_strategy_docs_exist() -> None:
    assert SUMMARY_PATH.exists()
    assert ARCH_PATH.exists()

    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    architecture = ARCH_PATH.read_text(encoding="utf-8")

    assert "LLM proposes" in architecture
    assert "Deterministic engine scores" in architecture
    assert "Paper portfolio simulates" in architecture
    assert "LIVE TRADING: DISABLED" in summary
    assert "LIVE TRADING: DISABLED" in architecture


def test_brendan_master_plan_has_ordered_br_phases() -> None:
    plan = _load_json(BR_PLAN_PATH)
    phases = [item["phase"] for item in plan]

    assert phases == [
        "BR-01",
        "BR-02",
        "BR-03",
        "BR-04",
        "BR-05",
        "BR-06",
        "BR-07",
        "BR-08",
        "BR-09",
        "BR-10",
        "BR-10A",
        "BR-10B",
        "BR-10C",
        "BR-10D",
        "BR-10E",
        "BR-11",
        "BR-12",
        "BR-13",
        "BR-14",
    ]


def test_brendan_master_plan_is_safety_gated() -> None:
    plan = _load_json(BR_PLAN_PATH)
    combined = json.dumps(plan, sort_keys=True)

    assert "LIVE TRADING: DISABLED" in combined
    assert "broker routing" in combined
    assert "Include tests" in combined

    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in combined


def test_main_queue_contains_br_01_and_br_02() -> None:
    queue = _load_json(MAIN_QUEUE_PATH)
    phases = [item["phase"] for item in queue]

    assert "BR-01" in phases
    assert "BR-02" in phases

    br_01 = next(item for item in queue if item["phase"] == "BR-01")
    br_02 = next(item for item in queue if item["phase"] == "BR-02")

    assert br_01["branch"] == "agent/br-01-options-leaps-data-model"
    assert br_02["branch"] == "agent/br-02-candidate-universe-builder"
    assert "LIVE TRADING: DISABLED" in br_01["spec"]
    assert "LIVE TRADING: DISABLED" in br_02["spec"]
