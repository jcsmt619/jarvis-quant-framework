# BR-29 Offline Snapshot Research Replay Evidence Pack

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Source Evidence
- BR-28 snapshot-to-candidate adapter report: reports\br28_snapshot_to_candidate_adapter\snapshot_to_candidate_adapter.json

## Replay Checks
- br28_report_loaded: True
- br28_report_accepted: True
- candidates_remain_human_review_required: True
- frozen_deterministic_boundaries_used: True
- opportunity_driven_selection: True
- no_fixed_daily_trade_quota: True
- aggregate_risk_budget_enforced: True
- concentration_limit_enforced: True
- duplicate_signal_controls_enforced: True
- operational_circuit_breakers_enforced: True
- post_decision_outcomes_available: False
- no_alpha_claim_created: True

## Supported Metrics
- turnover: 1.0
- gross_exposure: 1.0
- max_symbol_weight: 0.5
- trade_count: 2
- candidate_count: 2
- advanced_candidate_count: 2
- blocked_candidate_count: 0
- cost_sensitivity_supported: True
- symbol_contribution_supported: True
- parameter_neighborhood_supported: False
- alpha_claimed: False

## Unsupported Metrics
- gross_research_return: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- net_research_return: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- hit_rate: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- max_drawdown: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- sharpe: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- sortino: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- calmar: unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series
- benchmark_excess_return: unsupported because benchmark return series is not present in the frozen BR-28 candidate report
- fold_stability_score: unsupported because fold-level walk-forward or CPCV outcomes are not present in the frozen BR-28 candidate report

## Candidate Replay Decisions
- br28-7eb903a69e21c8ab: symbol=QQQ status=PAPER_ONLY_RESEARCH_REPORTABLE weight=0.5 label=PAPER_ONLY
- br28-f90aa6a950622bf1: symbol=SPY status=PAPER_ONLY_RESEARCH_REPORTABLE weight=0.5 label=PAPER_ONLY

## Cost Sensitivity
- 0 bps: estimated_turnover_cost=0.0 net_return_supported=False
- 5 bps: estimated_turnover_cost=0.0005 net_return_supported=False
- 10 bps: estimated_turnover_cost=0.001 net_return_supported=False
- 25 bps: estimated_turnover_cost=0.0025 net_return_supported=False
- 50 bps: estimated_turnover_cost=0.005 net_return_supported=False

## Symbol Contribution
- QQQ: paper_weight=0.5 gross_return_contribution=None
- SPY: paper_weight=0.5 gross_return_contribution=None

## Unresolved Blockers
- performance_metrics: post_decision_exit_prices_missing, outcome_return_series_missing
- benchmark_metrics: benchmark_return_series_missing
- fold_stability: fold_history_missing
- parameter_neighborhood: parameter_neighborhood_source_missing

## Required Human Review Actions
- br28-7eb903a69e21c8ab: Review BR-29 offline replay evidence before any research promotion decision.
- br28-7eb903a69e21c8ab: Confirm missing post-decision outcome data before interpreting performance metrics.
- br28-f90aa6a950622bf1: Review BR-29 offline replay evidence before any research promotion decision.
- br28-f90aa6a950622bf1: Confirm missing post-decision outcome data before interpreting performance metrics.
- BR-29: Do not claim alpha or approve live trading from this offline evidence pack.

## Acceptance Criteria
- br28_report_loaded: True
- br28_report_accepted: True
- offline_read_only_replay: True
- opportunity_driven_selection: True
- no_fixed_daily_trade_quota: True
- risk_budget_and_concentration_enforced: True
- duplicate_and_circuit_breakers_enforced: True
- unsupported_performance_metrics_block_alpha_claim: True
- human_review_actions_present: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_state_mutation: True
- live_trading_disabled: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Offline, read-only, deterministic evidence generation from BR-28 snapshot-derived candidates.
- Opportunity-driven selection is enforced; zero candidates can advance when none qualify, and multiple independent candidates can advance when all gates pass.
- No permanent fixed daily trade quota is imposed.
- No alpha is claimed merely because this report is generated.
- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, order routing, state mutation, or live trading authorization.
