# Jarvis Quant — Agent Instructions

These instructions apply to OpenAI Codex, Claude Code, Cline, and any coding agent working in this repository.

## Primary Rule

Jarvis is safety-first.

Agents may build:
- research modules
- dashboards
- alerts
- tests
- monitoring
- paper drills
- approval workflows
- audit and heartbeat systems
- deterministic strategy systems
- non-deterministic analyst review workflows

Agents may not:
- place trades
- enable live broker execution
- bypass safety gates
- touch secrets

## Latest Known Good State

10C-20 is committed:
- paper-arm drill state written to audit ledger
- paper-arm drill state written to heartbeat notes
- next phase is 10C-21 Real Paper Wrapper Connector — Disabled by Default

## AI Pathways Architecture

Jarvis has two AI pathways.

### Deterministic Pathway

This pathway builds fixed-rule systems.

Examples:
- RSI
- MACD
- Bollinger Bands
- Keltner Channels
- Z-score
- CCI
- Williams %R
- mean reversion systems
- LEAPS/options monitors
- backtests
- walk-forward tests
- slippage stress tests
- dashboards
- alerts
- paper drills

Rules:
- Must be testable.
- Must be repeatable.
- Must be auditable.
- Must have safety gates.
- Must not place live trades by default.

### Non-Deterministic Analyst Pathway

This pathway uses LLMs as analysts.

Examples:
- thesis review
- catalyst analysis
- news summaries
- ticker screening
- option-chain quality review
- LEAPS setup review
- risk/reward explanation
- second-opinion critique

Rules:
- Analyst output is research-only.
- Analyst output cannot directly execute trades.
- Analyst output cannot override deterministic gates.
- Analyst output must be labeled HUMAN_REVIEW_REQUIRED when trade-relevant.

## Do Not Touch

- .env
- API keys
- broker credentials
- OAuth tokens
- private keys
- live trading toggles
- production order execution code
- user payment credentials

## Required Behavior

Before editing:
- Read this file.
- Inspect the repo.
- Explain the plan.
- Keep scope small.

After editing:
- Run tests.
- Read errors.
- Fix errors.
- Summarize changes.
- Show remaining risks.

## Required Labels

Use these labels:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE

Never use these labels as trade instructions:
- BUY_NOW
- SELL_NOW
- EXECUTE_TRADE
- AUTO_TRADE

## 10C-21 Safety Requirements

10C-21 is Real Paper Wrapper Connector — Disabled by Default.

It must prove:
- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Moonshot LEAPS Rules

The Moonshot LEAPS system is research-only.

It may:
- score candidates
- pull option chains
- calculate Greeks
- monitor theta decay
- monitor IV
- monitor DTE
- flag targets/stops
- summarize news
- produce dashboard alerts
- produce human-review-required research memos

It may not:
- place options trades
- route orders
- tell the user to buy immediately
- bypass human approval
- override risk limits
