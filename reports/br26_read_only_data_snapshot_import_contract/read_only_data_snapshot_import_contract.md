# BR-26 Read Only Data Snapshot Import Contract

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Approved Files
- engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json

## Schema
- required_top_level_fields: snapshot_version, snapshot_id, generated_at, freshness_as_of, source_kind, data_domain, provenance, symbols, records, safety, redaction, labels
- required_provenance_fields: provider_name, provider_dataset, source_file_name, acquisition_method, collector, collected_at, checksum_sha256, schema_name, quality_score
- required_record_fields: symbol, timestamp, open, high, low, close, volume

## Validation Rules
- approved_file: snapshot_file_not_approved
- file_exists: snapshot_file_missing
- json_object: snapshot_not_object
- required_fields: snapshot_missing_required_field
- record_schema: snapshot_schema_malformed
- freshness: snapshot_stale
- provenance: snapshot_low_provenance
- redaction: snapshot_contains_unredacted_sensitive_field
- runtime_safety: snapshot_contains_unsafe_runtime_state
- checksum: snapshot_checksum_mismatch

## Import Decisions
- engines\moonshot\deterministic\fixtures\br26_read_only_data_snapshot_valid.json: accepted=True label=HUMAN_REVIEW_REQUIRED reasons=accepted

## Rejection Reasons
- snapshot_file_not_approved
- snapshot_file_missing
- snapshot_json_malformed
- snapshot_not_object
- snapshot_missing_required_field
- snapshot_schema_malformed
- snapshot_stale
- snapshot_low_provenance
- snapshot_contains_unredacted_sensitive_field
- snapshot_contains_unsafe_runtime_state
- snapshot_checksum_mismatch

## Redaction Rules
- api_key
- oauth_token
- password
- private_key
- secret
- broker_credentials
- account_id
- account_number

## Metrics
- approved_file_count: 1
- validation_rule_count: 10
- redaction_rule_count: 8
- rejection_reason_count: 11
- import_decision_count: 1
- accepted_snapshot_count: 1
- rejected_snapshot_count: 0
- acceptance_criteria_count: 12
- acceptance_criteria_passed_count: 12

## Acceptance Criteria
- approved_files_declared: True
- schema_fields_declared: True
- validation_rules_cover_rejections: True
- redaction_rules_declared: True
- all_decisions_validated: True
- accepted_snapshots_remain_human_review_required: True
- rejected_snapshots_blocked_by_safety_gate: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_state_mutation: True
- account_imports_blocked: True
- live_trading_disabled: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- The contract is file-based, offline by default, deterministic, fixture-testable, and report-only.
- No .env reads, credentials, secrets, data-provider calls, broker connections, account imports, broker actions, order paths, state mutation, or live trading enablement.
- Imported snapshots remain research evidence only and require human review before any downstream use.