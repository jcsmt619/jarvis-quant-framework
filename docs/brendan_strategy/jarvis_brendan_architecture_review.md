# BR-00 Jarvis Architecture Review

## Architecture decision

Jarvis will pivot from generic records-cycle expansion into a Brendan-style AI analyst plus deterministic options research system.

## Operating mantra

LLM proposes.
Deterministic engine scores.
Risk gate filters.
Paper portfolio simulates.
Dashboard explains.
Human reviews.

## Target system

The target system is a paper-first autonomous research and monitoring platform.

It has six layers:

### 1. Data layer

Collects or loads:

- equities universe
- watchlists
- price history
- option chains
- Greeks
- implied volatility
- volume and open interest
- spreads
- news and catalyst metadata
- paper portfolio state

Initial implementation may use deterministic fixtures and local JSON files before live data adapters.

### 2. Deterministic scoring layer

Scores candidates using fixed rules:

- liquidity score
- spread score
- DTE score
- theta risk score
- volatility score
- trend score
- catalyst score
- risk/reward score
- concentration score
- safety score

### 3. Non-deterministic analyst layer

Uses an LLM as an analyst, not as an executor.

It may produce:

- thesis memos
- risks
- catalyst summaries
- watchlist explanations
- comparison of candidates
- position review notes
- suggested paper-only actions for human review

### 4. Risk gate layer

The deterministic gate decides whether a candidate is:

- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE

The gate must block candidates with poor liquidity, unsafe spreads, excessive theta decay, missing data, stale data, excessive concentration, or missing thesis.

### 5. Paper portfolio layer

The paper portfolio manager can:

- create simulated positions
- update simulated marks
- track paper PnL
- record simulated entries and exits
- generate action suggestions
- produce daily review records

It must not touch live broker accounts.

### 6. Dashboard layer

A local desktop or browser dashboard should show:

- system safety status
- watched symbols
- candidate rankings
- options chain quality
- Greeks and DTE
- paper positions
- paper PnL
- open thesis memos
- deterministic scores
- risk gate decisions
- daily action queue
- blocked workflows
- operator review items

## Engineering principle

Jarvis should not become an endless record generator.

The next roadmap must build practical trading-research infrastructure:

- candidates
- chains
- scores
- paper trades
- monitoring
- dashboard
- reports
- human review

## Promotion rule

No live trading promotion is allowed inside BR-00 through BR-12.

A future separate live-trading approval track may be designed later, but only after paper results are validated and explicit human approval is recorded.

## Safety boundary

LIVE TRADING: DISABLED.

BR phases are RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, and BLOCKED_BY_SAFETY_GATE until a separate future approval track explicitly changes that.

No broker routing, broker calls, broker order submission, credential-file access, live trading, order execution, or automatic trade actions are enabled by BR-00 through BR-12.
