# BR-16 Fixture to Real Data Boundary Design

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Purpose
BR-16 defines the deterministic boundary for eventually replacing fixture/sample market data with read-only market data inputs while preserving offline tests and requiring no credentials by default.

## Metrics
- interface_count: 2
- validation_rule_count: 4
- schema_count: 2
- staleness_rule_count: 3
- provenance_record_count: 2
- cache_policy_count: 1
- fallback_behavior_count: 5
- redaction_rule_count: 7
- test_fixture_count: 3

## Interfaces
- MarketDataSnapshotInput: mode=fixture_default, schema=MarketDataSnapshotV1, label=MONITOR_ONLY
- OptionChainSnapshotInput: mode=read_only_real_data_design, schema=OptionChainSnapshotV1, label=MONITOR_ONLY

## Validation Rules
- BR16-RULE-SYMBOL-001: field=symbol, check=required uppercase ticker-like identifier with no account or credential content
- BR16-RULE-TIMESTAMP-001: field=as_of, check=required ISO-8601 timestamp; future timestamps are rejected
- BR16-RULE-PRICE-001: field=bid ask last close underlying_price, check=numeric non-negative prices; ask cannot be below bid when both are present
- BR16-RULE-PROVENANCE-001: field=provenance, check=source_type, source_name, captured_at, fixture_hash_or_cache_key, and read_only flag are required

## Schemas
- MarketDataSnapshotV1@1.0: required=symbol, as_of, open, high, low, close, volume, provenance
- OptionChainSnapshotV1@1.0: required=underlying_symbol, underlying_price, as_of, contracts, provenance

## Staleness Checks
- daily_bar: max_age_seconds=172800, fallback=use_fixture_snapshot
- intraday_quote: max_age_seconds=1800, fallback=block_record
- option_chain: max_age_seconds=1800, fallback=skip_symbol

## Provenance Records
- br03_options_chain_quality_fixture: source_type=fixture, read_only=True, credential_required=False
- future_read_only_market_data_adapter: source_type=real_data_design, read_only=True, credential_required=False

## Cache Boundaries
- market_data_boundary_cache: write_scope=local_artifact_only, read_scope=offline_tests_and_read_only_inputs, fallback=preserve_last_valid_fixture

## Fallback Behavior
- fixture_snapshot_is_default_when_no_read_only_input_is_supplied
- stale_or_invalid_real_data_records_are_blocked_or_skipped_before_scoring
- last_valid_fixture_snapshot_remains_available_for_offline_tests
- missing_optional_fields_are_recorded_as_quality_flags
- missing_required_fields_block_the_record

## Redaction Rules
- api_key
- secret
- token
- password
- oauth
- private_key
- account_id

## Test Fixtures
- br16_fixture_to_real_data_boundary.json
- br03_options_chain_quality.json
- br02_candidate_universe.json

## Acceptance Criteria
- fixture_data_remains_default: True
- offline_tests_preserved: True
- read_only_real_data_design_only: True
- no_credentials_or_env_files: True
- no_network_or_real_fetch: True
- no_broker_or_order_paths: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Fixture/sample data remains the default input for tests.
- Read-only real-data support is design-only in BR-16.
- No credentials, env file reads, secrets, broker connections, broker calls, order paths, network fetches, or live trading enablement.