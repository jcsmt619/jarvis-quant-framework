# BR-30 Read Only Live Market Data Adapter

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Provider
- provider_name: tastytrade
- request_mode: recorded_response
- accepted_for_shadow_research: True
- feed_identity: tastytrade.market-data.read-only
- schema_version: br30.read_only_market_data_adapter.v1

## Evidence Checks
- offline_default_fail_closed: True
- provider_interface_declared: True
- runtime_config_external_required: True
- secret_material_absent: True
- raw_evidence_preserved: True
- normalized_snapshot_created: True
- br26_snapshot_schema_compatible: True
- feed_identity_approved: True
- provider_timestamp_valid: True
- exchange_timestamp_valid: True
- acquisition_timestamp_valid: True
- clock_skew_within_limit: True
- quality_flags_accepted: True
- duplicates_rejected: True
- missing_bars_rejected: True
- malformed_payload_rejected: True
- unsafe_capabilities_absent: True

## Rejection Reasons
- none

## Checksums
- raw_checksum_sha256: d49e24d2e0ee75a45133a7ec2d24915f2822d4583d31d12b42e192fc02bc20eb
- normalized_checksum_sha256: 1d592ee1e2c61489bb4c1957a9a4dc4d581a2539395eb7890a6ed1d12cadcfbf

## Boundary Evidence
- reconnect_boundary_events: 0
- max_retry_count: 0
- min_rate_limit_remaining: 39
- duplicate_events: 0
- delayed_feed_events: 0
- sandbox_reset_events: 0

## Metrics
- adapter_check_count: 17
- adapter_check_passed_count: 17
- rejection_reason_count: 0
- normalized_record_count: 2
- normalized_symbol_count: 2
- acceptance_criteria_count: 10
- acceptance_criteria_passed_count: 10

## Acceptance Criteria
- provider_interface_declared: True
- default_offline_fail_closed: True
- accepted_data_remains_human_review_required: True
- raw_and_normalized_checksums_present_when_accepted: True
- br26_snapshot_schema_compatible: True
- all_quality_boundaries_enforced: True
- no_credentials_or_secrets: True
- no_external_network_or_real_fetch: True
- no_account_execution_or_state_mutation: True
- live_trading_disabled: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Default runtime remains offline and fail closed.
- Real provider access requires a separate explicit read-only runtime configuration outside this repository.
- Authentication material must stay in local secret storage and must not appear in source files, reports, logs, fixtures, Git history, or UI surfaces.
- No account mutation capabilities, execution methods, external routing paths, state mutation, or live trading authorization are created.
