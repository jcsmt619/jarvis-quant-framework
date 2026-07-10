# BR-21 Human Review Resolution Ledger

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-21 creates deterministic JSON and Markdown ledger records that let a human reviewer close unresolved research-review items from BR-17, BR-18, BR-19, and BR-20 without changing trading state.

Each ledger record includes source evidence, review item id, reviewer decision category, rationale, evidence references, unresolved blockers, required follow-up, acceptance criteria, and immutable safety boundaries.

Allowed resolution categories are:

- keep_blocked
- keep_review_required
- keep_paper_only
- needs_more_evidence
- stale_evidence
- duplicate_review_item

## Safety Boundaries

BR-21 is read-only over source evidence.
BR-21 is offline-only and deterministic.
BR-21 writes only resolution ledger report artifacts.
BR-21 does not read `.env`.
BR-21 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-21 does not call data providers.
BR-21 does not fetch real market data.
BR-21 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-21 does not call broker endpoints.
BR-21 does not create trade instructions.
BR-21 does not create broker actions.
BR-21 does not create order paths.
BR-21 does not mutate live state.
BR-21 does not enable live trading.

## Runtime Invariants

BR-21 must always prove:

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

The default source evidence paths are:

- `reports/br17_manual_report_review_packet/manual_report_review_packet.json`
- `reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json`
- `reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json`
- `reports/br20_paper_research_decision_journal/paper_research_decision_journal.json`

The default output directory is `reports/br21_human_review_resolution_ledger`.

BR-21 writes:

- `human_review_resolution_ledger.json`
- `human_review_resolution_ledger.md`

Run locally:

```powershell
python scripts/run_br21_human_review_resolution_ledger.py
```
