# BR-18 Fixture Scenario Expansion Matrix

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-18 expands deterministic offline fixture coverage for bullish, bearish, neutral, stale-data, poor-liquidity, no-candidate, thesis-missing, chain-quality-failed, risk-rejected, and paper-hold scenarios.

The matrix proves expected behavior across candidate selection, chain quality, contract scoring, thesis packaging, deterministic risk gate decisions, paper-only portfolio simulation, monitor alerts, and dashboard summaries.

## Safety Boundaries

BR-18 is fixture-only and offline-only.
BR-18 does not read `.env`.
BR-18 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-18 does not call data providers.
BR-18 does not fetch real market data.
BR-18 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-18 does not call broker endpoints.
BR-18 does not create trade instructions.
BR-18 does not create broker actions.
BR-18 does not create order paths.
BR-18 does not mutate live state.
BR-18 does not enable live trading.

## Runtime Invariants

BR-18 must always prove:

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
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Artifacts

The default fixture is `engines/moonshot/deterministic/fixtures/br18_fixture_scenario_expansion_matrix.json`.

The default output directory is `reports/br18_fixture_scenario_expansion_matrix`.

BR-18 writes:

- `fixture_scenario_expansion_matrix.json`
- `fixture_scenario_expansion_matrix.md`

Run locally:

```powershell
python scripts/run_br18_fixture_scenario_expansion_matrix.py
```
