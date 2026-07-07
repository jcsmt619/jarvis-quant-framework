# Moonshot Engine

The Moonshot engine is for research-only LEAPS and asymmetric opportunity
workflows. It may score candidates, monitor Greeks, track IV and DTE, flag
watchlist conditions, summarize news, and produce human-review-required memos.

## Folders

- `deterministic/`: repeatable LEAPS monitors, scoring rules, and dashboard
  alert conditions.
- `analyst_outputs/`: research memos, quality reviews, catalyst notes, and
  risk/reward critiques.

Moonshot outputs are research-only, monitor-only, paper-only, or
human-review-required. This engine must not place options trades or route
orders.

## 11B Risk Policy

The Moonshot risk policy is defined as `MOONSHOT_RISK_POLICY` in
`risk.policies`. It is `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`, and
`HUMAN_REVIEW_REQUIRED`, with max loss, drawdown, position sizing, promotion
gate, and stop-condition limits for LEAPS research. LIVE TRADING: DISABLED.

## 13A Moonshot Simulator

`engines.moonshot.deterministic.simulator` provides deterministic high-risk
scenario simulation for Moonshot research. It applies Moonshot risk caps,
records failure modes, and writes JSON/Markdown reports. Outputs are
research-only and paper-only, and blocked scenarios are retained for audit
visibility. LIVE TRADING: DISABLED.
