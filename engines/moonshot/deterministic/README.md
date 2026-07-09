# Moonshot Deterministic Lane

Use this lane for repeatable LEAPS research components:

- option-chain quality monitors
- BR-01 options LEAPS data model fixtures for equities, contracts, chains,
  Greeks, implied volatility, volume, open interest, spreads, DTE, catalysts,
  paper positions, and analyst thesis records
- BR-02 candidate universe builder fixtures and deterministic watchlists for
  sector, liquidity, trend, volatility, catalyst, market-cap, and options
  availability filters
- BR-04 Greeks, implied-volatility, spread, DTE, liquidity, and contract
  suitability scoring with explainable component scores
- BR-06 deterministic trade score risk gate combining chain quality, Greeks,
  liquidity, thesis quality, concentration, drawdown, and catalyst timing
- Greek calculations
- theta decay monitors
- IV and DTE monitors
- deterministic candidate scoring
- dashboard alert state
- research-only option thesis memos with Greeks-aware risk notes and
  expiration handling
- static options monitor dashboards and JSON/Markdown report outputs
- research-only crypto risk guards for drawdown, liquidity, volatility, and
  stale market data warnings

Outputs must use `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`,
`HUMAN_REVIEW_REQUIRED`, or `BLOCKED_BY_SAFETY_GATE` as appropriate.

LIVE TRADING: DISABLED.
