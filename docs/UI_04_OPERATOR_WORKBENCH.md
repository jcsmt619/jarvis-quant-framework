# UI-04 Operator Workbench

UI-04 converts the remaining UI-02A placeholder routes into read-only operator workflows for Risk Gate, Portfolio, Alerts, Models, Performance, Backtests, Paper Activity, Options, and Moonshot Research.

Safety state:

- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- LIVE TRADING: DISABLED

UI-04 is offline and deterministic by default. It consumes only committed local fixtures and repository evidence through the UI-01 local read-only service and UI-02 desktop shell gateway. It does not contact Tastytrade, DXLink, a provider, a broker, an external API, or an external site.

## View-Model Boundary

The canonical fixture is `ui_contracts/fixtures/ui04_operator_workbench.fixture.json`.

Every UI-04 route receives a `data.ui04` view model that preserves:

- provenance
- source identifier
- source mode
- observation time
- generation time
- freshness
- validation state
- warnings and errors
- provider status
- `is_live=false`
- safety labels
- evidence links

Missing evidence must remain visible as unavailable, no-data, stale, partial-evidence, blocked, malformed, or human-review-required. UI-04 must not fabricate prices, positions, cash, P&L, returns, exposure, drawdown, Greeks, implied volatility, confidence, model health, backtest performance, fills, catalysts, scenario probabilities, or provider readiness.

## Routes

Risk Gate shows the deterministic blocked decision, blocked reasons, required labels, provider gate, data-freshness gate, model-validation gate, portfolio-risk gate, human-review requirement, evidence references, and why execution remains unavailable. It has no approve, reject, override, arm, route, submit, execute, or mutation controls.

Portfolio shows paper-only snapshot identity, freshness, redacted/safe position summaries, unavailable cash and exposure states when unsupported, concentration, drawdown, allocation, and strict Wealth Engine versus Moonshot Engine separation.

Alerts shows a read-only alert console with identifier, severity, category, state, creation time, freshness, source, related module or candidate, human-review requirement, and evidence details. Acknowledgement and dismissal mutations are absent.

Models shows model identity, family, version, validation state, drift state, evidence links, supported strategy families, last validation time, freshness, warnings, and promotion eligibility. Training, tuning, deployment, and configuration controls are absent.

Performance shows metric-set identity, benchmark, period, supported series only, drawdown, risk-adjusted values, win rate, trade count, rolling metrics, regime slices, and Wealth versus Moonshot separation. Unsupported performance stays no-data.

Backtests shows a read-only run registry with strategy family, symbols, date range, in-sample and out-of-sample state, walk-forward state, slippage assumptions, benchmark, drawdown, result label, overfit warning, insufficient-trade warning, promotion-gate state, and evidence references. The browser cannot launch backtest processes.

Paper Activity shows paper-run identity, review state, ledger references, proposed actions, simulated fills only when canonically available, rejected actions, safety-gate reasons, timestamps, freshness, and provenance. It cannot create, modify, approve, submit, cancel, or route orders.

Options shows chain-quality state, underlying, expiration, DTE, strike, call/put, bid/ask, Greeks, implied volatility, open interest, freshness, scenario context, warnings, and provenance only when supported. Missing option-chain data remains unavailable.

Moonshot Research is a research-only LEAPS and asymmetric-opportunity workbench. It shows candidate identity, underlying, thesis, strategy family, catalyst evidence, horizon, premium or maximum modeled loss, scenario outcomes, convexity/payoff evidence, implied-volatility context, theta/time-decay context, invalidation conditions, contradicting evidence, uncertainty, lifecycle state, risk state, and HUMAN_REVIEW_REQUIRED. Moonshot research and exposure are visually separate from the Wealth Engine.

## Operator Instructions

Run the deterministic self-test:

```powershell
python scripts/run_ui04_operator_workbench_self_test.py
```

Run focused tests:

```powershell
python -m pytest tests/test_ui04_operator_workbench.py tests/test_ui03_research_workbench.py
node tests/test_ui04_frontend_state.js
node tests/test_ui03_frontend_state.js
```

Start the shell locally:

```powershell
python scripts/run_ui02_desktop_shell.py --port 0 --no-open
```

Open only the printed loopback URL. The shell remains CLI-independent; UI availability is not required for engine operation.
