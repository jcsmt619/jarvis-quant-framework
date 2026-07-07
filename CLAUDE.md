# Jarvis Quant — Claude Code Instructions

## Mission

Build Jarvis Quant as a research, monitoring, alerting, portfolio-analysis, and safety-gated trading-assistant system.

Jarvis uses a two-pathway AI architecture:

1. Deterministic Pathway
2. Non-Deterministic Analyst Pathway

The goal is to let coding agents build, test, monitor, and improve Jarvis while keeping all live-trading and broker-order actions locked behind safety gates and human approval.

## Current Priority

Continue the existing local autonomous orchestrator roadmap, then add Moonshot Jarvis as a research-only LEAPS/options monitor.

## Latest Known Good State

10C-20 is committed:
- paper-arm drill audit heartbeat integration
- latest commit: feat: add paper arm drill audit heartbeat integration
- next phase is 10C-21 Real Paper Wrapper Connector — Disabled by Default

## Existing Roadmap

- 9G: READY TO ARM report
- 10A: outbound alerts
- 10B: inbound approval replies
- 10C: local autonomous orchestrator
- 10D: safety scanner
- 11A: dual-engine folder structure
- 11B: Wealth/Moonshot risk policies
- 11C: strategy cards
- 11D: experiment registry
- 11E: promotion gate evaluator
- 12A-12D: Wealth mean-reversion lab, backtester, cost model, regime filter
- 13A-13C: Moonshot options/crypto simulators and risk guard
- 13D: Moonshot LEAPS Research Engine
- 13E: Moonshot Options Monitor Dashboard
- 13F: Moonshot Paper LEAPS Portfolio
- 13G: Claude/ChatGPT Dual-Agent Review
- 14A-14B: champion/challenger system and weekly review

## AI Pathways Architecture

### 1. Deterministic Pathway

The deterministic pathway uses fixed rules, repeatable code, tests, and measurable outputs.

It may build:
- RSI systems
- MACD systems
- Bollinger Band systems
- Keltner Channel systems
- Z-score systems
- CCI systems
- Williams %R systems
- LEAPS/options monitors
- backtest engines
- walk-forward tests
- slippage stress tests
- bootstrap tests
- regime filters
- portfolio analytics
- dashboards
- alerts
- approval-gated paper drills

Deterministic systems must be:
- testable
- repeatable
- auditable
- version-controlled
- protected by safety gates
- unable to place live trades by default

### 2. Non-Deterministic Analyst Pathway

The non-deterministic pathway uses Claude, ChatGPT, or another LLM as an analyst/advisor.

It may:
- summarize news
- identify possible catalysts
- explain risk/reward
- compare trade ideas
- critique a thesis
- score watchlist candidates
- review option-chain quality
- review LEAPS setups
- generate research memos
- act as a second-opinion risk reviewer

It may not:
- place trades
- submit broker orders
- bypass deterministic gates
- override risk limits
- directly issue live execution commands
- use labels like BUY_NOW, SELL_NOW, EXECUTE_TRADE, or AUTO_TRADE as trade instructions

### 3. Human Approval Layer

All potentially dangerous actions must remain human-review-required.

Human approval is required for:
- enabling paper wrapper connection
- enabling real broker order code
- changing live-trading toggles
- adding broker execution paths
- modifying .env or secrets
- moving from research to paper execution
- moving from paper execution to live execution

## Hard Safety Rules

- Never place live broker orders.
- Never enable live broker-order execution.
- Never bypass safety gates.
- Never remove trigger guards.
- Never modify .env, API keys, broker keys, OAuth tokens, passwords, or secrets.
- Never print secrets to terminal.
- Never commit secrets.
- Never run destructive commands without explicit human approval.
- Never change broker execution paths without explicit human approval.
- All trading-related outputs must be labeled research-only, monitor-only, paper-only, or human-review-required.

## Current Prohibition

No live trading.
No broker order submission.
No API order routing.
No automatic live execution.

Autopilot means:
- autonomous coding
- autonomous testing
- autonomous monitoring
- autonomous reporting
- autonomous paper/research simulation

Autopilot does not mean:
- autonomous live trading
- autonomous broker order submission
- autonomous options execution
- autonomous credential handling

## Required Workflow

For every task:
1. Inspect the repo before editing.
2. Read existing tests and architecture.
3. Create a short plan.
4. Implement one small milestone at a time.
5. Run focused tests first.
6. Run the full test suite only after focused tests pass.
7. Read failures.
8. Fix failures.
9. Summarize changed files.
10. Stop before dangerous actions.

## Token-Saving Rules

- Be concise.
- Do not inspect .venv, .git, __pycache__, reports, logs, node_modules, or generated artifacts unless asked.
- Do not read entire large files unless required.
- Prefer targeted file reads.
- Ask before large scans.
- Do not run broad rg searches over the entire repo unless necessary.

## Preferred Commands

Use PowerShell-compatible commands:
- python -m compileall .
- python -m pytest tests/ -q
- git status --short --untracked-files=all
- git branch --show-current
- git diff
- git add .
- git commit -m "message"

## Agent Roles

Claude Code:
- Main builder
- Edits code
- Runs tests
- Fixes failures
- Builds deterministic systems
- Builds dashboards and monitors

Codex/OpenAI:
- Reviewer
- Safety critic
- Architecture challenger
- Checks git diff
- Looks for broker-order risks
- Reviews deterministic and non-deterministic pathway boundaries

ChatGPT:
- Strategy architect
- Risk reviewer
- Prompt designer
- Second-opinion analyst

Claude/LLM Analyst:
- Thesis analyst
- News summarizer
- Catalyst reviewer
- LEAPS/options research assistant
- Non-deterministic analyst only unless explicitly converted into deterministic code and tested

## Moonshot LEAPS Rules

Moonshot LEAPS is research-only until explicitly approved.

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
- route options orders
- tell the user to buy immediately
- bypass human approval
- size positions without risk gates
