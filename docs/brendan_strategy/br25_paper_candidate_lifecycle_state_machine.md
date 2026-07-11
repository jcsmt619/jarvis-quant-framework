# BR-25 Paper Candidate Lifecycle State Machine

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-25 creates deterministic JSON and Markdown state-machine records for paper research candidates.

The state machine defines how candidates can move between blocked, review_required, paper_only, stale, duplicate, closed, and needs_more_evidence states. It records allowed transitions, forbidden transitions, source evidence requirements, review resolution requirements, outcome tracker requirements, promotion gate requirements, audit trail requirements, and safety boundary requirements.

## Safety Boundaries

BR-25 is read-only over committed BR-24 source evidence.
BR-25 is offline-only and deterministic.
BR-25 writes only state-machine report artifacts.
BR-25 does not read `.env`.
BR-25 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-25 does not call data providers.
BR-25 does not fetch real market data.
BR-25 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-25 does not call broker endpoints.
BR-25 does not create trade instructions.
BR-25 does not create broker actions.
BR-25 does not create order paths.
BR-25 does not mutate paper state.
BR-25 does not mutate live state.
BR-25 does not mutate broker state.
BR-25 does not mutate routing state.
BR-25 does not authorize live trading.
BR-25 does not enable live trading.

## Lifecycle States

- blocked
- review_required
- paper_only
- stale
- duplicate
- closed
- needs_more_evidence

## Requirement Sections

- source_evidence_requirements
- review_resolution_requirements
- outcome_tracker_requirements
- promotion_gate_requirements
- audit_trail_requirements
- safety_boundary_requirements

## Transition Boundaries

Allowed transitions are deterministic and require source evidence, review resolution evidence when applicable, outcome tracker evidence when applicable, promotion gate evidence when entering paper_only, an audit trail event, and disabled safety boundary proof.

Forbidden transitions are explicitly recorded for every state pair outside the transition table. Closed records are terminal. Self-transitions are forbidden because state retention should be recorded as an audit note or review resolution, not as a lifecycle transition.

## Runtime Invariants

BR-25 must always prove:

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
- live_state_mutation_allowed=false
- broker_state_mutation_allowed=false
- routing_state_mutation_allowed=false
- live_trading_enabled=false
- live_trading_authorized=false
- broker_actions_authorized=false
- order_paths_authorized=false
- data_provider_calls_authorized=false
- LIVE TRADING: DISABLED

## Artifacts

The default source evidence path is:

- `reports/br24_consolidated_research_dossier/consolidated_research_dossier.json`

The default output directory is `reports/br25_paper_candidate_lifecycle_state_machine`.

BR-25 writes:

- `paper_candidate_lifecycle_state_machine.json`
- `paper_candidate_lifecycle_state_machine.md`

Run locally:

```powershell
python scripts/run_br25_paper_candidate_lifecycle_state_machine.py
```
