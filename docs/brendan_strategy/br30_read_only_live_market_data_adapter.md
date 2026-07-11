# BR-30 Read Only Live Market Data Adapter

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30 defines a provider-independent read-only market data interface and an initial tastytrade-compatible adapter shape.

The adapter can ingest authorized recorded responses or fixtures containing bars, quotes, option-chain metadata, snapshot metadata, feed identity, provider timestamps, exchange timestamps, acquisition timestamps, schema versions, quality flags, checksums, and provenance. It normalizes accepted evidence into the BR-26 snapshot contract for later shadow research review.

Default runtime behavior is offline and fail closed.

## Safety Boundaries

BR-30 does not read `.env`.
BR-30 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-30 does not call data providers during automated tests.
BR-30 does not fetch real market data by default.
BR-30 requires separate explicit read-only runtime configuration outside the repository for any future real provider access.
BR-30 requires authentication material to stay in local secret storage and never in source files, reports, logs, fixtures, Git history, or the user interface.
BR-30 does not provide account mutation capabilities.
BR-30 does not provide execution methods.
BR-30 does not submit orders.
BR-30 does not create broker actions.
BR-30 does not create order paths.
BR-30 does not mutate paper state.
BR-30 does not mutate live state.
BR-30 does not authorize live trading.

## Provider-Neutral Contract

The canonical interface is `ReadOnlyMarketDataProvider.acquire_snapshot(request)`.

Provider adapters must preserve:

- immutable raw evidence checksum
- immutable normalized evidence checksum
- provider name
- feed identity
- provider timestamp
- exchange timestamp
- acquisition timestamp
- schema version
- quality flags
- provenance score
- quote metadata
- option-chain metadata
- BR-26-compatible normalized records

Future Massive, Databento, ORATS, TradeStation, or IBKR adapters can implement the same contract without strategy changes.

## Rejection Boundaries

BR-30 rejects:

- stale data
- malformed payloads
- incomplete records
- unapproved feeds
- low-provenance data
- clock-skewed timestamps
- duplicate events
- unsafe capabilities
- reconnect-boundary-open events
- retry-boundary exceeded events
- rate-limit-boundary exceeded events
- timezone-invalid events
- missing bars
- delayed feeds
- sandbox resets
- feed mismatches

## Runtime Invariants

BR-30 must always prove:

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
- data_provider_calls_authorized=false
- broker_write_operations_authorized=false
- external_routing_paths_authorized=false
- LIVE TRADING: DISABLED

## Artifacts

The default recorded-response fixture is:

- `engines/moonshot/deterministic/fixtures/br30_tastytrade_recorded_response_valid.json`

The default output directory is `reports/br30_read_only_live_market_data_adapter`.

BR-30 writes:

- `read_only_live_market_data_adapter.json`
- `read_only_live_market_data_adapter.md`
- `br30_normalized_br26_snapshot.json` when evidence is accepted

Run offline fail-closed mode:

```powershell
python scripts/run_br30_read_only_live_market_data_adapter.py
```

Run recorded-response mode without network access:

```powershell
python scripts/run_br30_read_only_live_market_data_adapter.py --mode recorded_response
```
