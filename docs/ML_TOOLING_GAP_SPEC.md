# ML Tooling Gap — Architecture Specification

> **Status:** DRAFT — awaiting user approval before implementation.
> **Origin:** `docs/SKOOL_VS_JARVIS_IMPLEMENTATION_AUDIT.md`, Finding 12 (Missing).
> **Goal:** Document a real capability gap without recommending premature
> complexity. This spec is deliberately conservative.

---

## 1. Purpose

The Skool research notes reference gradient-boosted tree models (XGBoost /
LightGBM) as a common tool for signal generation and feature selection. This
repo's current statistical/ML surface is:

- `analysis/linear_baseline.py` — logistic regression baseline (confirmed via
  `tests/test_linear_baseline.py`'s use of `LogisticRegressionCV`).
- `core/hmm_engine.py` — Gaussian HMM regime detection (`hmmlearn`).
- `analysis/momentum_research.py`, `analysis/cluster_hunter.py`,
  `analysis/multi_horizon_hunter.py`, `analysis/structural_arb.py`,
  `analysis/fundamental_arb.py`, `analysis/industrial_hunter.py` —
  research modules (not read line-by-line during the audit; likely mostly
  statistical/rule-based rather than tree-ensemble ML, but this should be
  confirmed, not assumed, before treating this gap as fully open).

No gradient-boosting library (`xgboost`, `lightgbm`, `catboost`) appears in
`requirements.txt`. This is a genuine tooling gap relative to the Skool
curriculum's toolset.

## 2. Explicit non-recommendation

**This spec does NOT recommend adding gradient-boosted trees right now.**
The existing `analysis/linear_baseline.py` was very likely built specifically
*because* linear/logistic baselines are:
- Far less prone to overfitting on the amount of data typically available in
  daily-bar equity backtests.
- Easier to interpret and sanity-check for look-ahead bias.
- A deliberately conservative first step before reaching for more
  expressive (and more overfit-prone) models — this matches the
  `write-lookahead-test` skill's repeated emphasis on the risk of models
  "peeking" or fitting noise.

Adding XGBoost/LightGBM without first exhausting simpler approaches would
contradict the repo's own stated design philosophy of "honesty over
performance" (`docs/EDGE_HUNTING_PIPELINE_SPEC.md` §2.1). This spec exists to
make the OPTION available and reviewed, not to advocate for exercising it.

## 3. If/when this is picked up: design constraints

Should a concrete use case arise where a linear model provably underfits a
genuinely non-linear relationship (evidenced by, e.g., `linear_baseline.py`
showing near-zero skill on a feature set with known non-linear structure —
not just "trying XGBoost because it might do better"), the following
constraints apply:

1. **Same validation gate, no exceptions.** Any tree-ensemble model goes
   through the exact same look-ahead test coverage
   (`write-lookahead-test` skill), CPCV, and deflated Sharpe pipeline as any
   other strategy — `docs/EDGE_HUNTING_PIPELINE_SPEC.md` is not bypassed for
   ML models.
2. **Purged, embargoed CV is mandatory, not optional.** Tree ensembles are
   more prone to overfitting on autocorrelated financial time series than
   linear models; `tests/test_linear_baseline.py`'s existing
   `test_boundary_purge_and_embargo` pattern must be replicated exactly for
   any new model class — no exceptions for "it's just a quick test."
3. **Feature importance is not causality.** Any tree-based feature-importance
   ranking is a candidate for further investigation, not a conclusion.
   Findings should be cross-checked against
   `analysis/trade_reviewer.py`-style manual review before being trusted.
4. **New dependency, explicit approval.** Adding `xgboost` or `lightgbm` to
   `requirements.txt` is a supply-chain decision (new binary dependency,
   larger install footprint) that should be called out and approved
   explicitly, not bundled silently into an unrelated change.
5. **Sits alongside, not instead of, `linear_baseline.py`.** Any new model
   is evaluated as an ADDITIONAL candidate compared against the existing
   linear baseline on the same data/features/validation gate — never
   presented as a wholesale replacement without a head-to-head comparison.

## 4. Module Map (what exists vs. what would be new, if approved)

| Component | Status | Module |
|---|---|---|
| Linear baseline (logistic regression) | **exists (reused unchanged)** | `analysis/linear_baseline.py` |
| Look-ahead test pattern to replicate | **exists (reused unchanged)** | `tests/test_linear_baseline.py` |
| CPCV / deflated Sharpe | **exists (reused unchanged)** | `backtest/cpcv.py`, `backtest/deflated_sharpe.py` |
| Gradient-boosted tree baseline | **new, NOT recommended yet** | `analysis/tree_ensemble_baseline.py` (name TBD) |

## 5. What this does NOT do

- ❌ Does not add any new dependency to `requirements.txt`.
- ❌ Does not modify `analysis/linear_baseline.py` or any existing analysis
  module.
- ❌ Does not implement anything — this documents an option, not a plan of
  record.
- ❌ Does not claim the six unread `analysis/` modules definitely lack
  tree-ensemble logic already — that should be confirmed with a targeted
  read before treating this as a hard gap, not an assumed one.

## 6. Recommended next step (if this is ever revisited)

Before writing any tree-ensemble code: read
`analysis/momentum_research.py`, `analysis/cluster_hunter.py`,
`analysis/multi_horizon_hunter.py`, `analysis/structural_arb.py`,
`analysis/fundamental_arb.py`, and `analysis/industrial_hunter.py` in full to
confirm none of them already use a tree-ensemble or other non-linear model
under a name that wasn't obvious from a file listing. This is the same
"verify before building" discipline applied in
`docs/STRATEGY_LIBRARY_EXPANSION_SPEC.md` §0.

---

**Approval required:** Do not implement until this architecture is approved
AND a concrete, evidenced use case (per §3, item 1) exists.
