# BR-25 Paper Candidate Lifecycle State Machine

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Lifecycle States
- blocked: label=BLOCKED_BY_SAFETY_GATE terminal=False
- review_required: label=HUMAN_REVIEW_REQUIRED terminal=False
- paper_only: label=PAPER_ONLY terminal=False
- stale: label=BLOCKED_BY_SAFETY_GATE terminal=False
- duplicate: label=MONITOR_ONLY terminal=False
- closed: label=HUMAN_REVIEW_REQUIRED terminal=True
- needs_more_evidence: label=HUMAN_REVIEW_REQUIRED terminal=False

## Allowed Transitions
- blocked -> review_required: label=HUMAN_REVIEW_REQUIRED evidence=4
- blocked -> closed: label=HUMAN_REVIEW_REQUIRED evidence=5
- blocked -> needs_more_evidence: label=HUMAN_REVIEW_REQUIRED evidence=5
- review_required -> blocked: label=BLOCKED_BY_SAFETY_GATE evidence=4
- review_required -> paper_only: label=PAPER_ONLY evidence=6
- review_required -> duplicate: label=MONITOR_ONLY evidence=5
- review_required -> closed: label=HUMAN_REVIEW_REQUIRED evidence=5
- review_required -> needs_more_evidence: label=HUMAN_REVIEW_REQUIRED evidence=5
- paper_only -> review_required: label=HUMAN_REVIEW_REQUIRED evidence=4
- paper_only -> stale: label=BLOCKED_BY_SAFETY_GATE evidence=5
- paper_only -> closed: label=HUMAN_REVIEW_REQUIRED evidence=5
- stale -> blocked: label=BLOCKED_BY_SAFETY_GATE evidence=4
- stale -> closed: label=HUMAN_REVIEW_REQUIRED evidence=5
- stale -> needs_more_evidence: label=HUMAN_REVIEW_REQUIRED evidence=5
- duplicate -> closed: label=HUMAN_REVIEW_REQUIRED evidence=6
- needs_more_evidence -> blocked: label=BLOCKED_BY_SAFETY_GATE evidence=4
- needs_more_evidence -> review_required: label=HUMAN_REVIEW_REQUIRED evidence=4
- needs_more_evidence -> stale: label=BLOCKED_BY_SAFETY_GATE evidence=5
- needs_more_evidence -> closed: label=HUMAN_REVIEW_REQUIRED evidence=5

## Forbidden Transitions
- blocked -> blocked: Self-transitions are forbidden; records require an audit event only when state changes.
- blocked -> paper_only: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- blocked -> stale: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- blocked -> duplicate: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- review_required -> review_required: Self-transitions are forbidden; records require an audit event only when state changes.
- review_required -> stale: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- paper_only -> blocked: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- paper_only -> paper_only: Self-transitions are forbidden; records require an audit event only when state changes.
- paper_only -> duplicate: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- paper_only -> needs_more_evidence: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- stale -> review_required: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- stale -> paper_only: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- stale -> stale: Self-transitions are forbidden; records require an audit event only when state changes.
- stale -> duplicate: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- duplicate -> blocked: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- duplicate -> review_required: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- duplicate -> paper_only: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- duplicate -> stale: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- duplicate -> duplicate: Self-transitions are forbidden; records require an audit event only when state changes.
- duplicate -> needs_more_evidence: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- closed -> blocked: Closed records are terminal and cannot transition.
- closed -> review_required: Closed records are terminal and cannot transition.
- closed -> paper_only: Closed records are terminal and cannot transition.
- closed -> stale: Closed records are terminal and cannot transition.
- closed -> duplicate: Closed records are terminal and cannot transition.
- closed -> closed: Closed records are terminal and cannot transition.
- closed -> needs_more_evidence: Closed records are terminal and cannot transition.
- needs_more_evidence -> paper_only: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- needs_more_evidence -> duplicate: Transition is outside the deterministic lifecycle table and remains blocked by safety gate.
- needs_more_evidence -> needs_more_evidence: Self-transitions are forbidden; records require an audit event only when state changes.

## Requirement Sections
- source_evidence_requirements
- review_resolution_requirements
- outcome_tracker_requirements
- promotion_gate_requirements
- audit_trail_requirements
- safety_boundary_requirements

## Metrics
- state_count: 7
- transition_count: 49
- allowed_transition_count: 19
- forbidden_transition_count: 30
- acceptance_criteria_count: 19
- acceptance_criteria_passed_count: 19

## Acceptance Criteria
- source_paths_include_br24: True
- all_lifecycle_states_present: True
- all_requirement_sections_present: True
- allowed_transitions_recorded: True
- forbidden_transitions_recorded: True
- closed_state_has_no_allowed_exit: True
- paper_only_requires_outcome_tracker: True
- paper_only_requires_promotion_gate: True
- all_allowed_transitions_require_audit: True
- all_transitions_keep_safety_boundary: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_state_mutation: True
- live_state_not_mutated: True
- paper_state_not_mutated: True
- broker_state_not_mutated: True
- routing_state_not_mutated: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- The state machine is deterministic, offline-only, read-only, and report-only.
- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, routing state mutation, paper state mutation, live state mutation, or live trading enablement.
- Promotion gates can only classify future review readiness; they cannot authorize live trading or broker activity.