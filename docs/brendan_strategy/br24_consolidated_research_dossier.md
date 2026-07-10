# BR-24 Consolidated Research Dossier

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-24 creates deterministic JSON and Markdown dossier records that consolidate BR-14 through BR-23 evidence into one operator-facing packet.

The dossier summarizes source evidence, candidate universe, option chain quality, contract scoring, thesis package context, risk gate outcomes, paper-only portfolio records, monitor observations, manual review packet, scenario matrix, replay evidence, paper decision journal, human review resolution ledger, paper outcome tracker, promotion gate checklist, unresolved blockers, required human review actions, acceptance criteria, and immutable safety boundaries.

## Safety Boundaries

BR-24 is read-only over committed source reports.
BR-24 is offline-only and deterministic.
BR-24 writes only consolidated dossier report artifacts.
BR-24 does not read `.env`.
BR-24 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-24 does not call data providers.
BR-24 does not fetch real market data.
BR-24 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-24 does not call broker endpoints.
BR-24 does not create trade instructions.
BR-24 does not create broker actions.
BR-24 does not create order paths.
BR-24 does not authorize live trading.
BR-24 does not mutate paper state.
BR-24 does not mutate live state.
BR-24 does not enable live trading.

## Dossier Sections

- source_evidence
- candidate_universe
- option_chain_quality
- contract_scoring
- thesis_package_context
- risk_gate_outcomes
- paper_only_portfolio_records
- monitor_observations
- manual_review_packet
- scenario_matrix
- replay_evidence
- paper_decision_journal
- human_review_resolution_ledger
- paper_outcome_tracker
- promotion_gate_checklist
- unresolved_blockers
- required_human_review_actions
- acceptance_criteria
- immutable_safety_boundaries

## Runtime Invariants

BR-24 must always prove:

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
- paper_state_mutation_allowed=false
- trading_state_mutation_allowed=false
- LIVE TRADING: DISABLED

## Artifacts

The default source evidence paths are:

- `reports/br14_local_paper_research_session_runner/manual_20260709T194500/local_paper_research_session.json`
- `reports/br15_session_evidence_review_gate/session_evidence_review_gate.json`
- `reports/br16_fixture_to_real_data_boundary/fixture_to_real_data_boundary.json`
- `reports/br17_manual_report_review_packet/manual_report_review_packet.json`
- `reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json`
- `reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json`
- `reports/br20_paper_research_decision_journal/paper_research_decision_journal.json`
- `reports/br21_human_review_resolution_ledger/human_review_resolution_ledger.json`
- `reports/br22_paper_outcome_tracker/paper_outcome_tracker.json`
- `reports/br23_promotion_gate_evidence_checklist/promotion_gate_evidence_checklist.json`

The default output directory is `reports/br24_consolidated_research_dossier`.

BR-24 writes:

- `consolidated_research_dossier.json`
- `consolidated_research_dossier.md`

Run locally:

```powershell
python scripts/run_br24_consolidated_research_dossier.py
```
