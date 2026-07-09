# New Brendan/Skool Modules — Sanitized Summary

**Source:** Brendan's Skool announcement ("New Modules: Screeners & Advanced HMMs").
**Status:** RESEARCH_ONLY. This is a paraphrased concept summary, not a copy of the
paid course material. Raw PDFs were reviewed locally and are **not** committed to
this repository (see `.gitignore` / local `.tmp/skool_pdfs/` working folder).

Three new modules were announced:

1. **Track A: Screeners** — chat-based (Claude Web UI) stock/crypto screening.
2. **Track B: Automated Screeners** — Claude-Code-built deterministic screener pipeline.
3. **Advanced HMM Tuning** (Track B) — tuning dials for regime-detection bots.

---

## 1. Track A — Chat Screening (Claude Web UI)

**What it is:** A methodology for using conversational Claude sessions as a
judgment-based, non-deterministic screener — the "front of the funnel" that
narrows a large universe (stocks/options/crypto) down to a short, ranked
candidate list worth spending expensive research time on.

**Key paraphrased concepts:**

- **Screening ≠ signal.** A screen only produces research candidates. Every
  survivor must go through a research/thesis step and a risk-sizing step
  before it becomes a trade idea — never straight from screen to order.
- **Universe design is the first (invisible) filter.** Whatever universe you
  define (index membership, cap range, liquidity floor, crypto tier, etc.)
  silently excludes everything outside it. The universe should be a
  deliberate, written, periodically-refreshed choice — not an accident of
  familiarity.
- **Filter taxonomy** — the module organizes screening filters into families:
  liquidity/floor filters (never loosened), trend filters, momentum filters
  (absolute vs. relative-to-benchmark), setup/proximity filters (distance to
  a level where risk can be defined), volatility/character filters, quality
  filters (business-health floor, not a full thesis), and event/calendar
  filters (earnings, macro prints, unlocks).
- **A good screen has few, strong, explainable filters** — each one must be
  able to state *what it excludes and why*. Short/ranked/possibly-empty
  output lists are correct; padding a weak day's list is treated as a
  failure mode.
- **Dial tuning discipline** — tune one threshold at a time, log what changed,
  keep changes that persist for a defined trial period, and record everything
  in a running journal (since a chat-based screen can't be backtested the
  way code can).
- **Regime-appropriate screening** — different screen types have a "home"
  market regime (trending, choppy/range, stressed); running the wrong screen
  type for the current regime under-performs by design. A regime check
  should precede screen selection.
- **A personalization "profile"** (universe, timeframe, risk comfort,
  exclusions, output rules) is meant to be reused across every screening
  session so results are consistent and personal rather than generic.
- **Graduation path to automation** — a screen becomes a candidate for
  Track B automation once its criteria are fully checkable (no judgment
  words), stable across weeks, and journaled as productive.

**Not adopted as-is:** the course's specific 84-prompt library, proprietary
prompt wording, and any exact copy-pasted checklists are intentionally
excluded from this summary and from the repo.

---

## 2. Track B — Automated Screener (Claude Code build)

**What it is:** The deterministic counterpart to Track A. Instead of asking
Claude in chat, a Python program is built (with Claude Code) that pulls
market data on a schedule, applies fixed filter rules, ranks survivors, and
publishes a static dashboard — same input always produces the same output.

**Key paraphrased architecture concepts:**

- **Config-first design.** All user-specific parameters (universe, liquidity
  floor, filter thresholds, ranking weights, schedule, list length) live in
  one settings file (e.g. `settings.yaml`). The code itself never hard-codes
  a threshold — this is what lets one codebase serve many different personal
  screeners.
- **Filter library as small, independently-testable components.** Each filter
  (liquidity, price range, trend, momentum, proximity/setup, volatility,
  volume-surge, event/gap exclusion) is its own class with a `pass_fail`
  method and a plain-language reason string, so every result is explainable.
  Point-in-time discipline (no look-ahead) is a stated requirement.
- **Ranking layer** turns filter pass/fail plus component scores into a
  single weighted composite score, with configurable weights and a minimum
  score threshold — explicitly allowing an empty result list.
- **Named screen "profiles."** Multiple screens (momentum, pullback,
  breakout, etc.) are pure-configuration variants of the same engine — adding
  a new screen means writing config, not code.
- **Scheduling & archiving.** The screener runs unattended on a schedule
  (always-on loop or free CI-based scheduled runs), and every run is archived
  with a timestamp so a history of screen output accumulates.
- **Static, dependency-light HTML dashboard**, regenerated every run, showing
  today's ranked results, a "what changed since last run" diff, and a short
  history — no server required.
- **Alerting** is config-driven (new top candidate, watchlist hit,
  score-threshold crossing) with a hard cap on alert volume, and secrets for
  delivery channels (Discord/Telegram/email) are expected to live in
  environment variables, never in config or code.
