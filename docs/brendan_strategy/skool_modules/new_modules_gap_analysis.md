# Gap Analysis: New Brendan/Skool Modules vs. BR-00 → BR-10

**Status:** RESEARCH_ONLY. This analysis compares the paraphrased concepts in
`new_screeners_hmm_module_summary.md` against the existing Jarvis/Brendan
roadmap (`docs/brendan_strategy/jarvis_brendan_architecture_review.md`, BR-00,
and `config/jarvis_brendan_master_plan.json`, BR-01 → BR-12). No code or config
changes are made by this document.

Current roadmap recap (BR-00 → BR-10):

| Phase | Title | Focus |
|---|---|---|
| BR-00 | Architecture Review | Six-layer target system, safety boundary |
| BR-01 | Options LEAPS Data Model | Data models/fixtures |
| BR-02 | Candidate Universe Builder | Deterministic watchlists from fixtures + filters |
| BR-03 | Options Chain Quality Scanner | Chain quality scoring |
| BR-04 | Greeks/IV/Spread/DTE Scoring | Options scoring |
| BR-05 | LLM Analyst Thesis Generator | Analyst prompt packaging |
| BR-06 | Deterministic Trade Score Risk Gate | Gate decision |
| BR-07 | Paper Options Portfolio Manager | Paper simulation |
| BR-08 | Daily Position Monitor / Alert Engine | Paper alerts |
| BR-09 | Local Operator Dashboard | Read-only dashboard |
| BR-10 | Paper Autopilot Loop | Orchestrates BR-02→BR-09 as one local workflow |

Repo grounding checked directly:
- `core/hmm_engine.py` implements a Gaussian HMM with BIC-based state-count
  selection (k∈{3..7}), forward-filtered (non-look-ahead) inference, and a
  flicker/stability confirmation window — but **no** per-asset config
  profiles, **no** persistence+confidence gating exposed as a configurable
  stack, **no** external volatility (VIX-style) feature/circuit-breaker, and
  **no** retraining/drift-detection scheduler.
- No `candidate_universe`, `screener`, or `screening` module exists yet in
  `core/`, `analysis/`, or elsewhere — BR-02 (Candidate Universe Builder) is
  on the roadmap but not yet implemented in this repo.
- No walk-forward / regime-validation harness comparing HMM vs. naive
  baseline was found in the codebase.

---

## 1. What new concepts are not already in BR-00 → BR-10?

- **Config-first "settings.yaml" pattern** for screener parameters (universe,
  thresholds, weights, schedule) as a single edit point — BR-02's spec
  mentions "configurable filters" but does not specify this config-file-only
  architecture pattern explicitly.
- **Named, config-only "screen profiles"** running many screens from one
  engine (momentum/pullback/breakout as pure config variants) — not present
  in any BR phase.
- **Point-in-time filter hygiene as a first-class, tested requirement** inside
  a screener engine (each filter unit-tested against synthetic data) — BR-02
  doesn't call this out explicitly.
- **"What-changed since last run" diffing** in a dashboard (new/dropped
  names, rank moves) — not present in BR-09's dashboard spec.
- **Parameter packs** (shareable screen-profile config files with an
  author/description/market header) — a community-sharing pattern with no
  BR-phase analog.
- **HMM per-asset tuning profiles** (crypto/equity/futures dial presets) —
  not present anywhere in the current roadmap or `hmm_engine.py`.
- **Explicit HMM signal-gating stack** (confidence threshold + persistence
  bars, optionally confidence-scaled sizing) as a distinct, testable,
  configurable layer between the HMM and a strategy router — the engine has
  a flicker/stability mechanism but it is fixed-parameter, not exposed as a
  tunable/tested gating module, and there's no confidence-scaled sizing mode.
- **External volatility integration (VIX/funding-rate/MOVE)** as both a
  feature and an independent circuit-breaker override — entirely new.
- **Retraining scheduler with drift detection**, and the explicit rule that
  live retraining schedule must match the walk-forward-simulated schedule —
  entirely new; no retraining logic exists in `hmm_engine.py` today.
- **Regime validation harness**: HMM vs. naive MA filter vs. no-regime
  baseline, scored out-of-sample — entirely new; no such harness exists yet.
- **Detection-lag measurement** (bars-late at known historical turns, costed
  in price terms) — entirely new.
- **A tuning experiment log** tied to trial-count discipline (for
  deflated-Sharpe-style honesty about how many things were tried) — related
  in spirit to `core/experiment_registry.py` but not HMM-tuning-specific.

## 2. Which parts improve the candidate universe builder (BR-02)?

- The Track B screener's **config-first, single-settings-file** pattern is a
  direct, low-risk upgrade for BR-02: instead of ad hoc "configurable
  filters," BR-02 could formalize one `universe_settings.yaml` (or JSON) that
  defines universe membership rules, liquidity floors, exclusions, and
  catalyst tags, with the builder code reading only from that file.
- The **filter-family taxonomy** (liquidity/floor, trend, momentum,
  setup/proximity, volatility, quality, event/calendar) gives BR-02 a
  principled structure for its "sector, liquidity, price trend, volatility,
  catalyst tags, market cap bucket, options availability" filters that are
  already in its spec — it's a naming/organizing improvement, not new scope.
- The **"universe is itself a filter, refresh it periodically"** framing is a
  useful operating note for BR-02's Markdown/JSON reports (e.g., record when
  the universe was last refreshed and why membership changed).

