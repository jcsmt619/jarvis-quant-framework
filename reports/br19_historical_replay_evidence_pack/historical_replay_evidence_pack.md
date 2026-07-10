# BR-19 Historical Replay Evidence Pack

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Replay Windows
- BR19-WINDOW-2026-06-03-AM: 2026-06-03 09:30:00 to 11:00:00 regime=bullish_momentum source=engines/moonshot/deterministic/fixtures/br18_fixture_scenario_expansion_matrix.json
- BR19-WINDOW-2026-06-10-PM: 2026-06-10 13:00:00 to 15:30:00 regime=liquidity_stress source=engines/moonshot/deterministic/fixtures/br18_fixture_scenario_expansion_matrix.json
- BR19-WINDOW-2026-06-17-CLOSE: 2026-06-17 15:00:00 to 16:00:00 regime=review_only_chop source=reports/br14_local_paper_research_session_runner/manual_20260709T194500/local_paper_research_session.json

## Metrics
- replay_window_count: 3
- replay_record_count: 4
- paper_only_change_count: 2
- blocked_risk_gate_count: 1
- human_review_risk_gate_count: 1
- paper_only_risk_gate_count: 2
- monitor_observation_count: 4
- unresolved_review_item_count: 5
- human_review_action_count: 6

## Replay Records
- BR19-REPLAY-001: scenario=bullish symbol=NVDA candidate=selected chain=passed score=97 risk=paper_hold:PAPER_ONLY paper_change=simulated_entry monitor=clear
- BR19-REPLAY-002: scenario=poor-liquidity symbol=XYZL candidate=blocked chain=blocked score=0 risk=rejected:BLOCKED_BY_SAFETY_GATE paper_change=none monitor=liquidity_alert
- BR19-REPLAY-003: scenario=neutral symbol=AAPL candidate=selected_for_watch chain=passed score=76 risk=review_required:HUMAN_REVIEW_REQUIRED paper_change=none monitor=watch
- BR19-REPLAY-004: scenario=paper-hold symbol=NVDA candidate=existing_paper_candidate chain=passed score=94 risk=paper_hold:PAPER_ONLY paper_change=hold_existing monitor=hold_monitor

## Unresolved Review Items
- BR19-REPLAY-001: Confirm replay thesis evidence remains sufficient for historical-style paper hold classification.
- BR19-REPLAY-002: Verify poor-liquidity rejection remains correct under historical replay window.
- BR19-REPLAY-002: Confirm no downstream paper entry was generated.
- BR19-REPLAY-003: Determine whether neutral replay evidence should stay on watchlist only.
- BR19-REPLAY-004: Confirm existing paper hold remains aligned with BR-14 committed evidence.

## Required Human Review Actions
- BR19-REPLAY-001: Review NVDA replay record against source fixture before allowing any future workflow change.
- BR19-REPLAY-001: Confirm simulated paper entry remains PAPER_ONLY and never broker-routed.
- BR19-REPLAY-002: Reject any attempt to promote XYZL replay evidence without fresh approved data boundary work.
- BR19-REPLAY-003: Keep AAPL replay item HUMAN_REVIEW_REQUIRED until a reviewer closes the neutral thesis question.
- BR19-REPLAY-004: Review existing NVDA paper hold before changing monitor status.
- BR19-REPLAY-004: Confirm no live state mutation occurred during replay evidence generation.

## Dashboard References
- BR19-REPLAY-001: BR19-DASH-NVDA-PAPER-HOLD label=MONITOR_ONLY
- BR19-REPLAY-002: BR19-DASH-XYZL-BLOCKED label=MONITOR_ONLY
- BR19-REPLAY-003: BR19-DASH-AAPL-REVIEW label=MONITOR_ONLY
- BR19-REPLAY-004: BR19-DASH-NVDA-HOLD label=MONITOR_ONLY

## Acceptance Criteria
- fixture_input_exists: True
- offline_replay_only: True
- all_replay_windows_have_records: True
- all_records_have_required_sections: True
- portfolio_changes_are_paper_only: True
- thesis_context_requires_human_review: True
- monitoring_is_monitor_only: True
- human_review_actions_present: True
- no_credentials_or_secrets: True
- no_data_provider_or_network_calls: True
- no_broker_or_order_paths: True
- live_trading_disabled: True
- human_review_required: True

## Safety Boundaries
- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.
- Offline replay-only evidence generation from committed fixture inputs.
- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.
- Paper-only portfolio changes are simulated evidence records and never routed externally.