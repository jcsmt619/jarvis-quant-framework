# Wealth Engine

The Wealth engine is for portfolio-oriented deterministic systems and
research-only analyst review. It can host allocation research, risk monitors,
backtests, dashboards, paper-only drills, and human-review-required memos.

## Folders

- `deterministic/`: repeatable rules, monitors, strategy components, and
  paper-only drills.
- `analyst_outputs/`: research memos, thesis reviews, catalyst summaries, and
  second-opinion notes.

Deterministic components must not depend on analyst memo text for execution.
Analyst outputs must not override deterministic gates.
