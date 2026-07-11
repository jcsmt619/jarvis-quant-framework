# UI-00 Jarvis Application Architecture Contract

Status: RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.

LIVE TRADING: DISABLED.

UI-00 defines the production architecture contract for a future interactive Jarvis desktop application. It is documentation, schemas, fixtures, and tests only. It does not create broker connectivity, external order routing, order submission, execution capability, state mutation, provider credential handling, or live trading.

## Safety Boundary

The Jarvis UI is an operator display and review surface. It must never become the only way to operate Jarvis. PowerShell on PC, Cline, Python scripts, tests, scheduled automation, audit tools, and the quant engine must remain independently operable when the UI is closed, crashed, failed, stale, or unavailable.

The UI must not store provider credentials, broker credentials, OAuth tokens, passwords, private keys, session secrets, or unrestricted execution handles. The UI must not directly import or call broker adapters, unrestricted execution functions, or live-trading toggles. Any trade-relevant analyst output displayed in the UI must be labeled HUMAN_REVIEW_REQUIRED.

Required disabled proof fields:

- `live_trading_enabled=false`
- `provider_credentials_stored_in_ui=false`
- `broker_credentials_stored_in_ui=false`
- `unrestricted_execution_access=false`
- `broker_order_call_performed=false`
- `external_order_routing_enabled=false`
- `state_mutation_enabled=false`
- `ui_required_for_engine_operation=false`

## Architecture Boundaries

`quant_engine` owns deterministic research, monitors, backtests, risk gates, paper drills, and analyst review artifacts. It remains runnable through CLI/scripts/tests without the UI.

`local_service_api` exposes versioned local API contracts. It reads canonical read models and accepts only explicitly permitted commands. UI-00 defines contracts only; it does not implement the service.

`event_stream` publishes append-only status events, audit events, research events, paper events, and safety-gate events with correlation IDs and monotonic sequence numbers.

`frontend` renders canonical read models, sends typed commands, subscribes to updates, shows failure states truthfully, and avoids direct filesystem, provider, broker, or execution access.

`desktop_shell` hosts the frontend, manages local window lifecycle, delegates auth to the local service, and must not contain credentials or execution logic.

## API Versioning

All API and event contracts are versioned under `v1`. Breaking schema changes require a new major version. Additive fields may be introduced only when clients can ignore unknown fields safely. Every payload includes `schema_version`, `contract_id`, `correlation_id`, and `created_at`.

## Canonical Read Models

Canonical read models are snapshots for display. They are not commands and must not mutate engine state.

- `system_health`: process status, heartbeat age, audit-ledger status, safety status.
- `data_status`: provider freshness, fixture freshness, gaps, stale-data flags.
- `research`: deterministic research runs, evidence packs, validation state.
- `screener`: candidates, filters, rankings, rejection reasons.
- `opportunities`: monitor-only or paper-only opportunity queue.
- `analyst_theses`: non-deterministic analyst memos labeled HUMAN_REVIEW_REQUIRED when trade-relevant.
- `market_regime`: regime labels, confidence, model provenance.
- `lifecycle`: candidate stage, review state, promotion gate state.
- `risk_gate`: current gate decision, blocked reasons, required labels.
- `portfolio`: read-only paper or imported snapshot state with redacted provenance.
- `alerts`: monitor alerts, acknowledgments, severity, stale status.
- `models`: model registry state, validation state, drift warnings.
- `performance_analytics`: metrics, drawdown, benchmark comparison, evidence links.
- `backtests`: run summaries, walk-forward results, slippage stress.
- `paper_activity`: paper drill status, paper fills, paper ledger references.
- `options`: options-chain quality, Greeks, DTE, IV, theta monitors.
- `moonshot_research`: Moonshot LEAPS research, risk review, target/stop flags for human review.

## Command Schemas

Commands are classified as `read_only` or `state_changing`.

Read-only commands may request snapshots, export reports, refresh local read models, or replay fixture streams. State-changing commands require authentication, role authorization, idempotency keys, correlation IDs, audit records, and explicit local-service approval. UI-00 permits only non-execution state changes such as acknowledging alerts or adding research annotations.

No command may create broker connectivity, submit an order, route an order, enable live trading, bypass a safety gate, or modify secrets.

## Event Schemas

Events are append-only records with:

- `event_id`
- `event_type`
- `schema_version`
- `sequence`
- `correlation_id`
- `causation_id`
- `created_at`
- `source_boundary`
- `label`
- `safety`
- `payload`

The event stream must support snapshot-then-subscribe behavior. Clients first load canonical read models through the API, then subscribe from the latest acknowledged sequence. Duplicate events are ignored by `event_id`.

## WebSocket-Style Updates

The planned update channel is local-only and WebSocket-style. It carries `hello`, `snapshot_available`, `read_model_updated`, `command_accepted`, `command_rejected`, `audit_record_appended`, `heartbeat`, `disconnect_notice`, and `resync_required`.

Reconnect behavior:

- Resume from `last_seen_sequence` when available.
- Request a full snapshot when the sequence is expired, missing, or inconsistent.
- Mark displays `STALE` when heartbeat age exceeds the contract threshold.
- Never hide uncertainty. Unknown, stale, degraded, disconnected, and blocked states must be visibly distinct.

## Authentication And Roles

The desktop shell delegates authentication to the local service. The frontend receives short-lived local UI sessions only and never receives provider or broker credentials.

Roles:

- `viewer`: read canonical read models and subscribe to events.
- `researcher`: viewer permissions plus create research annotations and request read-only exports.
- `operator`: researcher permissions plus acknowledge alerts and request paper-only drills through approved local-service commands.
- `auditor`: viewer permissions plus audit-log export and integrity checks.
- `admin`: local service configuration review only; cannot enable live trading through the UI.

## Audit, Correlation, And Idempotency

Every command must include `correlation_id` and `idempotency_key`. Every accepted or rejected command writes an audit record. Audit records include actor, role, command type, command classification, previous state hash when applicable, result, safety label, failure state, and disabled live-trading proof.

Repeated state-changing commands with the same idempotency key must return the original result or be rejected as a conflict. Read-only commands may use correlation IDs for traceability but must not create mutable state except optional audit records.

## Failure States

Required failure states:

- `DISCONNECTED`
- `STALE`
- `DEGRADED`
- `AUTH_REQUIRED`
- `FORBIDDEN`
- `COMMAND_REJECTED`
- `IDEMPOTENCY_CONFLICT`
- `SCHEMA_VERSION_UNSUPPORTED`
- `SAFETY_GATE_BLOCKED`
- `RESYNC_REQUIRED`
- `READ_MODEL_UNAVAILABLE`

Failure states must be legible and truthful. The UI must not imply a green or approved status when data is stale, degraded, unknown, blocked, or human-review-required.

## Design Direction

The visual direction is a futuristic dark holographic HUD using deep navy/black surfaces, electric blue structure, and amber attention states. The style must remain legible, truthful, keyboard-accessible, screen-reader-friendly, and color-blind-aware. Amber and blue effects are accents, not substitutes for text, icons, timestamps, severity labels, or explicit safety states.

Status displays must show actual state, freshness, provenance, and safety labels. Decorative effects must not obscure text, compress tables, hide blocked states, or make simulated/paper data look live-executable.

## UI-00 Deliverables

The canonical UI-00 machine-readable artifacts are:

- `ui_contracts/ui00_application_architecture_contract.schema.json`
- `ui_contracts/fixtures/ui00_application_architecture_contract.fixture.json`

These artifacts are contract fixtures for future implementation work. They are not runtime service code.
