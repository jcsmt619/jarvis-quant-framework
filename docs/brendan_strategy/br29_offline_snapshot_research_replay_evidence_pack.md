# BR-29 Offline Snapshot Research Replay Evidence Pack

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-29 consumes BR-28 snapshot-derived candidates and replays them through frozen deterministic screening, strategy, liquidity, correlation, portfolio-risk, lifecycle, safety, and paper-only reporting boundaries.

The phase is opportunity-driven. Zero candidates can advance when none qualify, and multiple independent candidates can advance when all deterministic gates pass. BR-29 does not impose a permanent fixed daily trade quota.

BR-29 does not claim alpha merely because the report passes. Metrics that require unavailable frozen source data are emitted as unsupported with explicit blockers and human-review actions.

## Safety Boundaries

BR-29 is offline, read-only, deterministic, report-only, fixture-testable, research-only, monitor-only, paper-only, and human-review-required.
BR-29 reads only the BR-28 deterministic JSON report by default.
BR-29 writes only deterministic JSON and Markdown artifacts.
BR-29 does not read `.env`.
BR-29 does not load, request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
BR-29 does not call data providers.
BR-29 does not fetch real market data at runtime.
BR-29 does not connect to brokers.
BR-29 does not perform broker write operations.
BR-29 does not create trade instructions.
BR-29 does not create broker actions.
BR-29 does not create order paths.
BR-29 does not create external routing paths.
BR-29 does not mutate paper state.
BR-29 does not mutate live state.
BR-29 does not mutate broker state.
BR-29 does not mutate routing state.
BR-29 does not authorize live trading.
BR-29 does not enable live trading.

## Frozen Inputs

Default source evidence:

- `reports/br28_snapshot_to_candidate_adapter/snapshot_to_candidate_adapter.json`

BR-29 requires the BR-28 acceptance criteria to pass before candidates are replayed.

## Supported Evidence

BR-29 records:

- deterministic gate results
- advanced candidate count
- blocked candidate count
- trade count as paper-only research reportable decisions
- turnover
- gross exposure
- max symbol weight
- cost sensitivity from turnover
- symbol contribution placeholders
- unresolved blockers
- required human-review actions

## Unsupported Performance Evidence

The default BR-28 snapshot candidates do not include post-decision exit prices, outcome return series, benchmark return series, fold history, or parameter-neighborhood replay results.

Therefore BR-29 marks these as unsupported instead of fabricating them:

- gross_research_return
- net_research_return
- hit_rate
- max_drawdown
- sharpe
- sortino
- calmar
- benchmark_excess_return
- fold_stability_score
- parameter_neighborhood_evidence

## Runtime Invariants

BR-29 must always prove:

- credential_loading_attempted=false
- env_file_read_attempted=false
- secret_request_attempted=false
- data_provider_call_attempted=false
- external_network_call_attempted=false
- real_data_fetch_attempted=false
- broker_connection_attempted=false
- broker_read_call_performed=false
- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- broker_order_submitted=false
- broker_order_routing_enabled=false
- trade_instruction_created=false
- broker_action_created=false
- order_path_created=false
- live_state_mutation_attempted=false
- paper_state_mutation_attempted=false
- paper_state_mutation_allowed=false
- live_trading_enabled=false
- broker_write_operations_authorized=false
- external_routing_paths_authorized=false
- data_provider_calls_authorized=false
- fixed_daily_trade_quota_imposed=false
- alpha_claim_created=false
- evaluation_period_tuning_performed=false
- parameter_optimization_performed=false
- strategy_selected_using_evaluation_outcomes=false
- LIVE TRADING: DISABLED

## Artifacts

The default output directory is `reports/br29_offline_snapshot_research_replay_evidence_pack`.

BR-29 writes:

- `offline_snapshot_research_replay_evidence_pack.json`
- `offline_snapshot_research_replay_evidence_pack.md`

Run locally:

```powershell
python scripts/run_br29_offline_snapshot_research_replay_evidence_pack.py
```
