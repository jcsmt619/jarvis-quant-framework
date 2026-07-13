# BR-30B Tastytrade Sandbox Read Only Connectivity Smoke Test

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30B defines the tastytrade sandbox read-only connectivity smoke test. BR-30B1 adds the concrete tastytrade sandbox read-only network client and operator smoke runner. BR-30B2 aligns the sandbox OAuth refresh exchange with the official tastytrade SDK token request contract. BR-30B3 aligns the read-only REST response parsers for customer accounts and API quote tokens. BR-30B4 replaces the earlier handwritten generic WebSocket market-data messages with a repository-owned Node 20+ DXLink sidecar that follows the official `@dxfeed/dxlink-api` SDK pattern used by tastytrade.

Default execution is fixture-only/offline and fail closed. The separate `sandbox_network` mode is explicit operator-invoked only and requires both `--mode sandbox_network` and the exact confirmation value `I_CONFIRM_BR30B1_SANDBOX_READ_ONLY_NETWORK_SMOKE`.

The smoke test is evidence-only. It is intended to prove that a local vaulted refresh token can be exchanged for a short-lived memory-only access token, that only `openid` and `read` are requested by Jarvis, that a provider-granted sandbox `trade` scope remains raw provider metadata with no effective Jarvis trade capability, that a minimal customer/account discovery request can be redacted, that a sandbox quote token can be obtained, and that delayed sandbox market data for approved symbols `SPY` and `QQQ` can be normalized through the BR-30 and BR-26 contracts.

## BR-30B1 Network Allowlist

The only approved REST origin is:

- `https://api.cert.tastyworks.com`

The unverified `api.cert.tastytrade.com` host, production hosts, HTTP downgrade, cross-host redirects, arbitrary caller-supplied URLs, and redirects to non-approved origins are rejected.

The only approved POST is:

- `POST /oauth/token`

## BR-30B2 OAuth Token Contract

The isolated OAuth refresh POST to `https://api.cert.tastyworks.com/oauth/token` sends a JSON body with exactly these keys:

- `grant_type`
- `refresh_token`
- `client_secret`
- `scope`

`grant_type` is always `refresh_token`. `scope` is the Jarvis-requested scope tuple joined with one ASCII space, currently `openid read`. The token request sends `Content-Type: application/json`, `Accept: application/json`, and the approved Jarvis User-Agent. It does not send `client_id`, query-string credentials, URL credentials, command-line credentials, or credential-bearing request evidence.

The successful token response parser reads only `access_token`, `expires_in`, `token_type`, and optional `scope`. If `scope` is absent, Jarvis retains only the requested `openid` and `read` scope set. If the provider reports `openid read trade`, Jarvis preserves `provider_scope_contains_trade=true` as provider metadata while trade, order, routing, execution, mutation, and live-trading capabilities remain false.

OAuth error handling classifies 400, 401, 403, 429, and 5xx responses into sanitized failure reasons without persisting or printing the provider response body.

After authentication, the only approved REST reads are:

- `GET /customers/me/accounts`
- `GET /api-quote-tokens`

The concrete client does not represent or expose order, position, transaction, balance mutation, watchlist mutation, account mutation, or order-management endpoints.

## BR-30B3 REST Response Contract

The customer account parser accepts the provider `data` wrapper and account records whose account number is nested under `account.account-number`. It also preserves direct documented account-number variants when they are present. Raw customer IDs and account numbers are extracted only in process memory; reports and Markdown evidence write deterministic redacted fingerprints only.

The API quote-token parser accepts canonical `token` and `dxlink-url` fields from either the top-level object or its `data` wrapper. Optional `level` is treated as non-secret metadata. The API quote token and access token remain memory-only. The full DXLink URL is not persisted, printed, hashed, or written to evidence. The websocket endpoint must come from the authenticated `/api-quote-tokens` response, must use `wss://`, and cannot be supplied or substituted by the caller. HTTP, HTTPS, WS, missing endpoints, malformed wrappers, missing token values, and unexpected container types fail closed.