- **"Parameter packs"** — a pattern for sharing a screen profile as a
  standalone config file (with an author/description/market header) so a
  screen can be shared and adapted without sharing code.
- **Standing guardrail, repeated explicitly:** the screener's output is a
  research queue only. It never places orders. An empty list on a weak day is
  the *correct* output, not a bug to "fix" by loosening thresholds.

---

## 3. Advanced HMM Tuning (Track B — Advanced)

**What it is:** A tuning guide for regime-detection HMM bots that already have
a working base model (e.g. a default 3-state Gaussian HMM), covering the
dials that make the detector fit a specific asset/timeframe rather than using
one-size-fits-all defaults.

**Key paraphrased tuning concepts:**

- **What tuning can/can't do.** Tuning can make regimes match an asset's real
  behavior, reduce whipsaw, and reduce (not eliminate) detection lag. It
  cannot predict regime changes in advance, remove lag entirely, or rescue a
  strategy that has no underlying edge. Validation (out-of-sample) still
  governs everything.
- **State-count selection.** Fit multiple candidate state counts (e.g. 2–5),
  compare with an information criterion (BIC/AIC) as a *shortlist* tool, then
  apply an "economic meaning" test — every retained state must be nameable
  (e.g. "calm uptrend," "high-vol selloff") and map to a distinct playbook, or
  it should be merged away. Statistical fit is explicitly described as
  necessary but not sufficient.
- **Feature selection & hygiene.** Start from a small core feature set
  (returns, volatility, volume/activity). Feature *window length* is framed as
  a lag-vs-noise dial (short windows react faster but are noisier; long
  windows are smoother but lag more). Discipline: no look-ahead in any
  feature/scaling, use stationary inputs (returns/ratios, not raw prices),
  and test each added feature for whether it actually makes states cleaner —
  removing it if not.
- **Per-asset tuning profiles.** The guide frames crypto, equities/indices,
  and futures as needing materially different dials (state count, feature
  window length, extra features like funding rate or VIX, retraining
  frequency, gating strictness) because their underlying market "physics"
  differ (24/7 vs. session-based, volatility magnitude, leverage). This maps
  naturally onto a config-driven "asset profile" pattern, similar to the
  screener's config-first design.
- **Signal gating stack (anti-whipsaw).** A confidence-threshold gate (only
  act on a state change when its probability clears a threshold) plus a
  persistence gate (require the new state to hold for N consecutive bars)
  are described as the standard two-layer defense against flickering raw HMM
  output. A confidence-scaled position-sizing mode is presented as a more
  advanced alternative to hard on/off gating.
- **External volatility integration** (e.g. VIX for equities, funding
  rate/implied vol for crypto, MOVE index for rates) can be wired in two
  ways: as an additional model feature, and/or as an independent circuit-
  breaker override that forces a defensive stance regardless of the HMM's
  read. Pitfalls called out: timestamp alignment (no look-ahead on the
  external series), double-counting with existing vol features, and
  threshold overfitting (prefer round, robustness-tested levels).
- **Retraining schedules.** Framed as a tunable parameter with a real
  tradeoff: too rare and the model describes a stale market; too frequent and
  it chases noise / redefines its own regime labels. A calendar schedule plus
  a drift-detection tripwire (based on live model fit degrading) is the
  suggested combination. Critically: whatever retraining schedule runs live
  must be the *exact* schedule simulated in walk-forward validation, or the
  backtest doesn't describe the live system.
- **Regime validation.** The decisive test is an out-of-sample walk-forward
  comparison of (a) strategy + tuned HMM regime switch vs. (b) same strategy
  with a naive filter (e.g. moving-average regime proxy) vs. (c) no regime
  layer at all. The HMM only "earns" its added complexity if it beats both
  simpler baselines out-of-sample. Detection lag should be explicitly
  measured (bars-late at known historical turning points) and budgeted for in
  position sizing, not treated as a flaw to eliminate.
- **When not to use an HMM.** A comparison framing against simpler filters
  (moving averages) and other ML alternatives (GMM/clustering, supervised
  classifiers, deep learning) with the explicit rule: complexity must earn
  its place by beating the simpler alternative out-of-sample, or the simpler
  tool should be used instead.
- **A "tuning log"** pattern is suggested — recording every tuning experiment
  (what changed, hypothesis, before/after validation results, keep/revert
  decision) partly so that the number of tuning trials run can be accounted
  for when judging whether a final result is statistically meaningful
  (deflated-Sharpe-style discipline).

---

## What is intentionally NOT imported

- No exact prompt text, templates, or the full 84-item Track A prompt library.
- No paid PDF content is stored verbatim in the repository.
- No credentials, cookies, signed file URLs, or session tokens from Skool.
- No new execution, order-placement, or live-trading capability is implied or
  requested by any of the above — every module explicitly reinforces
  research-only / paper-only framing already used in the Jarvis roadmap.
