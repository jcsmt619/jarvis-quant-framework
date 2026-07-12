# BR-30B Tastytrade Sandbox Read Only Connectivity Smoke Test

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30B defines the tastytrade sandbox read-only connectivity smoke test. BR-30B1 adds the concrete tastytrade sandbox read-only network client and operator smoke runner.

Default execution is fixture-only/offline and fail closed. The separate `sandbox_network` mode is explicit operator-invoked only and requires both `--mode sandbox_network` and the exact confirmation value `I_CONFIRM_BR30B1_SANDBOX_READ_ONLY_NETWORK_SMOKE`.

The smoke test is evidence-only. It is intended to prove that a local vaulted refresh token can be exchanged for a short-lived memory-only access token, that only `openid` and `read` are requested by Jarvis, that a provider-granted sandbox `trade` scope remains raw provider metadata with no effective Jarvis trade capability, that a minimal customer/account discovery request can be redacted, that a sandbox quote token can be obtained, and that delayed sandbox market data for approved symbols `SPY` and `QQQ` can be normalized through the BR-30 and BR-26 contracts.

## BR-30B1 Network Allowlist

The only approved REST origin is:

- `https://api.cert.tastyworks.com`

The unverified `api.cert.tastytrade.com` host, production hosts, HTTP downgrade, cross-host redirects, arbitrary caller-supplied URLs, and redirects to non-approved origins are rejected.

The only approved POST is:

- `POST /oauth/token`

After authentication, the only approved REST reads are:

- `GET /customers/me/accounts`
- `GET /api-quote-tokens`

The concrete client does not represent or expose order, position, transaction, balance mutation, watchlist mutation, account mutation, or order-management endpoints.

The API quote token and access token remain memory-only. The websocket endpoint must come from the authenticated `/api-quote-tokens` response, must use `wss://`, and cannot be supplied or substituted by the caller. The bounded stream subscribes only to `SPY` and `QQQ`, collects a small delayed sandbox sample, then closes. Strict connect, read, and overall timeouts prevent long-running streams.

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
- request methods and paths
- status classes
- explicit zero counts for provider-resource writes, order calls, mutations, routing, and execution

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
- `sandbox_network`: explicit operator-invoked mode requiring the exact confirmation value and local vaulted BR-30A credentials.

Running the repository runner in `sandbox_network` without the confirmation value remains blocked by safety gate. Automated tests and build phases use mocked transports only and do not call tastytrade.

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
- production-host rejection
- alternate-host rejection
- HTTP downgrade
- cross-host redirect
- write-method rejection
- order-path rejection
- websocket substitution
- timeout
- 401
- 403
- 429
- 5xx
- token leakage
- raw-account leakage

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

Explicit sandbox-network mode from the repository runner:

```powershell
python scripts/run_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py --mode sandbox_network --confirm I_CONFIRM_BR30B1_SANDBOX_READ_ONLY_NETWORK_SMOKE
```

Run tests:

```powershell
pytest tests/test_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py
```
