# BR-27 Approved Snapshot Intake Review Gate

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Source Evidence
- BR-26 import contract: reports\br26_read_only_data_snapshot_import_contract\read_only_data_snapshot_import_contract.json
- approved offline snapshot: engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json

## Review Records
- engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json: accepted_as_research_evidence=True label=HUMAN_REVIEW_REQUIRED reasons=accepted

## Checks
- snapshot: engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json
- file_approval: True
- checksum: True
- schema: True
- provenance: True
- freshness: True
- redaction: True
- runtime_safety: True
- observation_timestamps: True

## Observation Timestamps
- generated_at: 2026-07-10T20:00:00+00:00
- freshness_as_of: 2026-07-10T20:00:00+00:00
- collected_at: 2026-07-10T20:00:00+00:00
- record_timestamp: 2026-07-10T20:00:00+00:00
- record_timestamp: 2026-07-10T20:00:00+00:00

## Rejection Evidence
- br26_report_missing
- br26_report_malformed
- br26_report_phase_mismatch
- br26_report_safety_disabled_flags_missing
- snapshot_file_not_approved_by_br26
- snapshot_file_missing
- snapshot_json_malformed
- snapshot_not_object
- snapshot_missing_required_field
- snapshot_schema_malformed
- snapshot_provenance_missing_or_low_quality
- snapshot_stale
- snapshot_contains_unredacted_sensitive_field
- snapshot_contains_unsafe_runtime_state
- snapshot_checksum_mismatch
- snapshot_observation_timestamp_invalid
- snapshot_accepted_without_separate_review_decision

## Required Human Review Actions
- Confirm the approved snapshot may remain research evidence only.
- Record a separate human-review decision before any downstream adapter consumes the snapshot.
- Keep live trading disabled and do not create broker actions, order paths, or state mutations.

## Unresolved Blockers
- none for intake; separate review decision remains required

## Metrics
- source_path_count: 2
- review_record_count: 1
- accepted_research_evidence_count: 1
- rejected_snapshot_count: 0
- review_check_count: 8
- rejection_reason_count: 17
- required_human_review_action_count: 3
- acceptance_criteria_count: 12
- acceptance_criteria_passed_count: 12

## Acceptance Criteria
- source_paths_include_br26_and_snapshot: True
- all_review_records_validated: True
- all_checks_recorded: True
- accepted_snapshots_remain_research_evidence_only: True
- separate_review_decision_required: True
- rejected_snapshots_blocked_by_safety_gate: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_state_mutation: True
- advancement_not_authorized: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- The review gate is offline, read-only, deterministic, report-only, and fixture-testable.
- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, external routing paths, paper state mutation, trading state mutation, or live trading authorization.
- Accepted snapshots remain research evidence only and cannot advance without a separate human-review decision.