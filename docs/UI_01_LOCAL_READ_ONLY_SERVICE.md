# UI-01 Local Read-Only Service and Event Backbone

UI-01 adds an optional local application-service layer for the UI-00 contract. It is not required by the quant engine, Python scripts, PowerShell automation, Cline, tests, or the existing Jarvis CLI.

Safety status:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- LIVE TRADING: DISABLED

The service binds only to `127.0.0.1` on an operator-selected or ephemeral local port. It does not make outbound network requests, does not load `.env`, Windows Credential Manager, keyring, OAuth values, API keys, broker credentials, provider tokens, account numbers, customer identifiers, unrestricted execution modules, order routing, or broker write modules.

## Endpoints

Versioned read-only endpoints live under `/api/v1`.

Unauthenticated:
- `GET /api/v1/health`
- `GET /api/v1/version`

Protected by a memory-only local session token:
- `GET /api/v1/safety`
- `GET /api/v1/data-status`
- `GET /api/v1/research`
- `GET /api/v1/screener`
- `GET /api/v1/opportunities`
- `GET /api/v1/analyst-theses`
- `GET /api/v1/market-regime`
- `GET /api/v1/lifecycle`
- `GET /api/v1/risk-gate`
- `GET /api/v1/portfolio`
- `GET /api/v1/alerts`
- `GET /api/v1/models`
- `GET /api/v1/performance`
- `GET /api/v1/backtests`
- `GET /api/v1/paper-activity`
- `GET /api/v1/options`
- `GET /api/v1/moonshot-research`
- `GET /api/v1/events`

Only `GET`, `HEAD`, and `OPTIONS` are application methods. `POST`, `PUT`, `PATCH`, `DELETE`, `CONNECT`, and `TRACE` return deterministic `405` responses.

Every JSON response uses `ui_contracts/ui01_response_envelope.schema.json` and includes `provider_validation_status=pending`, `is_live=false` in market-facing data, and `LIVE TRADING: DISABLED`.

## Source Modes

Default mode is `fixture`. `recorded_response` uses committed sanitized evidence artifacts only. `live_provider` remains unavailable and fails closed while BR-30 DXLink Quote/Candle validation is pending.

## Local Session Boundary

The local session token is generated or injected at runtime, held only in process memory, and compared with constant-time comparison. It must not be printed, logged, persisted, put in URLs, command-line arguments, environment variables, reports, or Git. Tests may inject deterministic fake local-session tokens.

## Operator Self-Test

Run the offline fixture self-test:

```powershell
python scripts/run_ui01_local_service_self_test.py
```

The self-test starts the service on `127.0.0.1` with an ephemeral port, checks health and protected read endpoints, subscribes to SSE, verifies replay, checks mutation methods return `405`, stops the service, verifies port release, and prints only a sanitized result envelope.
