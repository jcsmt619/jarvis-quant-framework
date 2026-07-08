# BR-00 Brendan Strategy Import

This document imports the relevant strategy architecture from the Brendan video transcript into Jarvis.

## Source concept

The transcript describes a trading workflow where an LLM is used as a non-deterministic analyst and portfolio advisor, while deterministic software tracks positions, alerts, indicators, and portfolio state.

The important architecture is not the claimed profit result. The important architecture is the workflow:

1. Provide the LLM with account context, risk tolerance, time horizon, and constraints.
2. Ask the LLM to form a strategy.
3. Ask the LLM to research candidate tickers and option contracts.
4. Use deterministic software to monitor price action, news, alerts, Greeks, time decay, and portfolio state.
5. Re-query the LLM for analysis and adjustments when new information arrives.
6. Keep the human in the loop.

## Jarvis interpretation

Jarvis should implement a stricter version:

LLM proposes.
Deterministic engine scores.
Risk gate filters.
Paper portfolio simulates.
Dashboard explains.
Human reviews.
Live trading remains disabled unless a separate future approval phase explicitly changes that.

## What Brendan-style Jarvis should monitor

Jarvis should monitor:

- candidate tickers
- LEAPS and longer-dated call options
- option chains
- strike selection
- expiration selection
- bid/ask spread
- volume
- open interest
- implied volatility
- delta
- theta
- vega
- DTE
- catalyst timing
- price action
- trend
- invalidation levels
- risk/reward
- portfolio concentration
- paper PnL
- drawdown
- daily action queue

## Required safety stance

BR phases are research-only and paper-only until explicitly promoted later.

Required labels:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- LIVE TRADING: DISABLED

The system must not:
- place broker orders
- route broker orders
- call broker order endpoints
- use broker credentials
- read credential files
- enable live trading
- grant execution permission
- mutate real broker positions
- present records as guaranteed profit

## Immediate implementation target

Build a paper-first Jarvis options and LEAPS research autopilot with a local dashboard.

The first production milestone is not live trading.

The first production milestone is:

A local dashboard where the operator can see what Jarvis is watching, why it likes or rejects candidates, what the deterministic gate says, what the paper portfolio is doing, and which safety blocks remain active.
