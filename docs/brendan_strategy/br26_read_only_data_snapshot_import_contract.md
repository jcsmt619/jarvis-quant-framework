# BR-26 Read Only Data Snapshot Import Contract

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-26 defines the deterministic import contract for future read-only market data snapshots from approved local files.

The contract records schemas, validation rules, provenance requirements, freshness checks, redaction rules, fixture examples, rejection reasons, import decisions, and report artifacts. It is an offline file contract only; it does not fetch data.

## Safety Boundaries

BR-26 is file-based and offline by default.
BR-26 reads only approved snapshot files.
BR-26 writes only report artifacts.
BR-26 does not read `.env`.
BR-26 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-26 does not call data providers.
BR-26 does not fetch real market data at runtime.
BR-26 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-26 does not import accounts.
BR-26 does not call broker endpoints.
BR-26 does not create trade instructions.
BR-26 does not create broker actions.
BR-26 does not create order paths.
BR-26 does not mutate paper state.
BR-26 does not mutate live state.
BR-26 does not mutate broker state.
BR-26 does not mutate routing state.
BR-26 does not authorize live trading.
BR-26 does not enable live trading.

## Schema Contract

Required top-level fields:

- snapshot_version
- snapshot_id
- generated_at
- freshness_as_of
- source_kind
- data_domain
- provenance
- symbols
- records
- safety
- redaction
- labels

Required provenance fields:

- provider_name
- provider_dataset
- source_file_name
- acquisition_method
- collector
- collected_at
- checksum_sha256
- schema_name
- quality_score

Required record fields:

- symbol
- timestamp
- open
- high
- low
- close
- volume

## Validation Rules

- approved_file
- file_exists
- json_object
- required_fields
- record_schema
- freshness
- provenance
- redaction
- runtime_safety
- checksum

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

## Fixture Examples

- `engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json`
- `engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_stale.json`

## Runtime Invariants

BR-26 must always prove:

- credential_loading_attempted=false
- env_file_read_attempted=false
- secret_request_attempted=false
- data_provider_call_attempted=false
- external_network_call_attempted=false
- real_data_fetch_attempted=false
- broker_connection_attempted=false
- broker_read_call_performed=false
- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- broker_order_submitted=false
- broker_order_routing_enabled=false
- trade_instruction_created=false
- broker_action_created=false
- order_path_created=false
- live_state_mutation_attempted=false
- paper_state_mutation_attempted=false
- paper_state_mutation_allowed=false
- live_trading_enabled=false
- account_imports_allowed=false
- data_provider_calls_authorized=false
- broker_actions_authorized=false
- order_paths_authorized=false
- LIVE TRADING: DISABLED

## Artifacts

The default approved fixture path is:

- `engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json`

The default output directory is `reports/br26_read_only_data_snapshot_import_contract`.

BR-26 writes:

- `read_only_data_snapshot_import_contract.json`
- `read_only_data_snapshot_import_contract.md`

Run locally:

```powershell
python scripts/run_br26_read_only_data_snapshot_import_contract.py
```
