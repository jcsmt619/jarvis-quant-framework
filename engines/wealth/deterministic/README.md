# Wealth Deterministic Lane

Use this lane for fixed-rule systems that can be tested and replayed:

- allocation scoring
- risk monitors
- regime filters
- backtests
- walk-forward validation
- paper-only drill state

Outputs must use `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`, or
`BLOCKED_BY_SAFETY_GATE` as appropriate.

12D Wealth regime filters are deterministic research gates for volatility,
trend, liquidity, and risk-off state. They emit audit columns and an offline
research multiplier only; they do not route or submit orders.
