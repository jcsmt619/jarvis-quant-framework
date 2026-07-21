# UI-03 Research Intelligence Workbench

UI-03 converts the UI-02A placeholder research routes into read-only research workflows:

- Research
- Screener
- Opportunities
- Analyst Theses
- Market Regime
- Lifecycle

The phase remains `RESEARCH_ONLY`, `MONITOR_ONLY`, `PAPER_ONLY`, and `HUMAN_REVIEW_REQUIRED`. `LIVE TRADING: DISABLED` is permanent in this UI phase.

## Safety Boundary

UI-03 does not contact Tastytrade, DXLink, a broker, a remote API, or an external website. It consumes only UI-01 envelopes and the committed fixture at:

`ui_contracts/fixtures/ui03_research_workbench.fixture.json`

The gateway remains loopback-only on `127.0.0.1`, uses an isolated local session token server-side, rejects mutation methods, and serves local static assets under the restrictive UI-02A CSP. The UI does not use `localStorage`, `sessionStorage`, IndexedDB, cookies, service workers, telemetry, analytics, CDNs, remote fonts, or remote images.

## View Model

The UI-03 view model is exposed inside existing UI-01 response envelopes at `data.ui03`. It preserves:

- source identifiers and evidence paths
- observation time and generation time
- freshness and validation state
- warnings and unavailable states
- source mode and provider validation status
- `is_live=false`
- `LIVE TRADING: DISABLED`
- human-review and safety labels

Missing evidence renders as `unavailable`, `stale`, `partial-evidence`, `blocked`, or `HUMAN_REVIEW_REQUIRED`. Confidence values are shown only when present in the committed source. Otherwise they render as `unavailable`.

## Route Behavior

Research shows the selected offline research run, provenance, freshness, supporting and contradicting evidence, unresolved questions, warnings, and human-review requirements.

Screener shows a compact candidate table with in-memory search, sorting, filtering, and column controls. Filters are not persisted and do not modify backend state.

Opportunities is a review queue. It explains why a candidate was surfaced, why it may be withheld, evidence references, risk and lifecycle states, and the required human action.

Analyst Theses shows thesis cards linked to candidates. Thesis uncertainty, invalidation conditions, provenance, freshness, and `HUMAN_REVIEW_REQUIRED` status remain explicit.

Market Regime renders an explicit unavailable state because no committed UI-03 market-regime evidence is present.

Lifecycle shows stage counts, allowed transitions, evidence requirements, unresolved blockers, promotion-gate state, human-review state, duplicate state, stale state, and a read-only funnel.

Candidate selection is synchronized in memory across Screener, Opportunities, Analyst Theses, and Lifecycle for the current browser session only. It is never written to browser storage, files, reports, or external systems.

## Operator Instructions

Run the shell in fixture mode:

```powershell
python scripts/run_ui02_desktop_shell.py --source-mode fixture --no-open
```

Open the printed loopback URL in a browser. Use the six UI-03 routes from the left navigation. The Refresh button only re-reads approved local endpoints and may emit bounded local read-only refresh events through the existing event backbone.

Do not treat any UI-03 candidate, thesis, score, lifecycle state, or opportunity label as a trade instruction. The UI contains no approval, broker, order routing, credential, live execution, or state-change controls.

## Verification

Run:

```powershell
python scripts/run_ui03_research_workbench_self_test.py
node tests/test_ui03_frontend_state.js
python -m pytest tests/test_ui03_research_workbench.py
```

The self-test starts UI-01 and the shell on ephemeral loopback ports, verifies all six routes and Overview integrations, checks SSE behavior, safety headers, token isolation, unsupported methods, provider pending status, `is_live=false`, `LIVE TRADING: DISABLED`, and confirms port release/thread cleanup.
