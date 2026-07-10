# BR-11 Read Only Broker Account Sync Design

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-11 defines the future shape of read-only broker account-state import. It is a design and interface phase only. The goal is to let later phases reason about broker-reported account state without adding a broker connection, credential loader, order route, or execution permission in this phase.

BR-11 does not require credentials.
BR-11 does not connect to Alpaca, IBKR, TradeStation, or any broker.

## Scope

Allowed future import fields:

- account_status
- cash
- equity
- buying_power
- positions
- open_orders
- source_timestamp_utc

Allowed current artifacts:

- broker-neutral dataclasses for account, position, and open-order snapshots
- a provider protocol named `ReadOnlyBrokerAccountSyncProvider`
- disabled-by-default design-state evaluation
- snapshot validation for local fixture or test data
- runtime notes proving no connection, import, order route, or live trading occurred

## Non-Goals

BR-11 does not:

- connect to Alpaca, IBKR, TradeStation, or any broker
- load credentials
- require credentials
- read or write secret files
- register a provider in `broker.get_broker()`
- submit, cancel, replace, close, or route broker orders
- enable paper or live execution
- import real account state by default
- promote account-state import into a trading signal

## Interface Boundary

`broker/account_sync_design.py` owns the BR-11 interface layer:

- `BrokerAccountSyncSnapshot` is the account-state payload shape.
- `BrokerAccountPositionSnapshot` is a read-only position row.
- `BrokerAccountOpenOrderSnapshot` is a read-only open-order row with hashed broker order identity only.
- `ReadOnlyBrokerAccountSyncProvider` is a future protocol that returns a snapshot.
- `evaluate_broker_account_sync_design()` returns a disabled design state and never receives or calls a provider object.
- `validate_account_sync_snapshot()` validates local snapshot payloads without connecting to a broker.

The protocol intentionally separates provider construction from snapshot use. Any future provider must be reviewed in a separate phase before it may load credentials or perform read calls.

## Safety Invariants

The BR-11 safety manifest must always prove:

- credential_loading_required=false
- broker_connection_attempted=false
- broker_read_call_performed=false
- broker_order_call_performed=false
- account_state_imported=false
- order_routing_enabled=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

If a future phase permits read calls, it must still preserve:

- read-only broker permissions
- no execution permissions
- no order routes
- no credential printing
- no account numbers in reports
- hashed external identifiers only
- HUMAN_REVIEW_REQUIRED for trade-relevant interpretation

## Future Phase Checklist

Before account sync can move beyond design-only status, a later phase must add a separate reviewed provider implementation with tests proving:

- credentials are loaded only through an approved secret-safe mechanism
- credentials are never printed, serialized, or included in exceptions
- read permissions are sufficient and write permissions are not required
- startup defaults do not connect
- every broker read is explicit and auditable
- every report labels imported account state as MONITOR_ONLY and HUMAN_REVIEW_REQUIRED when trade-relevant
- broker order calls remain blocked
- live trading remains disabled

## Operator Interpretation

Imported account state, when a future phase enables it, is evidence for reconciliation and monitoring only. It is not a trading instruction, not an approval receipt, and not permission to execute.
