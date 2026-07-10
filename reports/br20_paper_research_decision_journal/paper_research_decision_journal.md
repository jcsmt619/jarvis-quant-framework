# BR-20 Paper Research Decision Journal

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

Source evidence: engines\moonshot\deterministic\fixtures\br19_historical_replay_evidence_pack.json

## Metrics
- journal_record_count: 4
- held_count: 2
- rejected_count: 1
- sent_for_review_count: 1
- paper_only_portfolio_state_count: 4
- monitor_outcome_count: 4
- human_review_action_count: 6
- operator_note_count: 8
- blocked_risk_gate_count: 1

## Decision Records
- BR20-JOURNAL-001: held symbol=NVDA candidate_score=96 chain_quality=100 contract_score=97 risk=paper_hold:PAPER_ONLY monitor=clear
- BR20-JOURNAL-002: rejected symbol=XYZL candidate_score=21 chain_quality=18 contract_score=0 risk=rejected:BLOCKED_BY_SAFETY_GATE monitor=liquidity_alert
- BR20-JOURNAL-003: sent_for_review symbol=AAPL candidate_score=72 chain_quality=82 contract_score=76 risk=review_required:HUMAN_REVIEW_REQUIRED monitor=watch
- BR20-JOURNAL-004: held symbol=NVDA candidate_score=91 chain_quality=100 contract_score=94 risk=paper_hold:PAPER_ONLY monitor=hold_monitor

## Held
- BR20-JOURNAL-001: NVDA contract=NVDA-20271217-C-140 reason=deterministic_replay_gates_passed_for_paper_record_only
- BR20-JOURNAL-004: NVDA contract=NVDA-20271217-C-180 reason=hold_existing_paper_position

## Rejected
- BR20-JOURNAL-002: XYZL contract=XYZL-20261218-C-25 reason=poor_liquidity

## Sent For Review
- BR20-JOURNAL-003: AAPL contract=AAPL-20270115-C-240 reason=insufficient_edge_for_paper_hold

## Source Evidence
- BR20-JOURNAL-001: engines\moonshot\deterministic\fixtures\br19_historical_replay_evidence_pack.json#BR19-REPLAY-001 sections=candidate_decision,option_chain_state,contract_scoring,thesis_context,risk_gate_outcome,paper_portfolio_change,monitor_observation,dashboard_reference
- BR20-JOURNAL-002: engines\moonshot\deterministic\fixtures\br19_historical_replay_evidence_pack.json#BR19-REPLAY-002 sections=candidate_decision,option_chain_state,contract_scoring,thesis_context,risk_gate_outcome,paper_portfolio_change,monitor_observation,dashboard_reference
- BR20-JOURNAL-003: engines\moonshot\deterministic\fixtures\br19_historical_replay_evidence_pack.json#BR19-REPLAY-003 sections=candidate_decision,option_chain_state,contract_scoring,thesis_context,risk_gate_outcome,paper_portfolio_change,monitor_observation,dashboard_reference
- BR20-JOURNAL-004: engines\moonshot\deterministic\fixtures\br19_historical_replay_evidence_pack.json#BR19-REPLAY-004 sections=candidate_decision,option_chain_state,contract_scoring,thesis_context,risk_gate_outcome,paper_portfolio_change,monitor_observation,dashboard_reference

## Required Human Review Actions
- BR20-JOURNAL-001: Review NVDA replay record against source fixture before allowing any future workflow change.
- BR20-JOURNAL-001: Confirm simulated paper entry remains PAPER_ONLY and never broker-routed.
- BR20-JOURNAL-002: Reject any attempt to promote XYZL replay evidence without fresh approved data boundary work.
- BR20-JOURNAL-003: Keep AAPL replay item HUMAN_REVIEW_REQUIRED until a reviewer closes the neutral thesis question.
- BR20-JOURNAL-004: Review existing NVDA paper hold before changing monitor status.
- BR20-JOURNAL-004: Confirm no live state mutation occurred during replay evidence generation.

## Acceptance Criteria
- source_evidence_path_recorded: True
- read_only_paper_records: True
- all_records_have_required_sections: True
- held_rejected_review_categories_present: True
- paper_portfolio_state_is_paper_only: True
- monitor_outcomes_are_monitor_only: True
- human_review_actions_present: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_actions_order_paths_or_live_mutation: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Read-only paper research journal records generated from committed source evidence.
- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.
- Paper-only portfolio state is journal evidence and never routed externally.