## 3. Which parts improve stock/crypto screening?

- Everything in module 2 (Track B Automated Screener) is directly about
  screening and would sit **downstream of BR-02** and **upstream of BR-03/
  BR-04**: it proposes a deterministic filter → rank → dashboard → alert
  pipeline that could consume BR-02's candidate universe output as its input
  universe.
- The **filter-as-tested-unit** pattern (each filter has its own unit test on
  synthetic data) is a concrete, safe engineering practice that should be
  adopted for any new screener code, matching the repo's existing testing
  culture (`tests/`).
- The **"empty list is a valid, correct output"** principle reinforces
  existing BR-06 risk-gate philosophy (never pad weak results) and should be
  explicitly carried into any new screener module's tests.

## 4. Which parts improve HMM tuning / regime detection?

- All of module 3 (Advanced HMM Tuning) is squarely about improving
  `core/hmm_engine.py` and any regime-based strategy routing:
  - State-count selection already exists (BIC over k∈{3..7}) — the new
    concept is adding the **"economic meaning" / nameability check** as an
    explicit, recorded step, not just picking BIC's argmin.
  - **Per-asset profiles** are a genuinely new configuration layer.
  - **Gating stack (confidence + persistence)** overlaps with the existing
    flicker/stability confirmation logic in `hmm_engine.py`
    (`stability_bars`, `flicker_window`, `flicker_threshold`,
    `min_confidence`) but the module's framing of it as a *separate,
    testable, per-asset-configurable* layer with an explicit before/after
    evaluation (switch counts, transaction-cost impact) is a real
    improvement over the current fixed-constructor-argument approach.
  - **VIX/vol-index integration and retraining/drift scheduling** are wholly
    new capabilities not present in the current engine.
  - **Regime validation harness and detection-lag measurement** would give
    the existing HMM engine the same walk-forward-style proof-of-value
    treatment that BR-06's risk gate philosophy already expects of trading
    decisions generally.

## 5. Which parts affect Track A vs. Track B?

- **Track A (chat screening)** is judgment-based, non-deterministic, and
  explicitly *not* meant to be automated as-is. Its main transferable value to
  Jarvis is the **conceptual discipline** (universe design, filter families,
  regime-appropriate screen selection, "screen ≠ signal," journal-based
  tuning) rather than any code to implement. It maps to *how a human operator
  reviews BR-09's dashboard*, not to new automated modules.
- **Track B (automated screener + advanced HMM tuning)** is code-oriented and
  directly implementable as deterministic, testable Python — this is where
  new BR-10x phases would live if justified.
- Practical implication: Track A content should be captured as **operator
  guidance / dashboard-review discipline** (e.g., an addendum to BR-09's
  operator workflow), while Track B content should be evaluated for **new
  BR-10x implementation phases**.

## 6. Which parts should be added before BR-11/BR-12?

BR-11/BR-12 are about *read-only broker sync design* and *human-approved
execution safety design* — i.e., the boundary before any future live-trading
track. Before reaching that boundary, it makes sense to strengthen the
research/paper pipeline that feeds BR-11/BR-12, specifically:

- A **config-driven automated screener** (Track B pattern) sitting between
  BR-02 (universe) and BR-06 (risk gate) would give the paper autopilot loop
  (BR-10) a deterministic, testable, explainable candidate-narrowing stage
  that today's roadmap only implies rather than specifies precisely.
- **HMM gating-stack formalization + regime validation harness** should land
  before BR-11/BR-12 because any future execution-safety design (BR-12)
  will want to reason about regime-based sizing/stand-down behavior, and that
  requires the regime detector to already be validated and gated safely.
- A **tuning/experiment log** for HMM changes complements the existing
  `core/experiment_registry.py` philosophy and should exist before any
  regime-aware sizing logic is trusted operationally.

These are exactly the kind of "before BR-11/BR-12" additions the task asked
about, and they are the basis for the BR-10x phase proposals in
`implementation_recommendations.md`.

## 7. Which parts should be ignored for safety or redundancy?

- **The full 84-prompt Track A library and its exact prompt text** — ignored;
  copying it would risk both a safety/IP issue (paid content verbatim) and
  redundancy (it's a chat-usage guide, not code).
- **Alert delivery integrations (Discord/Telegram/email)** — the *pattern*
  (secrets in env vars, never in config) is worth keeping as a safety note,
  but wiring actual third-party notification credentials is out of scope for
  a research-only/local-only repo and should not be implemented now.
- **"Parameter pack" community sharing mechanics** — interesting but not
  needed for a single-operator local repo; redundant with existing
  `config/` JSON patterns already used for phases/queues. Can be revisited
  later if genuinely needed.
- **Confidence-scaled position sizing** — explicitly described in the source
  material itself as "start with hard gates, graduate later." Given this repo
  has no live-trading path, implementing sizing logic now is premature;
  hard-gate-only logic is sufficient and safer to reason about.
- **GitHub Actions / always-on server deployment for scheduled screener
  runs** — deployment/ops concern, not a research-safety concern, and out of
  scope for this import task; can be revisited when/if a screener phase is
  actually implemented and needs a runner.
- Nothing in any of the three modules proposes live trading, broker order
  placement, or credential handling — no content needed to be rejected on
  those specific safety grounds, but the analysis above still explicitly
  avoids importing anything that would create such capability.
