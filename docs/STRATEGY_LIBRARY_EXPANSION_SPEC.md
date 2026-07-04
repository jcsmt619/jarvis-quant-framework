# Strategy Library Expansion — Architecture Specification

> **Status:** DRAFT — awaiting user approval before implementation.
> **Origin:** `docs/SKOOL_VS_JARVIS_IMPLEMENTATION_AUDIT.md`, Finding 7 (Missing).
> **Goal:** Add strategy breadth (not fix a defect). Four candidate strategies
> identified in the Skool research notes with no equivalent currently in
> `strategies/`.

---

## 0. Pre-condition (must happen before any of this is built)

Finding 7 flagged that `strategies/regime_blend.py` and
`strategies/skool_variant_1.py` were **not read internally** during the
audit — it's possible one of them already implements "correlation regime" or
"pure regime allocation" under a different name. Before implementing anything
in this spec, do a targeted read of:
- `strategies/regime_blend.py`
- `strategies/skool_variant_1.py`
- `strategies/challenger_variants.py`

...to confirm these four strategies are genuinely net-new and not
duplicating existing logic under a different name. This spec assumes that
check comes back clean; if it doesn't, this spec should be revised before
implementation.

## 1. Design Principles (apply to all four strategies below)

1. **Adapter pattern, not rewrite.** Each new strategy implements the
   existing `BaseStrategy` interface (`core/regime_strategies.py`) the same
   way `strategies/hmm_adapter.py` wraps `core/hmm_engine.py` — no existing
   strategy class is modified.
2. **Mandatory stop, no exceptions.** Per `01_CLAUDE.md` rule and
   `core/risk_manager.py`'s enforcement, every signal these strategies emit
   MUST carry a non-null `stop_loss`. This is enforced by the risk layer
   regardless, but each strategy's own signal-generation logic must compute
   one honestly (ATR-based, matching the existing convention).
3. **No look-ahead.** Any new indicator/feature computation follows the same
   causal-only rule as `data/feature_engineering.py` (trailing windows only,
   no negative shifts, no `center=True`). New features should go through
   `tests/write-lookahead-test` skill coverage before being trusted.
4. **Goes through the edge-hunting gate before being enabled live.** Each new
   strategy is validated via `docs/EDGE_HUNTING_PIPELINE_SPEC.md`'s pipeline
   (walk-forward + CPCV + deflated Sharpe + the new noise test from
   `docs/NOISE_TEST_SPEC.md`) BEFORE it is registered in
   `core/registered_strategies.py` or enabled in `config/settings.yaml`.
5. **Disabled by default.** Every new strategy ships with `enabled: false` in
   `config/settings.yaml` until it has passed the validation gate.

## 2. Candidates, in priority order (per the Skool note's own ranking)

### 2.1 Residual Momentum (Priority 1 — medium effort)

- **Concept:** Rank symbols by momentum AFTER regressing out market beta
  (i.e., momentum in the residual, not raw, return series) — reduces
  correlation with simple market-beta momentum and historically shows more
  persistence.
- **Data needed:** Existing OHLCV (already fetched via `data_fetcher.py`).
  Requires a broad-market proxy return series (e.g., SPY) to compute beta —
  already available.
- **New module:** `strategies/residual_momentum.py`
- **Core computation:**
  1. Rolling OLS beta of each symbol's returns vs. market proxy (rolling
     window, e.g. 126 bars, causal).
  2. Residual return = symbol return − beta × market return.
  3. Rank symbols by trailing N-bar cumulative residual return.
  4. Long top-decile / avoid or short bottom-decile (long-only variant should
     be the default given `01_CLAUDE.md`'s existing long-bias conventions in
     `core/regime_strategies.py`).
- **Effort:** Medium — rolling-beta computation is new, but no new data
  source is required.

### 2.2 Defensive Long/Short (Priority 2 — medium effort)

- **Concept:** Long the strongest relative-strength names, short (or
  underweight) the weakest, sized to keep net market exposure near zero in
  choppy/uncertain regimes — the "defensive" character comes from the
  reduced beta exposure, not from an absence of positions.
- **Data needed:** Existing OHLCV for a symbol universe (already available
  via `data/fetch_universe.py` / `data/universe/`).
- **New module:** `strategies/defensive_long_short.py`
- **Core computation:**
  1. Rank universe by trailing relative strength (e.g., 60-bar return).
  2. Long top-N, short bottom-N (or, if the repo's short-selling posture is
     not yet decided — see Open Question below — long top-N / cash
     bottom-N as a long-only fallback).
  3. Size each leg so net beta ≈ 0.
  4. Only activate in `regime in {"NEUTRAL", "uncertain"}` per the HMM
     output — this is the "defensive" trigger condition.
- **Open question requiring your explicit decision before implementation:**
  Does the repo currently support short positions anywhere in
  `core/risk_manager.py`/`broker/alpaca_client.py`? A quick grep during this
  audit did not confirm short-selling support end-to-end. If not supported,
  this strategy should ship long-only-vs-cash as a first version, with true
  long/short deferred to a broker-adapter capability check.