Malformed account payloads use the sanitized `account_payload_malformed` rejection reason. Malformed quote-token payloads use the sanitized `quote_token_payload_malformed` rejection reason. These stage-specific reasons prevent account diagnostics and quote-token diagnostics from collapsing into the generic `malformed_payload` result.

## BR-30B4A DXLink SDK Contract Correction And Runtime Preflight

The DXLink adapter lives under `integrations/tastytrade_dxlink`. Its dependency is pinned exactly to `@dxfeed/dxlink-api` `0.3.0` in both `package.json` and `package-lock.json`; floating `latest` dependencies are not allowed. The sidecar requires Node 20 or newer.

The Python runtime resolves `node.exe`/`node` to an absolute executable path, launches the sidecar with fixed argv and `shell=False`, and supplies only an allowlisted non-secret Windows/TLS child environment. Broker, OAuth, token, credential, API-key, account, and customer variables are excluded. The quote token and full provider-returned WSS endpoint are never passed through command-line arguments, environment variables, temporary files, reports, fixtures, logs, process titles, exceptions, or Git history. The child receives one bounded JSON document on stdin containing only:

- ephemeral quote token
- provider-returned DXLink WSS endpoint
- approved symbols `SPY` and `QQQ`
- acquisition timestamp
- bounded timeout

The sidecar never receives OAuth client ID, client secret, refresh token, account number, customer ID, REST access token, or arbitrary event subscriptions.

The sidecar follows the checked-in SDK `0.3.0` contract before any real DXLink connection:

- construct the client with `new DXLinkWebSocketClient()`
- call `client.connect(dxlinkUrl)` with the authenticated provider-returned WSS endpoint
- call `client.setAuthToken(quoteToken)`
- construct the feed with `new DXLinkFeed(client, FeedContract.AUTO)`
- configure separately with `feed.configure`, `acceptAggregationPeriod`, `FeedDataFormat.COMPACT`, and `acceptEventFields`
- add subscriptions as individual objects with `type` and singular `symbol`
- subscribe to Quote symbols `SPY` and `QQQ`
- subscribe to one-minute Candle symbols `SPY{=1m}` and `QQQ{=1m}`
- register data with `feed.addEventListener(listener)` using one listener argument
- treat the listener callback as a bounded iterable event batch

Subscription objects must not contain plural `symbols` or subscription-level `fields`. The sidecar subscribes only to Quote and one-minute Candle data for exactly `SPY` and `QQQ`. It does not subscribe to Trade, Greeks, Summary, Profile, Underlying, Order, account-streaming, or arbitrary event types. Compact fields are limited to normalized event symbol, timestamps, bid price, ask price, open, high, low, close, and volume.

## BR-30B4B DXLink Runtime Preflight Package Metadata

`dxlink_runtime_preflight.mjs` is a local no-credential preflight. It resolves the installed SDK entry with `import.meta.resolve("@dxfeed/dxlink-api")`, converts the file URL with `fileURLToPath`, and performs a bounded upward filesystem search for the physical package manifest under `node_modules/@dxfeed/dxlink-api`. It does not import or require the unexported `@dxfeed/dxlink-api/package.json` subpath.

The preflight accepts only a manifest whose `name` is exactly `@dxfeed/dxlink-api` and whose `version` is exactly `0.3.0`. Missing, malformed, ambiguous, escaped, symlinked, wrong-name, or wrong-version metadata fails closed with sanitized stderr. The preflight verifies `DXLinkWebSocketClient`, `DXLinkFeed`, `FeedContract.AUTO`, `FeedDataFormat.COMPACT`, `connect`, `setAuthToken`, `configure`, `addSubscriptions`, and `addEventListener` without accepting credentials and without calling `connect` or `setAuthToken`.

Successful stdout is exactly one bounded JSON object with `ok=true`, `sdk="@dxfeed/dxlink-api"`, `contract="0.3.0"`, `connection_attempted=false`, and `credentials_accepted=false`.

## BR-30B4C Windows Node Runtime Environment Boundary

BR-30B4C corrects the Python-to-Node subprocess environment boundary for Windows Node runtimes. The parent still resolves `node.exe`/`node` to an absolute executable path, uses fixed argv, and launches with `shell=False`. It never inherits the full parent environment.

