# BR-17 BR-14 Manual Report Review Packet

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Source Session
- source_as_of: 2026-07-08T16:00:00
- label: HUMAN_REVIEW_REQUIRED
- screener_queue_count: 3
- candidate_count: 5
- chain_count: 2
- contract_count: 6
- analyst_prompt_package_count: 1
- risk_gate_decision_count: 6
- simulated_paper_fill_count: 2
- paper_position_count: 2
- monitor_alert_count: 0
- dashboard_candidate_count: 5

## Candidate Universe
- review: NVDA score=89 label=MONITOR_ONLY
- review: MSFT score=83 label=MONITOR_ONLY
- review: TSLA score=70 label=MONITOR_ONLY
- reject: ABCD score=60 reasons=price_trend_below_minimum, volatility_above_maximum
- reject: XYZL score=38 reasons=average_volume_below_minimum, dollar_volume_below_minimum, options_not_available

## Options Chain Quality
- passed_chain_count: 1
- blocked_chain_count: 1
- hold/review: NVDA score=100 contracts=4
- reject: ABCD reasons=strike_availability_below_minimum, one_or_more_contracts_failed_quality_gate, chain_score_below_minimum

## Contract Scoring
- review: NVDA-20271217-C-140 total_score=100 label=MONITOR_ONLY
- review: NVDA-20271217-C-180 total_score=100 label=MONITOR_ONLY
- review: NVDA-20271217-C-220 total_score=92 label=MONITOR_ONLY
- review: NVDA-20271217-C-260 total_score=82 label=MONITOR_ONLY
- reject: ABCD-20260821-C-45 total_score=50 reasons=vega_below_minimum, implied_volatility_below_minimum, spread_below_minimum, dte_below_minimum, liquidity_below_minimum, total_score_below_minimum
- reject: ABCD-20260821-C-55 total_score=19 reasons=delta_below_minimum, theta_below_minimum, vega_below_minimum, implied_volatility_below_minimum, spread_below_minimum, dte_below_minimum, liquidity_below_minimum, total_score_below_minimum

## LLM Thesis Package
- THESIS-BR05-NVDA-001: symbol=NVDA confidence=medium label=HUMAN_REVIEW_REQUIRED

## Deterministic Risk Gate Decisions
- hold: NVDA-20271217-C-140 score=97 label=PAPER_ONLY
- hold: NVDA-20271217-C-180 score=94 label=PAPER_ONLY
- review: NVDA-20271217-C-220 score=87 label=HUMAN_REVIEW_REQUIRED
- reject: NVDA-20271217-C-260 score=79 label=BLOCKED_BY_SAFETY_GATE
- reject: ABCD-20260821-C-45 score=33 label=BLOCKED_BY_SAFETY_GATE
- reject: ABCD-20260821-C-55 score=23 label=BLOCKED_BY_SAFETY_GATE

## Simulated Paper Contracts
- NVDA-20271217-C-140: fill_id=BR-14-PAPER-FILL-001 premium=4280.0 label=PAPER_ONLY
- NVDA-20271217-C-180: fill_id=BR-14-PAPER-FILL-002 premium=2880.0 label=PAPER_ONLY

## Paper Portfolio State
- cash: 92840.0
- total_pnl: 143.2
- net_liquidation_value: 100143.2
- premium_at_risk_pct: 0.0716

## Monitor Alerts
- alert_count: 0
- no_monitor_alerts

## Operator Dashboard References
- candidate_count: 5
- paper_position_count: 2
- NVDA: label=PAPER_ONLY review_required=True
- MSFT: label=MONITOR_ONLY review_required=True
- TSLA: label=MONITOR_ONLY review_required=True
- ABCD: label=BLOCKED_BY_SAFETY_GATE review_required=True
- XYZL: label=BLOCKED_BY_SAFETY_GATE review_required=True

## Hold Reject Review Categories
- hold: NVDA-20271217-C-140, NVDA-20271217-C-180
- review: NVDA-20271217-C-220
- reject: NVDA-20271217-C-260, ABCD-20260821-C-45, ABCD-20260821-C-55

## Review Questions
- Do BR-14 candidate inclusion and exclusion reasons match the committed evidence?
- Do passed option chains and scored contracts remain source-grounded and complete enough for human review?
- Do thesis records cite only supplied evidence and remain labeled HUMAN_REVIEW_REQUIRED?
- Should hold-category paper contracts remain paper-only monitored items: NVDA-20271217-C-140, NVDA-20271217-C-180?
- Should review-category contracts remain blocked pending manual decision: NVDA-20271217-C-220?
- Are reject-category contracts correctly blocked by deterministic safety gates: NVDA-20271217-C-260, ABCD-20260821-C-45, ABCD-20260821-C-55?
- Are all broker, order-path, credential, and live-trading controls still disabled?

## Required Human Review Actions
- Human reviewer must compare this BR-17 packet against committed BR-14 evidence artifacts.
- Human reviewer must verify every trade-relevant item remains HUMAN_REVIEW_REQUIRED.
- Human reviewer must verify PAPER_ONLY items are simulated paper records, not broker actions.
- Human reviewer must reject any item whose source evidence is stale, missing, or inconsistent.
- Human reviewer must keep live trading disabled and broker order paths inactive.

## Acceptance Criteria
- source_phase_is_br14: True
- all_evidence_artifacts_loaded: True
- packet_is_read_only: True
- session_not_rerun: True
- evidence_not_mutated: True
- no_credentials_or_provider_calls: True
- no_broker_or_order_paths: True
- source_live_trading_disabled: True
- packet_live_trading_disabled: True
- hold_review_reject_categories_present: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Read-only packet generation from committed BR-14 evidence.
- No session rerun, evidence edit, credential loading, data-provider call, broker connection, broker action, order path, or live trading enablement.