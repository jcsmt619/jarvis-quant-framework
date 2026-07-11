from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-25"
MODULE_NAME = "Paper Candidate Lifecycle State Machine"
DEFAULT_REPORT_DIR = Path("reports/br25_paper_candidate_lifecycle_state_machine")
JSON_REPORT_NAME = "paper_candidate_lifecycle_state_machine.json"
MARKDOWN_REPORT_NAME = "paper_candidate_lifecycle_state_machine.md"
DEFAULT_SOURCE_PATHS = {
    "BR-24": Path("reports/br24_consolidated_research_dossier/consolidated_research_dossier.json"),
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
LIFECYCLE_STATES = (
    "blocked",
    "review_required",
    "paper_only",
    "stale",
    "duplicate",
    "closed",
    "needs_more_evidence",
)
REQUIRED_REQUIREMENT_SECTIONS = (
    "source_evidence_requirements",
    "review_resolution_requirements",
    "outcome_tracker_requirements",
    "promotion_gate_requirements",
    "audit_trail_requirements",
    "safety_boundary_requirements",
)
ALLOWED_TRANSITIONS = {
    "blocked": ("needs_more_evidence", "review_required", "closed"),
    "review_required": ("needs_more_evidence", "paper_only", "blocked", "duplicate", "closed"),
    "paper_only": ("review_required", "stale", "closed"),
    "stale": ("needs_more_evidence", "blocked", "closed"),
    "duplicate": ("closed",),
    "closed": (),
    "needs_more_evidence": ("review_required", "blocked", "stale", "closed"),
}
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "env_file_read_attempted",
    "secret_request_attempted",
    "data_provider_call_attempted",
    "external_network_call_attempted",
    "real_data_fetch_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "trade_instruction_created",
    "broker_action_created",
    "order_path_created",
    "live_state_mutation_attempted",
    "paper_state_mutation_attempted",
    "paper_state_mutation_allowed",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class LifecycleStateDefinition:
    state: str
    label: str
    terminal: bool
    description: str
    requirements: dict[str, tuple[str, ...]]

    def validate(self) -> None:
        _require_known_state(self.state)
        if self.label not in REQUIRED_LABELS:
            raise ValueError("BR-25 lifecycle state label must be a required safety label")
        if set(self.requirements) != set(REQUIRED_REQUIREMENT_SECTIONS):
            raise ValueError("BR-25 lifecycle state must include every requirement section")
        for section, items in self.requirements.items():
            if section in REQUIRED_REQUIREMENT_SECTIONS and not items:
                raise ValueError(f"BR-25 lifecycle state requirement section is empty: {section}")


@dataclass(frozen=True)
class LifecycleTransitionRule:
    from_state: str
    to_state: str
    allowed: bool
    label: str
    required_evidence: tuple[str, ...]
    review_resolution_required: bool
    outcome_tracker_required: bool
    promotion_gate_required: bool
    audit_trail_required: bool
    safety_boundary_required: bool
    rationale: str

    def validate(self) -> None:
        _require_known_state(self.from_state)
        _require_known_state(self.to_state)
        if self.allowed != (self.to_state in ALLOWED_TRANSITIONS[self.from_state]):
            raise ValueError("BR-25 transition allowed flag must match deterministic transition table")
        if self.label not in REQUIRED_LABELS:
            raise ValueError("BR-25 transition label must be a required safety label")
        if self.allowed and not self.required_evidence:
            raise ValueError("BR-25 allowed transitions require source evidence")
        if self.allowed and not self.audit_trail_required:
            raise ValueError("BR-25 allowed transitions require audit trail evidence")
        if self.allowed and not self.safety_boundary_required:
            raise ValueError("BR-25 allowed transitions require safety boundary evidence")


@dataclass(frozen=True)
class PaperCandidateLifecycleStateMachine:
    as_of: datetime
    source_paths: dict[str, str]
    states: tuple[LifecycleStateDefinition, ...]
    transitions: tuple[LifecycleTransitionRule, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-25 lifecycle state machine must require human review")
        if set(self.source_paths) != set(DEFAULT_SOURCE_PATHS):
            raise ValueError("BR-25 source paths must include BR-24")
        if {state.state for state in self.states} != set(LIFECYCLE_STATES):
            raise ValueError("BR-25 lifecycle state definitions must cover every state")
        for state in self.states:
            state.validate()
        expected_transition_count = len(LIFECYCLE_STATES) * len(LIFECYCLE_STATES)
        if len(self.transitions) != expected_transition_count:
            raise ValueError("BR-25 transition matrix must include every from/to state pair")
        for transition in self.transitions:
            transition.validate()
        _validate_disabled_safety(self.safety)


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "read_only": True,
        "offline_only": True,
        "committed_report_inputs_only": True,
        "deterministic_state_machine_records_only": True,
        "source_evidence_read_only": True,
        "live_state_mutation_allowed": False,
        "paper_state_mutation_allowed": False,
        "broker_state_mutation_allowed": False,
        "routing_state_mutation_allowed": False,
        "live_trading_authorized": False,
        "broker_actions_authorized": False,
        "order_paths_authorized": False,
        "data_provider_calls_authorized": False,
        "credential_loading_attempted": False,
        "env_file_read_attempted": False,
        "secret_request_attempted": False,
        "data_provider_call_attempted": False,
        "external_network_call_attempted": False,
        "real_data_fetch_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "trade_instruction_created": False,
        "broker_action_created": False,
        "order_path_created": False,
        "live_state_mutation_attempted": False,
        "paper_state_mutation_attempted": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_paper_candidate_lifecycle_state_machine(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> PaperCandidateLifecycleStateMachine:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    source_payloads = {phase: _load_json(path) for phase, path in resolved_paths.items()}
    _validate_source_payloads(source_payloads)
    state_machine = PaperCandidateLifecycleStateMachine(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_paths={phase: str(path) for phase, path in resolved_paths.items()},
        states=_build_state_definitions(),
        transitions=_build_transition_rules(),
        safety=safety_manifest(),
    )
    state_machine.validate()
    return state_machine


def paper_candidate_lifecycle_state_machine_payload(
    state_machine: PaperCandidateLifecycleStateMachine,
) -> dict[str, Any]:
    state_machine.validate()
    states = tuple(_state_payload(state) for state in state_machine.states)
    transitions = tuple(_transition_payload(transition) for transition in state_machine.transitions)
    allowed = tuple(transition for transition in transitions if transition["allowed"])
    forbidden = tuple(transition for transition in transitions if not transition["allowed"])
    acceptance = _state_machine_acceptance_criteria(state_machine)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": state_machine.as_of.isoformat(),
        "label": state_machine.label,
        "source_paths": state_machine.source_paths,
        "lifecycle_states": LIFECYCLE_STATES,
        "requirement_sections": REQUIRED_REQUIREMENT_SECTIONS,
        "safety": state_machine.safety,
        "metrics": {
            "state_count": len(states),
            "transition_count": len(transitions),
            "allowed_transition_count": len(allowed),
            "forbidden_transition_count": len(forbidden),
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "states": states,
        "allowed_transitions": allowed,
        "forbidden_transitions": forbidden,
        "transition_matrix": {
            state: tuple(
                transition
                for transition in transitions
                if transition["from_state"] == state
            )
            for state in LIFECYCLE_STATES
        },
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "PAPER_CANDIDATE_LIFECYCLE_STATE_MACHINE_ONLY",
            "candidate_lifecycle_defined": True,
            "manual_review_required": True,
            "ready_for_live_trading": False,
            "live_state_mutation_allowed": False,
            "paper_state_mutation_allowed": False,
            "broker_state_mutation_allowed": False,
            "routing_state_mutation_allowed": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "data_provider_calls_allowed": False,
        },
    }


def render_markdown_paper_candidate_lifecycle_state_machine(
    state_machine: PaperCandidateLifecycleStateMachine,
) -> str:
    payload = paper_candidate_lifecycle_state_machine_payload(state_machine)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Lifecycle States",
    ]
    for state in payload["states"]:
        lines.append(f"- {state['state']}: label={state['label']} terminal={state['terminal']}")

    lines.extend(["", "## Allowed Transitions"])
    for transition in payload["allowed_transitions"]:
        lines.append(
            f"- {transition['from_state']} -> {transition['to_state']}: "
            f"label={transition['label']} evidence={len(transition['required_evidence'])}"
        )

    lines.extend(["", "## Forbidden Transitions"])
    for transition in payload["forbidden_transitions"]:
        lines.append(f"- {transition['from_state']} -> {transition['to_state']}: {transition['rationale']}")

    lines.extend(["", "## Requirement Sections"])
    for section in REQUIRED_REQUIREMENT_SECTIONS:
        lines.append(f"- {section}")

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- The state machine is deterministic, offline-only, read-only, and report-only.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, routing state mutation, paper state mutation, live state mutation, or live trading enablement.",
            "- Promotion gates can only classify future review readiness; they cannot authorize live trading or broker activity.",
        ]
    )
    return "\n".join(lines)


