# BR-28 Snapshot to Candidate Deterministic Adapter

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-28 consumes only a BR-27-reviewed approved offline snapshot and converts point-in-time snapshot records into normalized research-candidate records.

Each candidate preserves observation timestamps, decision timestamps, source checksum, provenance, strategy version, feature inputs, missing-data flags, stale-data flags, benchmark context, and human-review status.

The adapter prevents look-ahead by allowing each candidate to use only records available at or before its decision timestamp. It does not optimize parameters and does not select a strategy using evaluation-period outcomes.

## Safety Boundaries

BR-28 is offline, read-only for source evidence, deterministic, report-only, fixture-testable, research-only, paper-only, monitor-only, and human-review-required.
BR-28 reads only the BR-27 report and the BR-27-reviewed approved offline snapshot.
BR-28 writes only deterministic JSON and Markdown artifacts.
BR-28 does not read `.env`.
BR-28 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-28 does not call data providers.
BR-28 does not fetch real market data at runtime.
BR-28 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-28 does not perform broker write operations.
BR-28 does not create trade instructions.
BR-28 does not create broker actions.
BR-28 does not create order paths.
BR-28 does not create external routing paths.
BR-28 does not mutate paper state.
BR-28 does not mutate live state.
BR-28 does not mutate broker state.
BR-28 does not mutate routing state.
BR-28 does not authorize live trading.
BR-28 does not enable live trading.

## Source Evidence

Default immutable inputs:

- `reports/br27_approved_snapshot_intake_review_gate/approved_snapshot_intake_review_gate.json`
- `engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json`

## Normalized Candidate Fields

- candidate_id
- symbol
- label
- human_review_status
- observation_timestamp
- decision_timestamp
- source_checksum_sha256
- provenance
- strategy_version
- feature_inputs
- missing_data_flags
- stale_data_flags
- benchmark_context
- lookahead_guard

## Look-Ahead Guard

Every candidate records:

- uses_only_records_at_or_before_decision_timestamp=true
- future_records_used=false
- evaluation_period_outcomes_used=false
- parameter_optimization_performed=false
- strategy_selected_using_evaluation_outcomes=false

## Runtime Invariants

BR-28 must always prove:

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
- candidate_records_authorize_trade=false
- broker_write_operations_authorized=false
- external_routing_paths_authorized=false
- data_provider_calls_authorized=false
- evaluation_period_outcomes_used=false
- parameter_optimization_performed=false
- strategy_selected_using_evaluation_outcomes=false
- LIVE TRADING: DISABLED

## Artifacts

The default output directory is `reports/br28_snapshot_to_candidate_adapter`.

BR-28 writes:

- `snapshot_to_candidate_adapter.json`
- `snapshot_to_candidate_adapter.md`

Run locally:

```powershell
python scripts/run_br28_snapshot_to_candidate_adapter.py
```