The child environment is an explicit case-insensitive Windows runtime allowlist containing ordinary non-secret operating-system variables only. `SSL_CERT_DIR` and `SSL_CERT_FILE` are retained only when already present. `NODE_NO_WARNINGS` is injected with the fixed value `1`; inherited `NODE_NO_WARNINGS` is ignored. Environment-name matching is case-insensitive, the original safe source name is preserved, and duplicate case-folded names such as `Path` plus `PATH` fail closed with `dxlink_runtime_environment_unavailable`.

Broker, OAuth, token, credential, API-key, account, customer, password, private-key, tastytrade, and secret-bearing names are denied. `NODE_OPTIONS`, `NODE_PATH`, `NODE_EXTRA_CA_CERTS`, `NODE_DEBUG`, and `SSLKEYLOGFILE` are explicitly rejected as Node injection/debugging variables even if they are accidentally added later. The child environment is not a credential transport; quote tokens and provider-returned WSS endpoints remain stdin-only and memory-only.

The repository-owned local preflight runner invokes `dxlink_runtime_preflight.mjs` through the exact production environment builder, absolute Node argv, `shell=False`, empty stdin, hard timeout, bounded stdout/stderr, and allowlisted sanitized error codes. It does not load the vault, accept credentials, call `connect`, call `setAuthToken`, or contact tastytrade or DXLink.

The sidecar stdout is a bounded machine-readable result envelope containing normalized non-secret event fields only. Stderr is restricted to allowlisted sanitized status codes. Raw DXLink protocol messages, authentication states, provider payloads, quote tokens, full WSS URLs, and SDK diagnostics must never be written or printed.

The Python parent enforces stdout and stderr size limits, hard timeout, approved-symbol validation, event-type validation, finite numeric validation, duplicate detection, timestamp parsing, 15-minute sandbox-delay classification, malformed output rejection, secret-leak detection, and deterministic process cleanup. The DXLink client is closed after each bounded sample. No orphan Node process may remain.

Stage-specific DXLink rejection reasons:

- `dxlink_dependency_unavailable`
- `dxlink_package_metadata_unavailable`
- `dxlink_contract_mismatch`
- `dxlink_authentication_failed`
- `dxlink_subscription_failed`
- `dxlink_timeout`
- `dxlink_process_failed`
- `dxlink_runtime_environment_unavailable`
- `dxlink_output_malformed`
- `dxlink_secret_leak_detected`

The bounded stream subscribes only to `SPY` and `QQQ`, collects a small delayed sandbox sample, then closes. Strict connect, read, and overall timeouts prevent long-running streams.

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
- account payload malformed
- quote-token payload malformed
- missing symbol
- redaction
- nested `account.account-number` parsing
- direct account-number fallbacks
- quote-token `data` wrappers
- top-level quote-token responses
- canonical `token` and `dxlink-url` parsing
- missing quote-token fields
- wrong DXLink schemes
- substituted DXLink URLs
- fixed DXLink child-process argv
- stdin-only quote-token and endpoint transport
- absence of secrets from argv and environment
- exact SPY and QQQ DXLink allowlist
- Quote and Candle subscription source configuration
- compact field configuration
- successful Quote and Candle normalization
- missing candle rejection
- unsupported event rejection
- malformed sidecar output
- oversized sidecar output
- sidecar timeout
- sidecar crash
- explicit Windows runtime child environment allowlist
- case-insensitive `Path`/`PATH` and `SystemRoot`/`SYSTEMROOT` handling
- duplicate case-folded environment-name rejection
- Node injection/debugging environment-variable blocking
- fixed `NODE_NO_WARNINGS=1`
- local runtime preflight subprocess contract
- cleanup boundary evidence
- raw-message blocking
- sidecar secret-leak detection
- exact OAuth JSON body key set
- exact OAuth JSON headers
- omitted OAuth `client_id`
- absent OAuth scope fallback
- provider-granted trade-scope isolation
- sanitized 400 OAuth error behavior
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

Credential-free local DXLink runtime preflight:

```powershell
python scripts/run_br30b4c_dxlink_runtime_preflight.py
```

Run tests:

```powershell
pytest tests/test_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py
```
