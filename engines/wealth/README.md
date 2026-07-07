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

## 11B Risk Policy

The Wealth risk policy is defined as `WEALTH_RISK_POLICY` in `risk.policies`.
It is `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`, and
`HUMAN_REVIEW_REQUIRED`, with max loss, drawdown, position sizing, promotion
gate, and stop-condition limits. LIVE TRADING: DISABLED.
