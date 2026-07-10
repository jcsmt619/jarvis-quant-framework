# BR-23 Promotion Gate Evidence Checklist

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-23 creates deterministic JSON and Markdown checklist records that define the evidence required before a paper research idea can advance to any later review stage.

Each checklist record covers source freshness, provenance, scenario coverage, replay coverage, decision journal completeness, human review resolution, paper outcome tracking, risk policy compliance, stale-data rejection, liquidity rejection, and safety boundaries. Records classify evidence as blocked, review-required, or paper-only.

## Safety Boundaries

BR-23 is read-only over committed source evidence.
BR-23 is offline-only and deterministic.
BR-23 writes only promotion gate evidence checklist report artifacts.
BR-23 does not read `.env`.
BR-23 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-23 does not call data providers.
BR-23 does not fetch real market data.
BR-23 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-23 does not call broker endpoints.
BR-23 does not create trade instructions.
BR-23 does not create broker actions.
BR-23 does not create order paths.
BR-23 does not authorize live trading.
BR-23 does not mutate paper state.
BR-23 does not mutate live state.
BR-23 does not enable live trading.

## Required Evidence

- source_freshness
- provenance
- scenario_coverage
- replay_coverage
- decision_journal_completeness
- human_review_resolution
- paper_outcome_tracking
- risk_policy_compliance
- stale_data_rejection
- liquidity_rejection
- safety_boundaries

## Runtime Invariants

BR-23 must always prove:

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
- live_trading_authorized=false
- broker_actions_authorized=false
- order_paths_authorized=false
- data_provider_calls_authorized=false
- LIVE TRADING: DISABLED

## Artifacts

The default source evidence paths are:

- `reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json`
- `reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json`
- `reports/br20_paper_research_decision_journal/paper_research_decision_journal.json`
- `reports/br21_human_review_resolution_ledger/human_review_resolution_ledger.json`
- `reports/br22_paper_outcome_tracker/paper_outcome_tracker.json`

The default output directory is `reports/br23_promotion_gate_evidence_checklist`.

BR-23 writes:

- `promotion_gate_evidence_checklist.json`
- `promotion_gate_evidence_checklist.md`

Run locally:

```powershell
python scripts/run_br23_promotion_gate_evidence_checklist.py
```
