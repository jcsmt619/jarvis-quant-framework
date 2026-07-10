# BR-12 Human Approved Execution Safety Design

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-12 defines a future human-approved execution safety boundary. It is a design phase only. The goal is to document the approval gates, broker adapter boundaries, kill switches, position limits, audit trails, and manual confirmations that a later reviewed phase would need before any real broker-facing workflow could be considered.

BR-12 does not enable live trading.
BR-12 does not load credentials.
BR-12 does not connect to Alpaca, IBKR, TradeStation, or any broker.
BR-12 does not submit broker orders.

## Approval Gates

Future broker-facing workflows must be blocked unless every gate has an explicit pass result:

- strategy_signal_review
- risk_policy_review
- position_limit_review
- broker_adapter_boundary_review
- operator_manual_confirmation
- audit_receipt_review

Each gate must be HUMAN_REVIEW_REQUIRED when trade-relevant and BLOCKED_BY_SAFETY_GATE on failure. Analyst output, research rankings, alerts, or paper-only drill state cannot override these gates.

## Broker Adapter Boundary

The future boundary must separate research, monitoring, paper intent, and broker calls:

- research modules may produce RESEARCH_ONLY outputs
- monitors may produce MONITOR_ONLY outputs
- paper workflows may produce PAPER_ONLY outputs
- trade-relevant interpretations must require HUMAN_REVIEW_REQUIRED
- broker adapter construction must remain separate from approval evaluation
- credentials must never be requested, printed, serialized, or included in exceptions
- broker account identifiers must be hashed or omitted from audit trails

BR-12 safety flags:

- credential_loading_required=false
- broker_connection_attempted=false
- broker_order_routing_enabled=false
- broker_order_call_performed=false
- broker_order_submitted=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Kill Switches

Future approval design requires kill switches that default to engaged until an operator explicitly clears them in a later reviewed phase:

- global_operator_halt
- strategy_halt
- symbol_halt
- broker_adapter_halt
- stale_data_halt
- audit_write_failure_halt

Any kill switch failure must produce BLOCKED_BY_SAFETY_GATE. Audit write failure must block because an unrecorded approval path is not acceptable.

## Position Limits

The design requires positive, blocking position limits before any future broker-facing workflow:

- max_position_notional_pct
- max_daily_loss_pct
- max_open_positions
- max_symbol_concentration_pct

Limit checks must happen before any broker adapter call. Limit breaches must block and must be written to the audit trail.

## Audit Trail

A future audit receipt must be append-only and must include:

- request_id
- phase
- timestamp_utc
- operator_id_hash
- strategy_id
- symbol
- approval_gate_results
- position_limit_results
- manual_confirmation_results
- decision
- live_trading_status

Audit trails must not contain secrets, tokens, account numbers, raw broker credentials, or private keys.

## Manual Confirmations

Future manual confirmation requirements:

- operator_identity_confirmed
- account_scope_confirmed
- symbol_and_quantity_confirmed
- risk_limits_confirmed
- kill_switches_confirmed_clear
- audit_receipt_confirmed

BR-12 only defines these confirmation names. It does not record live operator confirmations, does not treat a confirmation as permission to trade, and does not create an approval receipt that can reach a broker.

## Operator Interpretation

BR-12 is a safety design artifact. It is not a trading system, not a broker adapter, not an approval receipt, and not permission to place orders. Any later implementation must be reviewed in a separate phase and must continue to prove LIVE TRADING: DISABLED unless explicitly authorized outside this roadmap phase.
