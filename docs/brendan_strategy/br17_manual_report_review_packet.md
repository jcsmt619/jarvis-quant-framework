# BR-17 BR-14 Manual Report Review Packet

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-17 reads the committed BR-14 local paper research session evidence and writes deterministic JSON/Markdown human-review packets. It summarizes candidate universe, options chain quality, contract scoring, LLM thesis package, deterministic risk gate decisions, simulated paper contracts, paper portfolio state, monitor alerts, operator dashboard references, review questions, hold/reject/review categories, and required human review actions.

## Safety Boundaries

BR-17 is read-only packet generation.
BR-17 does not rerun the BR-14 session.
BR-17 does not edit evidence.
BR-17 does not delete artifacts.
BR-17 does not load credentials.
BR-17 does not request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-17 does not call data providers.
BR-17 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-17 does not call broker endpoints.
BR-17 does not create trade instructions.
BR-17 does not create broker actions.
BR-17 does not create order paths.
BR-17 does not enable live trading.

## Runtime Invariants

BR-17 must always prove:

- session_rerun_attempted=false
- evidence_mutation_attempted=false
- artifact_deletion_attempted=false
- credential_loading_attempted=false
- data_provider_call_attempted=false
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
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Artifacts

The default evidence directory is `reports/br14_local_paper_research_session_runner/manual_20260709T194500`.

The default output directory is `reports/br17_manual_report_review_packet`.

BR-17 writes:

- `manual_report_review_packet.json`
- `manual_report_review_packet.md`

Run locally:

```powershell
python scripts/run_br17_manual_report_review_packet.py
```
