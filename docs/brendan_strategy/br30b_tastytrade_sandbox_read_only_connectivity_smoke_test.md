# BR-30B Tastytrade Sandbox Read Only Connectivity Smoke Test

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30B defines the tastytrade sandbox read-only connectivity smoke test.

Default execution is fixture-only/offline and fail closed. The separate `sandbox_network` mode is explicit operator-invoked only and requires an injected read-only sandbox client plus the BR-30A secure local OAuth bridge.

The smoke test is evidence-only. It is intended to prove that a local vaulted refresh token can be exchanged for a short-lived memory-only access token, that only `openid` and `read` are active for Jarvis, that a minimal customer/account discovery request can be redacted, that a sandbox quote token can be obtained, and that delayed sandbox market data for approved symbols such as `SPY` and `QQQ` can be normalized through the BR-30 and BR-26 contracts.

## Evidence Preserved

BR-30B preserves:

- raw evidence checksum
- normalized BR-26 evidence checksum
- feed identity
- provider timestamps
- exchange timestamps
- acquisition timestamps
- quote age
- delayed sandbox classification
- provenance scores
- schema version
- quality flags
- redacted customer/account fingerprints

Raw account identifiers must not appear in reports, logs, fixtures, or UI state.

## Safety Boundaries

BR-30B does not touch `.env`.
BR-30B does not request, print, modify, expose, persist, fixture, or report API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
Access tokens remain memory-only.
BR-30B does not provide account mutation methods.
BR-30B does not provide execution methods.
BR-30B does not add external routing.
BR-30B does not change positions.
BR-30B does not submit broker orders.
BR-30B does not add broker order routing.
BR-30B does not authorize live trading.

## Runtime Modes

- `offline`: default, fixture-only/offline, fail closed.
- `sandbox_network`: explicit operator-invoked mode requiring an injected OAuth bridge and read-only sandbox client.

The repository runner intentionally has no built-in network client. Running it in `sandbox_network` without an injected client remains blocked by safety gate.

## Boundary Cases

Mocked tests cover:

- token failure
- expired token
- wrong sandbox host
- unexpected scope
- delayed feed classification
- duplicate event
- stale quote
- clock skew
- disconnect
- reconnect boundary
- rate limit
- malformed payload
- missing symbol
- redaction

## Required Disabled State

- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Run

Offline fail-closed report:

```powershell
python scripts/run_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py
```

Explicit blocked sandbox-network mode from the repository runner:

```powershell
python scripts/run_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py --mode sandbox_network
```

Run tests:

```powershell
pytest tests/test_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py
```
