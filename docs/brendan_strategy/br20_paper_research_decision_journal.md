# BR-20 Paper Research Decision Journal

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-20 creates deterministic JSON and Markdown paper research decision journal records from committed source evidence.

The journal explains why paper candidates were held, rejected, or sent for review. Each record links source evidence, scenario context, candidate scores, option-chain quality, contract scores, thesis package references, risk gate reasons, paper-only portfolio state, monitor outcomes, operator notes, acceptance criteria, and required human-review actions.

## Safety Boundaries

BR-20 is read-only over source evidence.
BR-20 writes only paper research journal report artifacts.
BR-20 does not read `.env`.
BR-20 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-20 does not call data providers.
BR-20 does not fetch real market data.
BR-20 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-20 does not call broker endpoints.
BR-20 does not create trade instructions.
BR-20 does not create broker actions.
BR-20 does not create order paths.
BR-20 does not mutate live state.
BR-20 does not enable live trading.

## Runtime Invariants

BR-20 must always prove:

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

The default source evidence is `engines/moonshot/deterministic/fixtures/br19_historical_replay_evidence_pack.json`.

The default output directory is `reports/br20_paper_research_decision_journal`.

BR-20 writes:

- `paper_research_decision_journal.json`
- `paper_research_decision_journal.md`

Run locally:

```powershell
python scripts/run_br20_paper_research_decision_journal.py
```
