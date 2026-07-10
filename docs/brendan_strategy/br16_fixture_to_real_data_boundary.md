# BR-16 Fixture to Real Data Boundary Design

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-16 defines the deterministic boundary for eventually replacing local fixture/sample market data with read-only market data inputs. It preserves offline tests, keeps fixture data as the default path, and requires no credentials by default.

## Scope

BR-16 defines:

- deterministic input interfaces for market snapshots and option-chain snapshots
- validation rules for symbols, timestamps, prices, required fields, provenance, and read-only status
- schemas for `MarketDataSnapshotV1` and `OptionChainSnapshotV1`
- staleness checks for daily bars, intraday quotes, and option chains
- provenance records for fixture and future read-only market data inputs
- cache boundaries for local artifacts only
- fallback behavior for stale, invalid, missing, or unavailable records
- redaction rules for sensitive field names
- fixture names used by offline tests

## Safety Boundaries

BR-16 is design-only for future read-only market data.
BR-16 keeps fixture/sample data as the default.
BR-16 preserves offline tests.
BR-16 does not read `.env`.
BR-16 does not request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-16 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-16 does not call broker endpoints.
BR-16 does not fetch real market data at runtime.
BR-16 does not import broker account state.
BR-16 does not create broker actions.
BR-16 does not create order paths.
BR-16 does not enable live trading.

## Runtime Invariants

BR-16 must always prove:

- credential_loading_attempted=false
- env_file_read_attempted=false
- secret_request_attempted=false
- external_network_call_attempted=false
- broker_connection_attempted=false
- broker_read_call_performed=false
- real_data_fetch_attempted=false
- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- broker_order_submitted=false
- broker_order_routing_enabled=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Artifacts

The default fixture is `engines/moonshot/deterministic/fixtures/br16_fixture_to_real_data_boundary.json`.

The default output directory is `reports/br16_fixture_to_real_data_boundary`.

BR-16 writes:

- `fixture_to_real_data_boundary.json`
- `fixture_to_real_data_boundary.md`

Run locally:

```powershell
python scripts/run_br16_fixture_to_real_data_boundary.py
```
