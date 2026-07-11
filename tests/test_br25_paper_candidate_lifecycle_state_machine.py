from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br25_paper_candidate_lifecycle_state_machine import (
    ALLOWED_TRANSITIONS,
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    LIFECYCLE_STATES,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_REQUIREMENT_SECTIONS,
    build_paper_candidate_lifecycle_state_machine,
    paper_candidate_lifecycle_state_machine_payload,
    render_markdown_paper_candidate_lifecycle_state_machine,
    run_paper_candidate_lifecycle_state_machine,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br25_paper_candidate_lifecycle_state_machine.py")
SCRIPT_PATH = Path("scripts/run_br25_paper_candidate_lifecycle_state_machine.py")
DOC_PATH = Path("docs/brendan_strategy/br25_paper_candidate_lifecycle_state_machine.md")


def test_br25_safety_manifest_is_report_only_offline_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["module"] == MODULE_NAME
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["read_only"] is True
    assert manifest["offline_only"] is True
    assert manifest["committed_report_inputs_only"] is True
    assert manifest["deterministic_state_machine_records_only"] is True
    assert manifest["live_state_mutation_allowed"] is False
    assert manifest["paper_state_mutation_allowed"] is False
    assert manifest["broker_state_mutation_allowed"] is False
    assert manifest["routing_state_mutation_allowed"] is False
    assert manifest["live_trading_authorized"] is False
    assert manifest["broker_actions_authorized"] is False
    assert manifest["order_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br25_builds_state_machine_from_committed_br24_evidence() -> None:
    state_machine = build_paper_candidate_lifecycle_state_machine()
    payload = paper_candidate_lifecycle_state_machine_payload(state_machine)

    assert all(path.exists() for path in DEFAULT_SOURCE_PATHS.values())
    assert payload["phase"] == "BR-25"
    assert payload["module"] == "Paper Candidate Lifecycle State Machine"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["source_paths"]) == {"BR-24"}
    assert payload["lifecycle_states"] == LIFECYCLE_STATES
    assert payload["requirement_sections"] == REQUIRED_REQUIREMENT_SECTIONS
    assert payload["metrics"]["state_count"] == 7
    assert payload["metrics"]["transition_count"] == 49
    assert payload["metrics"]["allowed_transition_count"] == sum(len(targets) for targets in ALLOWED_TRANSITIONS.values())
    assert payload["metrics"]["forbidden_transition_count"] > payload["metrics"]["allowed_transition_count"]
    assert payload["metrics"]["acceptance_criteria_passed_count"] == payload["metrics"]["acceptance_criteria_count"]
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["candidate_lifecycle_defined"] is True
    assert payload["readiness_state"]["manual_review_required"] is True
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert payload["readiness_state"]["paper_state_mutation_allowed"] is False
    assert payload["readiness_state"]["live_state_mutation_allowed"] is False
    assert payload["readiness_state"]["broker_state_mutation_allowed"] is False
    assert payload["readiness_state"]["routing_state_mutation_allowed"] is False


def test_br25_states_cover_required_requirements_and_labels() -> None:
    payload = paper_candidate_lifecycle_state_machine_payload(build_paper_candidate_lifecycle_state_machine())
    states = {state["state"]: state for state in payload["states"]}

    assert set(states) == set(LIFECYCLE_STATES)
    assert states["blocked"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert states["review_required"]["label"] == HUMAN_REVIEW_REQUIRED
    assert states["paper_only"]["label"] == PAPER_ONLY
    assert states["stale"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert states["duplicate"]["label"] == MONITOR_ONLY
    assert states["closed"]["label"] == HUMAN_REVIEW_REQUIRED
    assert states["closed"]["terminal"] is True
    assert states["needs_more_evidence"]["label"] == HUMAN_REVIEW_REQUIRED
    for state in states.values():
        assert set(state["requirements"]) == set(REQUIRED_REQUIREMENT_SECTIONS)
        assert "source_evidence_requirements" in state["requirements"]
        assert "review_resolution_requirements" in state["requirements"]
        assert "outcome_tracker_requirements" in state["requirements"]
        assert "promotion_gate_requirements" in state["requirements"]
        assert "audit_trail_requirements" in state["requirements"]
        assert "safety_boundary_requirements" in state["requirements"]


def test_br25_transition_matrix_records_allowed_and_forbidden_transitions() -> None:
    payload = paper_candidate_lifecycle_state_machine_payload(build_paper_candidate_lifecycle_state_machine())
    allowed_pairs = {(item["from_state"], item["to_state"]) for item in payload["allowed_transitions"]}
    forbidden_pairs = {(item["from_state"], item["to_state"]) for item in payload["forbidden_transitions"]}

    assert allowed_pairs == {
        (from_state, to_state) for from_state, targets in ALLOWED_TRANSITIONS.items() for to_state in targets
    }
    assert ("closed", "review_required") in forbidden_pairs
    assert ("paper_only", "paper_only") in forbidden_pairs
    assert ("blocked", "paper_only") in forbidden_pairs
    assert payload["transition_matrix"]["closed"]
    assert all(not item["allowed"] for item in payload["transition_matrix"]["closed"])
    paper_only_entries = [item for item in payload["allowed_transitions"] if item["to_state"] == "paper_only"]
    assert paper_only_entries
    assert all(item["outcome_tracker_required"] for item in paper_only_entries)
    assert all(item["promotion_gate_required"] for item in paper_only_entries)
    assert all(item["audit_trail_required"] for item in payload["allowed_transitions"])
    assert all(item["safety_boundary_required"] for item in payload["allowed_transitions"])


def test_br25_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br25_lifecycle_state_machine_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    state_machine = run_paper_candidate_lifecycle_state_machine(out_dir=out_dir)
    payload = paper_candidate_lifecycle_state_machine_payload(state_machine)

    assert payload["acceptance_criteria"]["allowed_transitions_recorded"] is True
    assert payload["acceptance_criteria"]["forbidden_transitions_recorded"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br25_markdown_script_and_doc_record_required_sections() -> None:
    state_machine = build_paper_candidate_lifecycle_state_machine()
    markdown = render_markdown_paper_candidate_lifecycle_state_machine(state_machine)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-25 Paper Candidate Lifecycle State Machine" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Lifecycle States" in markdown
    assert "## Allowed Transitions" in markdown
    assert "## Forbidden Transitions" in markdown
    assert "## Requirement Sections" in markdown
    for state in LIFECYCLE_STATES:
        assert state in markdown
        assert state in doc_text
    for section in REQUIRED_REQUIREMENT_SECTIONS:
        assert section in markdown
        assert section in doc_text
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "does not mutate live state" in doc_text
    assert "does not mutate broker state" in doc_text
    assert "does not mutate routing state" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br25_validation_rejects_unsafe_state_machine_mutations() -> None:
    state_machine = build_paper_candidate_lifecycle_state_machine()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(state_machine, safety={**state_machine.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(state_machine, safety={**state_machine.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(state_machine, safety={**state_machine.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(state_machine, safety={**state_machine.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(state_machine, safety={**state_machine.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot set paper_state_mutation_attempted"):
        replace(state_machine, safety={**state_machine.safety, "paper_state_mutation_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot allow live_state_mutation_allowed"):
        replace(state_machine, safety={**state_machine.safety, "live_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow broker_state_mutation_allowed"):
        replace(state_machine, safety={**state_machine.safety, "broker_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow routing_state_mutation_allowed"):
        replace(state_machine, safety={**state_machine.safety, "routing_state_mutation_allowed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(state_machine, safety={**state_machine.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(state_machine, label=MONITOR_ONLY).validate()


def test_br25_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
    assert "from broker" not in source
    assert "import broker" not in source
