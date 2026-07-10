# BR-04 Greeks IV Spread DTE Scoring

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Metrics
- contract_count: 6
- suitable_contract_count: 4
- blocked_contract_count: 2
- human_review_required_count: 6

## Suitable Contracts
- NVDA-20271217-C-140: total_score=100, label=MONITOR_ONLY, dte=527, iv=0.44
- NVDA-20271217-C-180: total_score=100, label=MONITOR_ONLY, dte=527, iv=0.46
- NVDA-20271217-C-220: total_score=92, label=MONITOR_ONLY, dte=527, iv=0.49
- NVDA-20271217-C-260: total_score=82, label=MONITOR_ONLY, dte=527, iv=0.53

## Blocked Contracts
- ABCD-20260821-C-45: total_score=50, label=BLOCKED_BY_SAFETY_GATE, reasons=vega_below_minimum, implied_volatility_below_minimum, spread_below_minimum, dte_below_minimum, liquidity_below_minimum, total_score_below_minimum
- ABCD-20260821-C-55: total_score=19, label=BLOCKED_BY_SAFETY_GATE, reasons=delta_below_minimum, theta_below_minimum, vega_below_minimum, implied_volatility_below_minimum, spread_below_minimum, dte_below_minimum, liquidity_below_minimum, total_score_below_minimum

## Component Scores
- NVDA-20271217-C-140
  - delta: score=100, weight=15, passed=True, reason=delta_inside_target_band
  - theta: score=100, weight=12, passed=True, reason=theta_decay_inside_ideal_limit
  - vega: score=100, weight=10, passed=True, reason=vega_inside_ideal_floor
  - implied_volatility: score=100, weight=14, passed=True, reason=implied_volatility_inside_ideal_band
  - spread: score=100, weight=12, passed=True, reason=spread_inside_ideal_limit
  - dte: score=100, weight=14, passed=True, reason=dte_inside_ideal_band
  - liquidity: score=100, weight=13, passed=True, reason=volume_and_open_interest_inside_ideal_floor
  - contract_suitability: score=100, weight=10, passed=True, reason=strike_to_underlying_inside_ideal_band
- NVDA-20271217-C-180
  - delta: score=100, weight=15, passed=True, reason=delta_inside_target_band
  - theta: score=100, weight=12, passed=True, reason=theta_decay_inside_ideal_limit
  - vega: score=100, weight=10, passed=True, reason=vega_inside_ideal_floor
  - implied_volatility: score=100, weight=14, passed=True, reason=implied_volatility_inside_ideal_band
  - spread: score=100, weight=12, passed=True, reason=spread_inside_ideal_limit
  - dte: score=100, weight=14, passed=True, reason=dte_inside_ideal_band
  - liquidity: score=100, weight=13, passed=True, reason=volume_and_open_interest_inside_ideal_floor
  - contract_suitability: score=100, weight=10, passed=True, reason=strike_to_underlying_inside_ideal_band
- NVDA-20271217-C-220
  - delta: score=100, weight=15, passed=True, reason=delta_inside_target_band
  - theta: score=100, weight=12, passed=True, reason=theta_decay_inside_ideal_limit
  - vega: score=100, weight=10, passed=True, reason=vega_inside_ideal_floor
  - implied_volatility: score=100, weight=14, passed=True, reason=implied_volatility_inside_ideal_band
  - spread: score=70, weight=12, passed=True, reason=spread_inside_acceptable_limit
  - dte: score=100, weight=14, passed=True, reason=dte_inside_ideal_band
  - liquidity: score=70, weight=13, passed=True, reason=volume_and_open_interest_inside_minimum_floor
  - contract_suitability: score=100, weight=10, passed=True, reason=strike_to_underlying_inside_ideal_band
- NVDA-20271217-C-260
  - delta: score=70, weight=15, passed=True, reason=delta_inside_acceptable_band
  - theta: score=100, weight=12, passed=True, reason=theta_decay_inside_ideal_limit
  - vega: score=70, weight=10, passed=True, reason=vega_inside_acceptable_floor
  - implied_volatility: score=100, weight=14, passed=True, reason=implied_volatility_inside_ideal_band
  - spread: score=70, weight=12, passed=True, reason=spread_inside_acceptable_limit
  - dte: score=100, weight=14, passed=True, reason=dte_inside_ideal_band
  - liquidity: score=70, weight=13, passed=True, reason=volume_and_open_interest_inside_minimum_floor
  - contract_suitability: score=70, weight=10, passed=True, reason=strike_to_underlying_inside_acceptable_band
- ABCD-20260821-C-45
  - delta: score=100, weight=15, passed=True, reason=delta_inside_target_band
  - theta: score=100, weight=12, passed=True, reason=theta_decay_inside_ideal_limit
  - vega: score=0, weight=10, passed=False, reason=missing_vega
  - implied_volatility: score=25, weight=14, passed=False, reason=implied_volatility_outside_acceptable_band
  - spread: score=20, weight=12, passed=False, reason=spread_above_acceptable_limit
  - dte: score=25, weight=14, passed=False, reason=dte_outside_acceptable_band
  - liquidity: score=25, weight=13, passed=False, reason=volume_or_open_interest_below_minimum_floor
  - contract_suitability: score=100, weight=10, passed=True, reason=strike_to_underlying_inside_ideal_band
- ABCD-20260821-C-55
  - delta: score=0, weight=15, passed=False, reason=missing_delta
  - theta: score=0, weight=12, passed=False, reason=missing_theta
  - vega: score=0, weight=10, passed=False, reason=missing_vega
  - implied_volatility: score=0, weight=14, passed=False, reason=missing_implied_volatility
  - spread: score=20, weight=12, passed=False, reason=spread_above_acceptable_limit
  - dte: score=25, weight=14, passed=False, reason=dte_outside_acceptable_band
  - liquidity: score=25, weight=13, passed=False, reason=volume_or_open_interest_below_minimum_floor
  - contract_suitability: score=100, weight=10, passed=True, reason=strike_to_underlying_inside_ideal_band

## Safety
- Deterministic options scoring report only; no broker routing or order submission.
- Contract suitability is monitor-only research and requires human review.
- Report-level state remains blocked by safety gate.