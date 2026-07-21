# UI-02A Visual Contract

Jarvis UI-02A is a local, read-only command center over the UI-01 service. It is `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`, `HUMAN_REVIEW_REQUIRED`, and `BLOCKED_BY_SAFETY_GATE` where appropriate. `LIVE TRADING: DISABLED` remains the dominant global safety state.

## Shell Regions

- Top strip: Jarvis SVG emblem, `JARVIS QUANT` wordmark, connection state, source mode, provider validation, UTC time, local time, and one dominant `LIVE TRADING: DISABLED` badge.
- Left navigation rail: icon navigation for Overview, Research, Screener, Opportunities, Analyst Theses, Market Regime, Lifecycle, Risk Gate, Portfolio, Alerts, Models, Performance, Backtests, Paper Activity, Options, and Moonshot Research.
- Central workspace: routed read-only module content. Overview is the dense command-center layout. Other routes show a module header, truthful summary, unavailable or pending state, warnings when present, and collapsed Diagnostics.
- Right event rail: stream health and bounded event timeline with event icons, timestamps, source-mode labels, and safe details.
- Bottom strip: CLI independence, stream state, source mode, UTC time, local time, loopback environment, and `PAPER_ONLY` status.

## Design Tokens

Tokens are centralized in `ui02_desktop_shell/static/theme.css` and mirrored for deterministic checks in `ui02_desktop_shell/static/state.js`.

- Surfaces: near-black `#020611`, deep navy `#07111f`, panel `#0a1728`.
- Data accents: cyan `#2ee9ff`, electric blue `#2f8cff`.
- State accents: healthy green `#47d18c`, pending/review amber `#ffb547`, blocked red `#ff5b73`.
- Shape and layers: 8px panel radius, bounded panel borders, restrained illumination, scan-line texture, grid texture, visible focus ring, and explicit top/dialog z-index layers.

## Overview Hierarchy

Overview must render these interactive panels from UI-01 fixture or sanitized recorded-response envelopes only:

- Market Regime
- Risk Gate
- Opportunity Radar
- Portfolio and Exposure
- Wealth Engine
- Moonshot Engine
- Market / System Data chart frame or no-data state
- Signal-Strength Distribution
- Exposure Allocation
- Research State
- Data Source
- Provider Validation
- Local Service Health
- Human Review
- Event Stream
- Safe Mode
- Collapsed Overview Diagnostics

Missing values must render as unavailable, pending, stale, fixture, blocked, or no-data. UI-02A must not fabricate live prices, positions, returns, confidence values, market regimes, opportunities, provider readiness, or account state.

## Event-Stream States

The frontend state machine distinguishes:

- `connected`: current heartbeat and no known stream gap.
- `fixture_complete`: deterministic fixture stream ended after accepted fixture data; this is idle/complete, not failure.
- `reconnecting`: bounded retry after a non-fixture stream fault.
- `degraded`: accepted stream gap is present.
- `stale`: heartbeat age exceeded the stale threshold.
- `lost`: heartbeat age exceeded the lost threshold or the stream failed closed.

There may be at most one active `EventSource`. A replacement closes the old stream first. Reconnect delay is bounded exponential. Heartbeats that repeat the latest fixture sequence refresh heartbeat freshness without inflating duplicate-data counters. Duplicate, malformed, gap, and timeline storage are bounded in memory.

## Responsive Behavior

Wide desktop uses persistent top, left, center, right, and bottom regions. Standard laptops condense the left rail while retaining icon navigation. Narrow layouts stack regions vertically and keep panels within the viewport. Text must wrap inside containers without horizontal overflow, clipped timestamps, or unreadable identifier fragments.

## Phase Boundaries

UI-02A owns the visual system, Overview reconstruction, Diagnostics presentation, local SVG assets, and frontend SSE stability. UI-03 and UI-04 will add deeper route-specific workflows. UI-05 owns packaging or installer work. UI-02A must not change provider status, run external network requests, redesign authorization, touch broker code, add order routing, or enable live trading.
