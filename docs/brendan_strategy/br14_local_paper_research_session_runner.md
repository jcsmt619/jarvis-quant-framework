# BR-14 Local Paper Research Session Runner

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-14 runs a local paper-only research session using fixture/sample data by default. It composes existing safe modules into one dry run:

- BR-10C Track B Config Driven Screener Pipeline
- BR-02 Candidate Universe Builder
- BR-03 Options Chain Quality Scanner
- BR-04 Greeks IV Spread DTE Scoring
- BR-05 LLM Analyst Thesis Generator
- BR-06 Deterministic Trade Score Risk Gate
- BR-07 Paper Options Portfolio Manager
- BR-08 Daily Position Monitor Alert Engine
- BR-09 Local Operator Dashboard

## Safety Boundaries

BR-14 does not load credentials.
BR-14 does not request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-14 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-14 does not submit broker orders.
BR-14 does not add broker order routing.
BR-14 does not enable live trading.

## Runtime Invariants

BR-14 must always prove:

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

The default output directory is `reports/br14_local_paper_research_session_runner`.

The runner writes a session JSON/Markdown summary plus nested static artifacts for each composed phase. Simulated fills are generated only from BR-06 `PAPER_ONLY` decisions, and monitor snapshots are derived from local fixture contract data. All trade-relevant output remains `HUMAN_REVIEW_REQUIRED`.

Run locally:

```powershell
python scripts/run_br14_local_paper_research_session.py
```
