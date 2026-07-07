# 11A Dual Engine Folder Structure

Jarvis separates strategy systems into two engines:

- `engines/wealth`: portfolio and allocation-oriented research workflows.
- `engines/moonshot`: LEAPS and asymmetric setup research workflows.

Each engine has the same internal boundary:

- `deterministic/`: repeatable strategy, monitor, backtest, scoring, and
  paper-only drill modules.
- `analyst_outputs/`: non-deterministic analyst memos, research summaries,
  catalyst review, and critique artifacts.

## Safety Contract

Deterministic code must be testable, repeatable, auditable, and blocked by
safety gates when appropriate. Analyst output is research-only and cannot
execute trades, override deterministic gates, or bypass human approval.

Required labels:

- `RESEARCH_ONLY`
- `MONITOR_ONLY`
- `PAPER_ONLY`
- `HUMAN_REVIEW_REQUIRED`
- `BLOCKED_BY_SAFETY_GATE`

11A is structure-only. It does not add broker order routing, live execution,
or secret access. LIVE TRADING: DISABLED.
