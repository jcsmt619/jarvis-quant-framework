# BR-03 Options Chain Quality Scanner

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Metrics
- chain_count: 2
- passed_chain_count: 1
- blocked_chain_count: 1
- contract_count: 6
- passed_contract_count: 4
- blocked_contract_count: 2
- human_review_required_count: 8

## Passed Chains
- NVDA: score=100, strikes=4, label=MONITOR_ONLY

## Blocked Chains
- ABCD: score=0, label=BLOCKED_BY_SAFETY_GATE, reasons=strike_availability_below_minimum, one_or_more_contracts_failed_quality_gate, chain_score_below_minimum

## Contract Quality Flags
- ABCD-20260821-C-45: score=0, label=BLOCKED_BY_SAFETY_GATE, reasons=spread_pct_above_maximum, volume_below_minimum, open_interest_below_minimum, dte_below_minimum, stale_quote_data, missing_greeks, implied_volatility_out_of_range, contract_score_below_minimum
- ABCD-20260821-C-55: score=0, label=BLOCKED_BY_SAFETY_GATE, reasons=spread_pct_above_maximum, volume_below_minimum, open_interest_below_minimum, dte_below_minimum, stale_quote_data, missing_greeks, missing_implied_volatility, contract_score_below_minimum

## Safety
- Deterministic option-chain quality report only; no broker routing or order submission.
- Quality pass state is monitor-only research and requires human review.
- Report-level state remains blocked by safety gate.