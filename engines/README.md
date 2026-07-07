# Jarvis Dual Engine Structure

Phase 11A creates two engine lanes:

- `wealth`: broad portfolio research, monitoring, and paper-only strategy work.
- `moonshot`: high-conviction LEAPS and asymmetric setup research.

Each engine keeps deterministic code separate from non-deterministic analyst
outputs.

## Boundary Rules

`deterministic/` is for repeatable strategy modules, scoring rules, monitors,
backtests, and safety-gated paper drills. Code in this lane must be testable,
auditable, and reproducible.

`analyst_outputs/` is for non-deterministic research memos, LLM analyst notes,
thesis reviews, news summaries, and second-opinion critiques. Anything
trade-relevant in this lane requires `HUMAN_REVIEW_REQUIRED`.

Allowed safety labels are:

- `RESEARCH_ONLY`
- `MONITOR_ONLY`
- `PAPER_ONLY`
- `HUMAN_REVIEW_REQUIRED`
- `BLOCKED_BY_SAFETY_GATE`

## Execution Safety

This structure does not add broker adapters, order routing, or live execution.
Engine outputs are research, monitoring, paper-only drills, or human-review
records. LIVE TRADING: DISABLED.