- **Effort:** Medium — needs multi-symbol ranking logic not yet present in
  any single-symbol-per-strategy config today (per `config/settings.yaml`'s
  current `symbols: [X]` convention, this may need a config schema addition
  for multi-symbol universes).

### 2.3 Correlation Regime (Priority 3 — low effort)

- **Concept:** Track rolling average pairwise correlation across a basket
  (e.g., sector ETFs or the existing strategy universe) as a regime signal
  distinct from the HMM's volatility-based regime — high average correlation
  often precedes/accompanies risk-off/crash regimes ("everything sells off
  together").
- **Data needed:** Existing OHLCV for the same symbols already tracked by
  `core/capital_allocator.py`'s `compute_correlation_matrix()` — **this
  computation likely already exists and can be reused directly** rather than
  reimplemented.
- **New module:** `strategies/correlation_regime.py` (or, if primarily a
  regime **filter** rather than a signal generator, `core/regime_filters.py`
  as a shared utility consumed by other strategies)
- **Core computation:**
  1. Reuse `CapitalAllocator.compute_correlation_matrix()` (confirmed to
     exist in `core/capital_allocator.py`, already used by
     `execution/multistrat_engine.py._detect_correlation_clusters()`).
  2. Compute rolling average off-diagonal correlation.
  3. Classify into LOW/MEDIUM/HIGH correlation regime via configurable
     thresholds (mirroring the HMM's `_LABEL_SCHEMES` pattern for
     consistency).
  4. Expose this as an additional gating signal other strategies can consult
     (e.g., "reduce exposure when correlation regime is HIGH"), not
     necessarily as a standalone P&L-generating strategy.
- **Effort:** Low — the heaviest computation (`compute_correlation_matrix`)
  already exists; this is mostly a thresholding/labeling wrapper.

### 2.4 Pure Regime Allocation (Priority 4 — low effort)

- **Concept:** A strategy whose ONLY input is the HMM regime label/probability
  (no price-action overlay, no separate technical signal) — i.e., a maximally
  simple "trust the regime engine alone" baseline, useful as a lower bound
  to compare `core/regime_strategies.py`'s more elaborate strategies against.
- **Data needed:** None beyond what `core/hmm_engine.py` already produces.
- **New module:** `strategies/pure_regime_allocation.py`
- **Core computation:**
  1. Consume `RegimeState` (label, probability, is_confirmed) directly from
     `core/hmm_engine.py`.
  2. Allocation = f(regime.expected_return, regime.expected_volatility) from
     the existing `RegimeInfo` metadata (already computed in
     `HMMRegimeEngine._build_regime_metadata`) — no new inference required.
  3. Stop = ATR-based, matching the existing convention in
     `core/regime_strategies.py`.
- **Effort:** Low — this is almost entirely a thin wrapper around metadata
  the HMM engine already computes; the main "new" work is the allocation
  function mapping regime metadata to a position size, which is simple.

## 3. Module Map (what exists vs. what's new)

| Component | Status | Module |
|---|---|---|
| BaseStrategy interface | **exists (reused unchanged)** | `core/regime_strategies.py` |
| HMM regime engine + metadata | **exists (reused unchanged)** | `core/hmm_engine.py` |
| Correlation matrix computation | **exists (reused unchanged)** | `core/capital_allocator.py` |
| Residual Momentum | **new** | `strategies/residual_momentum.py` |
| Defensive Long/Short | **new** | `strategies/defensive_long_short.py` |
| Correlation Regime | **new** | `strategies/correlation_regime.py` |
| Pure Regime Allocation | **new** | `strategies/pure_regime_allocation.py` |
| Multi-symbol universe config schema (if needed for 2.2) | **new/TBD** | `config/settings.yaml` schema extension |

## 4. What this does NOT do

- ❌ Does not modify any existing strategy file.
- ❌ Does not enable any new strategy in `config/settings.yaml` by default.
- ❌ Does not change `core/risk_manager.py`, `core/capital_allocator.py`, or
  `core/hmm_engine.py` — all four candidates consume existing outputs.
- ❌ Does not add short-selling broker support — Defensive Long/Short ships
  long-only-vs-cash unless/until short support is separately confirmed and
  approved.
- ❌ None of these strategies go live or into paper trading until they pass
  the full edge-hunting validation gate.

## 5. Sequencing recommendation

1. Verify pre-condition (§0) — confirm `regime_blend.py`/`skool_variant_1.py`
   don't already cover this ground.
2. Implement Pure Regime Allocation first (lowest effort, reuses the most
   existing code, useful as a baseline for evaluating the other three).
3. Implement Correlation Regime second (low effort, reuses
   `compute_correlation_matrix`).
4. Implement Residual Momentum third (medium effort, self-contained).
5. Resolve the short-selling open question, then implement Defensive
   Long/Short last (medium effort, has the most open design questions).

Each strategy should be implemented, tested for look-ahead bias, and run
through the edge-hunting pipeline **one at a time**, with results reviewed
before starting the next — not all four built speculatively up front.

---

**Approval required:** Do not implement until this architecture is approved.
