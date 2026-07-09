# Implementation Recommendations: New Brendan/Skool Modules

**Status:** RESEARCH_ONLY / PROPOSAL ONLY. This document proposes candidate
new roadmap phases based on `new_modules_gap_analysis.md`. **No code has been
written and no config files have been modified as part of this task.** Any
phase below would still need to be explicitly added to
`config/jarvis_brendan_master_plan.json` / `config/jarvis_master_plan_queue.json`
and implemented in a separate, reviewed step before it does anything.

All proposed phases, if ever implemented, must remain:
RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, with
LIVE TRADING: DISABLED, no broker routing/calls, no order execution, and no
credentials — consistent with BR-00's safety boundary.

---

## Recommended phases

### BR-10A — New Brendan Screeners & HMM Import Review *(justified)*

- **Why justified:** The task itself requires a durable, reviewable record of
  what was imported and why. This phase formalizes that as a roadmap entry
  rather than a one-off task artifact, so future BR-11/BR-12 work can point
  back to it.
- **Scope:** Documentation-only phase capturing the sanitized module summary
  and gap analysis (already produced by this task) as an official roadmap
  checkpoint. No new code.

### BR-10B — Track A Manual Screener Operator Workflow *(justified, docs-only)*

- **Why justified:** Track A's value is conceptual/operator discipline
  (universe design, filter families, regime-appropriate screening, "screen ≠
  signal," journaling), which is genuinely missing from the current BR-09
  dashboard/operator materials.
- **Scope:** A short operator playbook (Markdown) describing how a human
  reviewing the BR-09 dashboard should reason about candidate quality —
  liquidity floors, distinguishing filter, regime fit, and the rule that an
  empty candidate list is a valid, correct result. **No executable code** —
  this is a human-review-process document, not automation.
- **Explicitly not included:** the 84-prompt library or any chat-prompt
  automation.

### BR-10C — Track B Config-Driven Screener Pipeline *(justified)*

- **Why justified:** This is the clearest, highest-value, safely-scoped new
  capability: a deterministic, testable, config-driven screener that sits
  between BR-02 (candidate universe) and BR-03/BR-06 (scoring/risk gate),
  filling a real gap (no screener module exists in the repo today).
- **Scope:** A `screener/` module with: a config-first settings file, a small
  filter library (liquidity, price range, trend, momentum, proximity,
  volatility, volume-surge) each with unit tests on synthetic data, a ranking
  layer with configurable weights, named screen profiles as pure config, and
  a static Markdown/JSON (not live-serving HTML/JS) report output consistent
  with the rest of the repo's reporting style. No scheduler, no network
  alerting, no HTML/JS dashboard runtime — those are deferred (see "ignored"
  list) until a real need is demonstrated.
- **Safety:** Research-only, paper-only; explicitly must be able to return an
  empty candidate list; must not place or suggest live orders.

### BR-10D — Advanced HMM Tuning: Gating Stack & Per-Asset Profiles *(justified)*

- **Why justified:** `core/hmm_engine.py` already has BIC-based state
  selection and a flicker/stability mechanism, but no per-asset config
  profiles and no independently testable gating stack with before/after
  evaluation. This is a natural, safely-scoped extension of existing code
  rather than a new subsystem.
- **Scope:** A `core/hmm_gating.py`-style module (or equivalent) exposing
  confidence-threshold + persistence gating as configurable, testable units,
  plus a small per-asset profile config (e.g. crypto/equity/futures presets
  for window length, state count default, gating strictness) consumed by the
  existing engine. No confidence-scaled sizing (deferred — see "ignored").
  No VIX/external data integration yet (deferred to a later phase if a data
  source is actually available locally).

### BR-10E — HMM Regime Validation & Tuning Experiment Registry *(justified)*

- **Why justified:** The gap analysis identifies a concrete missing
  capability — there is no harness proving the HMM regime layer beats a naive
  baseline out-of-sample, and no log of tuning trials (needed for honest
  statistical claims). This directly extends the spirit of
  `core/experiment_registry.py` to HMM tuning specifically, and is a
  prerequisite the gap analysis flagged as wanted **before** BR-11/BR-12.
- **Scope:** A deterministic comparison harness (HMM-gated strategy vs. naive
  moving-average regime proxy vs. no-regime baseline) over local fixture
  data, plus an append-only tuning log recording what changed, the
  hypothesis, and the keep/revert decision. Detection-lag measurement can be
  included if time permits, but is not required for this phase to be useful.

### BR-10F — Screener-to-Paper-Autopilot Integration *(NOT currently justified — defer)*

- **Why NOT currently justified:** BR-10C (the screener itself) doesn't exist
  yet in this repo, and BR-10 (Paper Autopilot Loop) is already scoped around
  BR-02→BR-09. Wiring a not-yet-built screener into the existing autopilot
  loop is premature until BR-10C ships and is reviewed. Recommendation: build
  BR-10C first, get it reviewed, and only then decide whether a distinct
  integration phase is needed or whether BR-10 (Paper Autopilot Loop) simply
  gets updated in place.

---

## Explicitly deferred / not recommended right now

- **Live alerting integrations** (Discord/Telegram/email webhooks) — no
  credential handling should be added to this repo for a research-only
  screener; defer indefinitely unless a specific, reviewed need arises.
- **Parameter-pack community sharing format** — no current multi-user need in
  this single-operator repo.
- **Confidence-scaled position sizing for HMM regimes** — source material
  itself recommends starting with hard gating only; premature given no
  live-trading path exists.
- **Scheduled/always-on deployment (GitHub Actions or server loop) for the
  screener** — an operations concern, not a research capability; can be
  revisited once BR-10C exists and is validated.
- **External volatility index (VIX/funding-rate) integration** — deferred
  until a concrete local data source for such a series is confirmed
  available; do not add a new external data dependency speculatively.

---

## Summary table

| Phase | Title | Justified now? | Type |
|---|---|---|---|
| BR-10A | New Brendan Screeners & HMM Import Review | Yes | Docs only |
| BR-10B | Track A Manual Screener Operator Workflow | Yes | Docs only |
| BR-10C | Track B Config-Driven Screener Pipeline | Yes | Code + tests |
| BR-10D | Advanced HMM Tuning: Gating Stack & Per-Asset Profiles | Yes | Code + tests |
| BR-10E | HMM Regime Validation & Tuning Experiment Registry | Yes | Code + tests |
| BR-10F | Screener-to-Paper-Autopilot Integration | No — defer | Deferred |

This document does not modify `config/jarvis_brendan_master_plan.json` or
`config/jarvis_master_plan_queue.json`. Adding these phases to those files,
and implementing BR-10C/BR-10D/BR-10E, should happen in a follow-up step
after this recommendation is reviewed.
