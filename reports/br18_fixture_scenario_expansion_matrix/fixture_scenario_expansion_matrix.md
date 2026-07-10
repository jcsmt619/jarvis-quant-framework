# BR-18 Fixture Scenario Expansion Matrix

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Purpose
BR-18 expands offline fixture coverage across deterministic Moonshot LEAPS scenario outcomes and proves expected behavior through the research pipeline.

## Metrics
- scenario_count: 10
- pipeline_stage_count: 8
- matrix_cell_count: 80
- paper_hold_scenario_count: 2
- blocked_scenario_count: 6
- human_review_scenario_count: 2
- monitor_alert_scenario_count: 8
- dashboard_summary_count: 10

## Scenario Matrix
| Scenario | Candidate | Chain | Score | Thesis | Risk Gate | Paper Sim | Alerts | Dashboard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bullish | selected (RESEARCH_ONLY) | passed (MONITOR_ONLY) | high_score (HUMAN_REVIEW_REQUIRED) | packaged (HUMAN_REVIEW_REQUIRED) | paper_hold (PAPER_ONLY) | simulated_hold (PAPER_ONLY) | clear (MONITOR_ONLY) | paper_hold_visible (MONITOR_ONLY) |
| bearish | selected_for_review (RESEARCH_ONLY) | passed (MONITOR_ONLY) | low_score (HUMAN_REVIEW_REQUIRED) | packaged (HUMAN_REVIEW_REQUIRED) | review_required (HUMAN_REVIEW_REQUIRED) | no_fill (PAPER_ONLY) | risk_review_alert (MONITOR_ONLY) | review_visible (MONITOR_ONLY) |
| neutral | selected_for_watch (RESEARCH_ONLY) | passed (MONITOR_ONLY) | medium_score (HUMAN_REVIEW_REQUIRED) | packaged (HUMAN_REVIEW_REQUIRED) | review_required (HUMAN_REVIEW_REQUIRED) | no_fill (PAPER_ONLY) | watch (MONITOR_ONLY) | watch_visible (MONITOR_ONLY) |
| stale-data | selected_for_check (RESEARCH_ONLY) | blocked (BLOCKED_BY_SAFETY_GATE) | skipped (BLOCKED_BY_SAFETY_GATE) | skipped (HUMAN_REVIEW_REQUIRED) | rejected (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | stale_data_alert (MONITOR_ONLY) | blocked_visible (MONITOR_ONLY) |
| poor-liquidity | blocked (BLOCKED_BY_SAFETY_GATE) | blocked (BLOCKED_BY_SAFETY_GATE) | skipped (BLOCKED_BY_SAFETY_GATE) | skipped (HUMAN_REVIEW_REQUIRED) | rejected (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | liquidity_alert (MONITOR_ONLY) | blocked_visible (MONITOR_ONLY) |
| no-candidate | empty (RESEARCH_ONLY) | skipped (MONITOR_ONLY) | skipped (HUMAN_REVIEW_REQUIRED) | skipped (HUMAN_REVIEW_REQUIRED) | no_decision (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | empty (MONITOR_ONLY) | empty_state (MONITOR_ONLY) |
| thesis-missing | selected (RESEARCH_ONLY) | passed (MONITOR_ONLY) | high_score (HUMAN_REVIEW_REQUIRED) | missing (HUMAN_REVIEW_REQUIRED) | rejected (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | thesis_alert (MONITOR_ONLY) | review_visible (MONITOR_ONLY) |
| chain-quality-failed | selected (RESEARCH_ONLY) | failed (BLOCKED_BY_SAFETY_GATE) | blocked (BLOCKED_BY_SAFETY_GATE) | skipped (HUMAN_REVIEW_REQUIRED) | rejected (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | quality_alert (MONITOR_ONLY) | blocked_visible (MONITOR_ONLY) |
| risk-rejected | selected (RESEARCH_ONLY) | passed (MONITOR_ONLY) | high_score (HUMAN_REVIEW_REQUIRED) | packaged (HUMAN_REVIEW_REQUIRED) | rejected (BLOCKED_BY_SAFETY_GATE) | no_fill (PAPER_ONLY) | risk_gate_alert (MONITOR_ONLY) | blocked_visible (MONITOR_ONLY) |
| paper-hold | existing_paper_candidate (RESEARCH_ONLY) | passed (MONITOR_ONLY) | hold_score (HUMAN_REVIEW_REQUIRED) | packaged (HUMAN_REVIEW_REQUIRED) | paper_hold (PAPER_ONLY) | hold_existing (PAPER_ONLY) | hold_monitor (MONITOR_ONLY) | paper_hold_visible (MONITOR_ONLY) |

## Scenario Outcomes
- bullish: risk=paper_hold label=PAPER_ONLY paper=simulated_hold alert=clear
- bearish: risk=review_required label=HUMAN_REVIEW_REQUIRED paper=no_fill alert=risk_review_alert
- neutral: risk=review_required label=HUMAN_REVIEW_REQUIRED paper=no_fill alert=watch
- stale-data: risk=rejected label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=stale_data_alert
- poor-liquidity: risk=rejected label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=liquidity_alert
- no-candidate: risk=no_decision label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=empty
- thesis-missing: risk=rejected label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=thesis_alert
- chain-quality-failed: risk=rejected label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=quality_alert
- risk-rejected: risk=rejected label=BLOCKED_BY_SAFETY_GATE paper=no_fill alert=risk_gate_alert
- paper-hold: risk=paper_hold label=PAPER_ONLY paper=hold_existing alert=hold_monitor

## Stage Status Counts
- candidate_selection: blocked=1, empty=1, existing_paper_candidate=1, selected=4, selected_for_check=1, selected_for_review=1, selected_for_watch=1
- chain_quality: blocked=2, failed=1, passed=6, skipped=1
- contract_scoring: blocked=1, high_score=3, hold_score=1, low_score=1, medium_score=1, skipped=3
- thesis_packaging: missing=1, packaged=5, skipped=4
- risk_gate_decision: no_decision=1, paper_hold=2, rejected=5, review_required=2
- paper_only_portfolio_simulation: hold_existing=1, no_fill=8, simulated_hold=1
- monitor_alerts: clear=1, empty=1, hold_monitor=1, liquidity_alert=1, quality_alert=1, risk_gate_alert=1, risk_review_alert=1, stale_data_alert=1, thesis_alert=1, watch=1
- dashboard_summary: blocked_visible=4, empty_state=1, paper_hold_visible=2, review_visible=2, watch_visible=1

## Acceptance Criteria
- all_required_scenarios_present: True
- all_pipeline_stages_covered: True
- fixture_only_offline: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_or_order_paths: True
- paper_simulation_only: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Offline fixture-only matrix generation.
- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.
- Paper-only portfolio behavior is simulated locally and never routed externally.