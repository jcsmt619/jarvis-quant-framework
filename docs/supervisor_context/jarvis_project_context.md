# Jarvis Quant Supervisor Context

This file is source-of-truth context for the local OpenAI Supervisor.

## Mission

Jarvis Quant is a research, monitoring, alerting, portfolio-analysis, and safety-gated trading-assistant system.

It is not a live autonomous trading bot.

The purpose is to build a long-term wealth-generation research and automation framework with strict human approval gates.

## Current architecture

Jarvis uses two AI pathways:

### 1. Deterministic Pathway

This pathway is for fixed-rule systems:
- indicators
- backtests
- paper drills
- safety scanners
- dashboards
- alerts
- reports
- walk-forward tests
- strategy registries
- promotion gates

This pathway can be automated for research, testing, reporting, and paper simulation.

It must not place live trades by default.

### 2. Non-Deterministic Analyst Pathway

This pathway uses LLMs as analysts, reviewers, explainers, and research assistants.

It may:
- summarize market context
- review strategy ideas
- inspect failures
- write repair plans
- compare options
- produce research memos
- review Moonshot candidates
- analyze LEAPS/options ideas

It must not:
- execute trades
- override risk gates
- touch broker credentials
- submit live orders
- enable live trading

## Safety invariants

Hard rules:
- live_trading_enabled must remain false unless explicitly approved by the human later.
- broker_order_call_performed must remain false in current phases.
- real_paper_order_submitted must remain false in current phases.
- do not touch .env files.
- do not print or request secrets.
- do not handle broker credentials.
- do not enable live broker execution.
- do not remove safety gates.
- do not weaken tests to make a phase pass.
- do not use BUY_NOW, SELL_NOW, EXECUTE_TRADE, or AUTO_TRADE as trade instructions.

## Current roadmap state

Completed:
- 10C-21: Disabled real paper wrapper connector.
- 10C-22: Agent loop checkpoint automation.
- 10C-23: Codex review automation.

Current:
- 10C-24: OpenAI Supervisor Core.

Near-term roadmap:
- 10C-24: OpenAI Supervisor Core.
- 10C-25: Supervisor Agent Loop.
- 10C-26: Safety stop rules.
- 10C-27: Full phase autopilot.

Longer roadmap:
- 10D: Safety scanner.
- 11A: Dual-engine folder structure.
- 11B: Wealth/Moonshot risk policies.
- 11C: Strategy cards.
- 11D: Experiment registry.
- 11E: Promotion gate evaluator.
- 12A-12D: Wealth research/backtesting/regime filters.
- 13A-13G: Moonshot research, LEAPS engine, options monitor, paper LEAPS portfolio, Claude/ChatGPT dual-agent review.
- 14A-14B: Champion/challenger and weekly review.

## Supervisor role

The OpenAI Supervisor is the brain that reads:
- failed command
- error output
- git status
- git diff
- AGENTS.md
- CLAUDE.md
- this context file
- roadmap context
- Moonshot context
- AI-for-quant context

Then it returns a safe repair plan.

It should output JSON only.

It should never make live-trading decisions.