def write_paper_candidate_lifecycle_state_machine(
    state_machine: PaperCandidateLifecycleStateMachine,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    state_machine.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(paper_candidate_lifecycle_state_machine_payload(state_machine), indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_paper_candidate_lifecycle_state_machine(state_machine), encoding="utf-8")
    return json_path, markdown_path


def run_paper_candidate_lifecycle_state_machine(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> PaperCandidateLifecycleStateMachine:
    state_machine = build_paper_candidate_lifecycle_state_machine(source_paths=source_paths, as_of=as_of)
    write_paper_candidate_lifecycle_state_machine(state_machine, out_dir=out_dir)
    return state_machine


def _build_state_definitions() -> tuple[LifecycleStateDefinition, ...]:
    return tuple(
        LifecycleStateDefinition(
            state=state,
            label=_label_for_state(state),
            terminal=state == "closed",
            description=_state_description(state),
            requirements=_requirements_for_state(state),
        )
        for state in LIFECYCLE_STATES
    )


def _build_transition_rules() -> tuple[LifecycleTransitionRule, ...]:
    rules: list[LifecycleTransitionRule] = []
    for from_state in LIFECYCLE_STATES:
        for to_state in LIFECYCLE_STATES:
            allowed = to_state in ALLOWED_TRANSITIONS[from_state]
            rules.append(
                LifecycleTransitionRule(
                    from_state=from_state,
                    to_state=to_state,
                    allowed=allowed,
                    label=_label_for_transition(to_state, allowed),
                    required_evidence=_required_evidence_for_transition(from_state, to_state) if allowed else (),
                    review_resolution_required=allowed and to_state in {"review_required", "paper_only", "closed"},
                    outcome_tracker_required=allowed and to_state in {"paper_only", "stale", "closed"},
                    promotion_gate_required=allowed and to_state == "paper_only",
                    audit_trail_required=allowed,
                    safety_boundary_required=True,
                    rationale=_transition_rationale(from_state, to_state, allowed),
                )
            )
    return tuple(rules)


def _requirements_for_state(state: str) -> dict[str, tuple[str, ...]]:
    base_source = (
        "BR-24 dossier reference",
        "candidate id",
        "source phase id",
        "source artifact path",
        "evidence timestamp",
    )
    common_safety = (
        "RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, and BLOCKED_BY_SAFETY_GATE labels remain available",
        "LIVE TRADING remains DISABLED",
        "no credential, data-provider, broker, order path, paper state, live state, or routing mutation is allowed",
    )
    state_specific = {
        "blocked": (
            "blocking reason",
            "blocking gate name",
            "reviewer-visible remediation note",
        ),
        "review_required": (
            "review question",
            "review owner or queue",
            "trade-relevant HUMAN_REVIEW_REQUIRED label",
        ),
        "paper_only": (
            "paper-only outcome reference",
            "paper-only monitor note",
            "promotion gate checklist reference",
        ),
        "stale": (
            "staleness reason",
            "stale source timestamp",
            "fresh evidence requirement",
        ),
        "duplicate": (
            "primary candidate id",
            "duplicate detection reason",
            "no second workflow action note",
        ),
        "closed": (
            "closure reason",
            "final reviewer note",
            "terminal audit event",
        ),
        "needs_more_evidence": (
            "missing evidence category",
            "approved offline evidence collection path",
            "review owner or queue",
        ),
    }
    review_requirements = {
        "blocked": ("reviewer must keep item blocked or request evidence",),
        "review_required": ("reviewer must resolve the open question before any state change",),
        "paper_only": ("reviewer must confirm paper-only status remains non-routed",),
        "stale": ("reviewer must reject stale evidence for promotion",),
        "duplicate": ("reviewer must link the primary candidate record",),
        "closed": ("reviewer must provide final closeout rationale",),
        "needs_more_evidence": ("reviewer must identify the missing evidence category",),
    }
    return {
        "source_evidence_requirements": base_source + state_specific[state],
        "review_resolution_requirements": review_requirements[state],
        "outcome_tracker_requirements": (
            "paper outcome tracker id when paper-only or closed after paper monitoring",
            "monitor observation summary",
            "no order or broker action reference",
        ),
        "promotion_gate_requirements": (
            "promotion gate evidence checklist id when evaluating paper-only readiness",
            "stale data, liquidity, safety, and human-review checks remain explicit",
            "promotion gate cannot authorize live trading",
        ),
        "audit_trail_requirements": (
            "previous state",
            "next state",
            "transition reason",
            "operator or system reviewer id",
            "timestamp",
        ),
        "safety_boundary_requirements": common_safety,
    }


def _required_evidence_for_transition(from_state: str, to_state: str) -> tuple[str, ...]:
    evidence = [
        "source_evidence_reference",
        "review_resolution_reference",
        "audit_trail_event",
        "safety_boundary_snapshot",
    ]
    if to_state in {"paper_only", "stale", "closed"}:
        evidence.append("outcome_tracker_reference")
    if to_state == "paper_only":
        evidence.append("promotion_gate_checklist_reference")
    if from_state == "duplicate" or to_state == "duplicate":
        evidence.append("primary_candidate_reference")
    if to_state == "needs_more_evidence":
        evidence.append("missing_evidence_category")
    return tuple(evidence)


def _state_machine_acceptance_criteria(state_machine: PaperCandidateLifecycleStateMachine) -> dict[str, bool]:
    allowed_pairs = {(rule.from_state, rule.to_state) for rule in state_machine.transitions if rule.allowed}
    forbidden_pairs = {(rule.from_state, rule.to_state) for rule in state_machine.transitions if not rule.allowed}
    return {
        "source_paths_include_br24": set(state_machine.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_lifecycle_states_present": {state.state for state in state_machine.states} == set(LIFECYCLE_STATES),
        "all_requirement_sections_present": all(
            set(state.requirements) == set(REQUIRED_REQUIREMENT_SECTIONS) for state in state_machine.states
        ),
        "allowed_transitions_recorded": allowed_pairs
        == {(from_state, to_state) for from_state, targets in ALLOWED_TRANSITIONS.items() for to_state in targets},
        "forbidden_transitions_recorded": bool(forbidden_pairs),
        "closed_state_has_no_allowed_exit": not ALLOWED_TRANSITIONS["closed"],
        "paper_only_requires_outcome_tracker": all(
            rule.outcome_tracker_required for rule in state_machine.transitions if rule.allowed and rule.to_state == "paper_only"
        ),
        "paper_only_requires_promotion_gate": all(
            rule.promotion_gate_required for rule in state_machine.transitions if rule.allowed and rule.to_state == "paper_only"
        ),
        "all_allowed_transitions_require_audit": all(
            rule.audit_trail_required for rule in state_machine.transitions if rule.allowed
        ),
        "all_transitions_keep_safety_boundary": all(rule.safety_boundary_required for rule in state_machine.transitions),
        "no_credentials_or_secrets": all(
            state_machine.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            state_machine.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_state_mutation": all(
            state_machine.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "live_state_not_mutated": state_machine.safety["live_state_mutation_allowed"] is False,
        "paper_state_not_mutated": state_machine.safety["paper_state_mutation_allowed"] is False,
        "broker_state_not_mutated": state_machine.safety["broker_state_mutation_allowed"] is False,
        "routing_state_not_mutated": state_machine.safety["routing_state_mutation_allowed"] is False,
        "live_trading_disabled": state_machine.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": state_machine.label == HUMAN_REVIEW_REQUIRED,
    }


def _state_payload(state: LifecycleStateDefinition) -> dict[str, Any]:
    return {
        "state": state.state,
        "label": state.label,
        "terminal": state.terminal,
        "description": state.description,
        "requirements": state.requirements,
    }


def _transition_payload(transition: LifecycleTransitionRule) -> dict[str, Any]:
    return {
        "from_state": transition.from_state,
        "to_state": transition.to_state,
        "allowed": transition.allowed,
        "label": transition.label,
        "required_evidence": transition.required_evidence,
        "review_resolution_required": transition.review_resolution_required,
        "outcome_tracker_required": transition.outcome_tracker_required,
        "promotion_gate_required": transition.promotion_gate_required,
        "audit_trail_required": transition.audit_trail_required,
        "safety_boundary_required": transition.safety_boundary_required,
        "rationale": transition.rationale,
    }


def _label_for_state(state: str) -> str:
    labels = {
        "blocked": BLOCKED_BY_SAFETY_GATE,
        "review_required": HUMAN_REVIEW_REQUIRED,
        "paper_only": PAPER_ONLY,
        "stale": BLOCKED_BY_SAFETY_GATE,
        "duplicate": MONITOR_ONLY,
        "closed": HUMAN_REVIEW_REQUIRED,
        "needs_more_evidence": HUMAN_REVIEW_REQUIRED,
    }
    return labels[state]


def _label_for_transition(to_state: str, allowed: bool) -> str:
    if not allowed:
        return BLOCKED_BY_SAFETY_GATE
    return _label_for_state(to_state)


def _state_description(state: str) -> str:
    descriptions = {
        "blocked": "Candidate cannot advance because a deterministic gate, stale evidence, liquidity issue, or safety boundary blocks it.",
        "review_required": "Candidate is trade-relevant research that needs a human reviewer before any later paper-only lifecycle change.",
        "paper_only": "Candidate is eligible only for paper-only monitoring records and cannot route externally.",
        "stale": "Candidate evidence is too old or incomplete for review or paper-only continuation.",
        "duplicate": "Candidate duplicates a primary record and must not create a second workflow action.",
        "closed": "Candidate lifecycle is terminal until a separate future phase creates a new candidate record.",
        "needs_more_evidence": "Candidate lacks approved offline evidence needed to resolve review or blocked status.",
    }
    return descriptions[state]


def _transition_rationale(from_state: str, to_state: str, allowed: bool) -> str:
    if allowed:
        return "Transition is allowed only with source evidence, review resolution, audit trail, and disabled safety boundary proof."
    if from_state == "closed":
        return "Closed records are terminal and cannot transition."
    if from_state == to_state:
        return "Self-transitions are forbidden; records require an audit event only when state changes."
    return "Transition is outside the deterministic lifecycle table and remains blocked by safety gate."


def _validate_source_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    if set(payloads) != set(DEFAULT_SOURCE_PATHS):
        raise ValueError("BR-25 source payloads must include BR-24")
    payload = payloads["BR-24"]
    if payload.get("phase") != "BR-24":
        raise ValueError("BR-25 source payload phase mismatch for BR-24")
    safety = payload.get("safety", {})
    if safety.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-25 source payload BR-24 must keep LIVE TRADING disabled")
    for field_name in REQUIRED_DISABLED_FLAGS:
        if field_name in safety and safety[field_name] is not False:
            raise ValueError(f"BR-25 source payload BR-24 cannot set {field_name}")


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-25 state machine cannot set {field_name}")
    for field_name in (
        "live_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
        "live_trading_authorized",
        "broker_actions_authorized",
        "order_paths_authorized",
        "data_provider_calls_authorized",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-25 state machine cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-25 state machine must keep LIVE TRADING disabled")


def _require_known_state(state: str) -> None:
    if state not in LIFECYCLE_STATES:
        raise ValueError("BR-25 lifecycle state is not recognized")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload
