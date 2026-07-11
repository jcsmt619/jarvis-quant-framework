# BR-27 Approved Snapshot Intake Review Gate

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-27 reviews a BR-26 approved offline snapshot as immutable source evidence.

The gate reads the committed BR-26 import-contract report and the approved offline snapshot, then writes deterministic JSON and Markdown review records. The records cover file approval, checksum, schema, provenance, freshness, redaction, runtime safety, observation timestamps, rejection evidence, unresolved blockers, and required human-review actions.

An accepted snapshot remains research evidence only. It cannot advance to a downstream adapter, paper workflow, or trading workflow without a separate human-review decision.

## Safety Boundaries

BR-27 is offline, read-only, deterministic, report-only, and fixture-testable.
BR-27 reads only the committed BR-26 report and approved offline snapshot.
BR-27 writes only report artifacts.
BR-27 does not read `.env`.
BR-27 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-27 does not call data providers.
BR-27 does not fetch real market data at runtime.
BR-27 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-27 does not perform broker write operations.
BR-27 does not create trade instructions.
BR-27 does not create broker actions.
BR-27 does not create order paths.
BR-27 does not create external routing paths.
BR-27 does not mutate paper state.
BR-27 does not mutate live state.
BR-27 does not mutate broker state.
BR-27 does not mutate routing state.
BR-27 does not authorize live trading.
BR-27 does not enable live trading.

## Source Evidence

Default immutable inputs:

- `reports/br26_read_only_data_snapshot_import_contract/read_only_data_snapshot_import_contract.json`
- `engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json`

## Review Checks

- file_approval
- checksum
- schema
- provenance
- freshness
- redaction
- runtime_safety
- observation_timestamps

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

## Human Review Actions

Accepted research evidence still requires:

- confirmation that the snapshot remains research evidence only
- a separate human-review decision before any downstream adapter consumes it
- continued proof that broker actions, order paths, state mutation, and live trading remain disabled

Rejected evidence requires:

- review of deterministic rejection evidence
- correction of source evidence before a new review
- no downstream adapter advancement

## Runtime Invariants

BR-27 must always prove:

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
- advancement_authorized=false
- broker_write_operations_authorized=false
- external_routing_paths_authorized=false
- data_provider_calls_authorized=false
- LIVE TRADING: DISABLED

## Artifacts

The default output directory is `reports/br27_approved_snapshot_intake_review_gate`.

BR-27 writes:

- `approved_snapshot_intake_review_gate.json`
- `approved_snapshot_intake_review_gate.md`

Run locally:

```powershell
python scripts/run_br27_approved_snapshot_intake_review_gate.py
```
