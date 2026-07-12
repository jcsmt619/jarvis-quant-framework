# BR-30A Secure Local OAuth Runtime Bridge

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE

LIVE TRADING: DISABLED

## Purpose

BR-30A defines a provider-neutral runtime credential interface for short-lived OAuth access tokens.

The initial provider profile is tastytrade sandbox only. The bridge is offline and fail-closed by default. It does not call the provider unless a caller injects an explicit token client at runtime, and automated tests use mocked vault and token clients only.

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

Allowed OAuth scopes are exactly:

- `openid`
- `read`

Unexpected write-capable scopes are rejected by the runtime bridge.

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
