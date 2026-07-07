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
