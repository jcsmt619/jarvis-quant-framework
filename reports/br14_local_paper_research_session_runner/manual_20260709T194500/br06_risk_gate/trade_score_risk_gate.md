# BR-06 Deterministic Trade Score Risk Gate

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Metrics
- candidate_count: 6
- paper_only_count: 2
- human_review_required_count: 1
- monitor_only_count: 0
- research_only_count: 0
- blocked_count: 3

## Gate Decisions
- NVDA-20271217-C-140: score=97, label=PAPER_ONLY, hard_blocks=
- NVDA-20271217-C-180: score=94, label=PAPER_ONLY, hard_blocks=
- NVDA-20271217-C-220: score=87, label=HUMAN_REVIEW_REQUIRED, hard_blocks=
- NVDA-20271217-C-260: score=79, label=BLOCKED_BY_SAFETY_GATE, hard_blocks=proposed_position_pct_above_maximum, symbol_concentration_above_maximum
- ABCD-20260821-C-45: score=33, label=BLOCKED_BY_SAFETY_GATE, hard_blocks=chain_quality_failed, contract_score_failed, portfolio_drawdown_above_maximum, candidate_drawdown_above_maximum
- ABCD-20260821-C-55: score=23, label=BLOCKED_BY_SAFETY_GATE, hard_blocks=chain_quality_failed, contract_score_failed

## Component Scores
- NVDA-20271217-C-140
  - chain_quality: score=100, weight=15, reason=chain_quality_score
  - contract_score: score=100, weight=20, reason=contract_total_score
  - greeks: score=100, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=100, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=96, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=80, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=92, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=86, weight=5, reason=days_to_next_catalyst_score
- NVDA-20271217-C-180
  - chain_quality: score=100, weight=15, reason=chain_quality_score
  - contract_score: score=100, weight=20, reason=contract_total_score
  - greeks: score=100, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=100, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=96, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=63, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=84, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=79, weight=5, reason=days_to_next_catalyst_score
- NVDA-20271217-C-220
  - chain_quality: score=100, weight=15, reason=chain_quality_score
  - contract_score: score=92, weight=20, reason=contract_total_score
  - greeks: score=100, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=70, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=96, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=73, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=88, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=40, weight=5, reason=days_to_next_catalyst_score
- NVDA-20271217-C-260
  - chain_quality: score=100, weight=15, reason=chain_quality_score
  - contract_score: score=82, weight=20, reason=contract_total_score
  - greeks: score=85, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=70, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=96, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=0, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=80, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=83, weight=5, reason=days_to_next_catalyst_score
- ABCD-20260821-C-45
  - chain_quality: score=0, weight=15, reason=chain_quality_score
  - contract_score: score=50, weight=20, reason=contract_total_score
  - greeks: score=56, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=22, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=0, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=93, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=0, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=78, weight=5, reason=days_to_next_catalyst_score
- ABCD-20260821-C-55
  - chain_quality: score=0, weight=15, reason=chain_quality_score
  - contract_score: score=19, weight=20, reason=contract_total_score
  - greeks: score=0, weight=15, reason=delta_theta_vega_iv_score
  - liquidity: score=22, weight=15, reason=spread_volume_open_interest_score
  - thesis_quality: score=0, weight=15, reason=source_grounded_analyst_thesis_score
  - concentration: score=93, weight=8, reason=position_and_symbol_exposure_score
  - drawdown: score=90, weight=7, reason=portfolio_and_candidate_drawdown_score
  - catalyst_timing: score=45, weight=5, reason=days_to_next_catalyst_score

## Safety
- Deterministic trade score risk gate only; no broker routing or order submission.
- Candidate outputs remain research-only, monitor-only, paper-only, or human-review-required.
- Report-level state remains blocked by safety gate.