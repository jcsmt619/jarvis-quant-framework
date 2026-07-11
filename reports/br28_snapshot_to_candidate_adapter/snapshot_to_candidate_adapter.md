# BR-28 Snapshot to Candidate Deterministic Adapter

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Source Evidence
- BR-27 approved snapshot intake review gate: reports\br27_approved_snapshot_intake_review_gate\approved_snapshot_intake_review_gate.json
- BR-27-reviewed approved offline snapshot: engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json

## Adapter Checks
- br27_report_accepted: True
- snapshot_path_matches_br27: True
- snapshot_checksum_matches_br27: True
- offline_snapshot_loaded: True
- records_are_point_in_time: True
- decision_timestamps_not_before_observations: True
- candidate_fields_normalized: True
- no_evaluation_outcomes_used: True
- no_parameter_optimization: True

## Research Candidates
- br28-7eb903a69e21c8ab: symbol=QQQ observation=2026-07-10T20:00:00+00:00 decision=2026-07-10T20:00:00+00:00 label=HUMAN_REVIEW_REQUIRED human_review_status=HUMAN_REVIEW_REQUIRED
- br28-f90aa6a950622bf1: symbol=SPY observation=2026-07-10T20:00:00+00:00 decision=2026-07-10T20:00:00+00:00 label=HUMAN_REVIEW_REQUIRED human_review_status=HUMAN_REVIEW_REQUIRED

## Preserved Fields
- observation_timestamp
- decision_timestamp
- source_checksum_sha256
- provenance
- strategy_version
- feature_inputs
- missing_data_flags
- stale_data_flags
- benchmark_context
- human_review_status

## Blocked Records
- none

## Metrics
- candidate_count: 2
- blocked_record_count: 0
- adapter_check_count: 9
- adapter_check_passed_count: 9
- acceptance_criteria_count: 12
- acceptance_criteria_passed_count: 12

## Acceptance Criteria
- source_paths_include_br27_and_snapshot: True
- br27_report_accepted: True
- snapshot_path_matches_br27: True
- snapshot_checksum_matches_br27: True
- candidate_records_created: True
- candidate_records_remain_human_review_required: True
- lookahead_prevention_enforced: True
- no_evaluation_outcomes_or_parameter_optimization: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_state_mutation: True
- live_trading_disabled: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- The adapter is offline, read-only for source evidence, deterministic, report-only, fixture-testable, research-only, and human-review-required.
- It consumes only a BR-27-reviewed approved offline snapshot.
- It prevents look-ahead by using only records available at or before each decision timestamp.
- It does not optimize parameters or select a strategy using evaluation-period outcomes.
- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, external routing paths, state mutation, or live trading authorization.