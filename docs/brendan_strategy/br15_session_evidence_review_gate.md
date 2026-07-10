# BR-15 Session Evidence Review Gate

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-15 reads the committed BR-14 local paper research session evidence and writes deterministic JSON/Markdown review reports. It summarizes evidence integrity, safety manifest state, session metrics, session flow completeness, generated artifact presence, simulated paper contracts, monitor alerts, readiness state, unresolved review items, acceptance criteria, and required human review actions.

## Safety Boundaries

BR-15 is evidence-review-only.
BR-15 does not rerun the BR-14 session.
BR-15 does not mutate evidence.
BR-15 does not delete artifacts.
BR-15 does not load credentials.
BR-15 does not request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-15 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-15 does not call broker endpoints.
BR-15 does not create broker actions.
BR-15 does not create order paths.
BR-15 does not enable live trading.

## Runtime Invariants

BR-15 must always prove:

- session_rerun_attempted=false
- evidence_mutation_attempted=false
- artifact_deletion_attempted=false
- credential_loading_attempted=false
- broker_connection_attempted=false
- broker_read_call_performed=false
- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- broker_order_submitted=false
- broker_order_routing_enabled=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Artifacts

The default evidence directory is `reports/br14_local_paper_research_session_runner/manual_20260709T194500`.

The default output directory is `reports/br15_session_evidence_review_gate`.

BR-15 writes:

- `session_evidence_review_gate.json`
- `session_evidence_review_gate.md`

Run locally:

```powershell
python scripts/run_br15_session_evidence_review_gate.py
```
