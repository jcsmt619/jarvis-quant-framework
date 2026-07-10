# BR-19 Historical Replay Evidence Pack

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-19 creates deterministic offline historical-style replay records from committed fixture and replay inputs.

The evidence pack summarizes replay windows, scenario provenance, candidate decisions, option-chain state, contract scoring, thesis context, deterministic risk gate outcomes, paper-only portfolio changes, monitor observations, dashboard references, unresolved review items, and required human-review actions.

## Safety Boundaries

BR-19 is offline replay-only and fixture-only.
BR-19 does not read `.env`.
BR-19 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-19 does not call data providers.
BR-19 does not fetch real market data.
BR-19 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-19 does not call broker endpoints.
BR-19 does not create trade instructions.
BR-19 does not create broker actions.
BR-19 does not create order paths.
BR-19 does not mutate live state.
BR-19 does not enable live trading.

## Runtime Invariants

BR-19 must always prove:

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

The default replay fixture is `engines/moonshot/deterministic/fixtures/br19_historical_replay_evidence_pack.json`.

The default output directory is `reports/br19_historical_replay_evidence_pack`.

BR-19 writes:

- `historical_replay_evidence_pack.json`
- `historical_replay_evidence_pack.md`

Run locally:

```powershell
python scripts/run_br19_historical_replay_evidence_pack.py
```
