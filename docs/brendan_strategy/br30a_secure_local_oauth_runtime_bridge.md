# BR-30A / BR-30A1 Secure Local OAuth Runtime Bridge

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30A defines a provider-neutral runtime credential interface for short-lived OAuth access tokens.

The initial provider profile is tastytrade sandbox only. The bridge is offline and fail-closed by default. It does not call the provider unless a caller injects an explicit token client at runtime, and automated tests use mocked vault and token clients only.

BR-30A1 adds the Sandbox OAuth Capability Firewall. It distinguishes:

- Jarvis-requested OAuth scopes
- provider-granted OAuth scopes
- Jarvis-effective runtime capabilities

The exposed credentials are sandbox-only and must never be reused for production.

## Credential Storage

Runtime credentials are stored in the local operating-system credential vault through Python `keyring`. On Windows this is intended to use Windows Credential Manager through the installed keyring backend.

The interactive setup utility is:

```powershell
python scripts/setup_br30a_secure_local_oauth_runtime_bridge.py
```

The utility prompts for:

- OAuth client identifier
- replacement OAuth client secret
- OAuth refresh token

Client secret and refresh token input is collected with `getpass` and is not echoed. Secret values must not be passed as command-line arguments and must not be written to `.env`, source files, test fixtures, reports, logs, Git history, UI state, exception messages, or process output.

## OAuth Scope Policy

Jarvis-requested OAuth scopes are exactly:

- `openid`
- `read`

A caller cannot request `trade` capability. Unexpected Jarvis-requested write-capable scopes are rejected by the runtime bridge.

For tastytrade sandbox only, the provider-granted token response may include:

- `openid`
- `read`
- `trade`

The provider-granted sandbox `trade` scope is reported as `provider_scope_contains_trade=true` when present, but it does not become a Jarvis-effective capability. Effective Jarvis capabilities remain read-only.

Unknown provider-granted scopes are rejected. Provider-granted `trade` is accepted only when the provider is `tastytrade`, the environment is `sandbox`, and all Jarvis-effective order, mutation, execution, external routing, and live-trading capabilities are false.

## Provider Resource Firewall

BR-30A1 adds a strict read-only HTTP method and endpoint allowlist for the later BR-30B sandbox smoke test.

Allowed provider-resource methods are:

- `GET`

POST, PUT, PATCH, and DELETE provider-resource operations are blocked, except for the isolated OAuth token refresh exchange on the configured token endpoint. The token refresh exchange is not a provider-resource operation and must not expose order, mutation, routing, execution, or live-trading capability.

Allowed sandbox hosts are:

- `api.cert.tastyworks.com`

Allowed token exchange endpoint:

- `POST https://api.cert.tastyworks.com/oauth/token`

Allowed read-only provider-resource endpoints:

- `GET https://api.cert.tastyworks.com/customers/me/accounts`
- `GET https://api.cert.tastyworks.com/api-quote-tokens`

Production hosts are rejected. Unknown endpoints are rejected. Mutation paths containing order, position, transfer, deposit, withdrawal, ACH, wire, or transaction markers are rejected even for read methods.

## Runtime Boundaries

BR-30A keeps access tokens in process memory only.
BR-30A rejects missing secrets.
BR-30A rejects wrong environments.
BR-30A rejects malformed token responses.
BR-30A rejects expired tokens.
BR-30A rejects clock-skewed near-expiry tokens.
BR-30A supports revocation by clearing in-memory token state.
BR-30A blocks when the credential vault is unavailable.

## Safety Boundaries

BR-30A does not touch `.env`.
BR-30A does not print, persist, log, fixture, or report secret values.
BR-30A does not expose account mutation.
BR-30A does not expose execution methods.
BR-30A does not expose external routing.
BR-30A does not expose position mutation.
BR-30A does not authorize live trading.
BR-30A does not submit broker orders.
BR-30A does not add broker order routing.

BR-30A1 reports these effective capabilities as false:

- order-read
- order-create
- order-replace
- order-cancel
- account mutation
- position mutation
- execution
- external routing
- live trading

BR-30A1 does not import or expose execution or order-management modules.

## Required Disabled State

- real_paper_wrapper_connected=false
- real_paper_wrapper_attempted=false
- real_paper_order_submitted=false
- broker_order_call_performed=false
- live_trading_enabled=false
- LIVE TRADING: DISABLED

## Tests

Run:

```powershell
pytest tests/test_br30a_secure_local_oauth_runtime_bridge.py
```

The tests use redacted values and mocked vault/token clients only. They do not call tastytrade or any external provider.
