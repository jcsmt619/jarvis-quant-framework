# SKOOL vs JARVIS Implementation Audit

> **Created:** 2026-07-04
> **Scope:** Cross-reference of `private_research/skool/*.md` claims against the
> actual Jarvis codebase, verified by direct code reading (not assumed).
> **Method:** Every claim below was checked against the live source file(s)
> listed. Claims that could not be directly verified are marked accordingly.
> **No code was changed to produce this report.**

---

## How to read this report

Each finding has a classification:

1. **Already implemented correctly**
2. **Partially implemented**
3. **Missing**
4. **Implemented incorrectly**
5. **Dangerous / likely Gemini damage**
6. **Unclear and needs human review**

And these fields:
- **Skool reference** — which private note the claim comes from
- **Affected Jarvis files**
- **Exact risk if ignored**
- **Proposed fix**
- **Changes strategy logic?**
- **Changes backtest assumptions?**
- **Changes live/paper execution behavior?**

---

## FINDING 1 — Dead code / unreachable `return` in `PortfolioRiskManager.kill_switch_engaged()`

**Classification: 5. Dangerous / likely Gemini damage**

- **Skool reference:** SKOOL_RISK_RULES.md, "Circuit Breakers" checklist — "Peak DD breaker writes a lock file requiring manual deletion", "Every circuit breaker manually triggered and verified."
- **Affected Jarvis files:** `core/risk_manager.py`, lines 690–692
- **Details:** The method is:
  ```python
  def kill_switch_engaged(self) -> bool:
      return self.lock_file.exists()
      return (None, None)
  ```
  The second `return (None, None)` is unreachable dead code — it can never execute because the function already returned. It has no runtime effect today, but it is a strong signature of corrupted/duplicated code (likely from an automated edit that appended a stray return from a different function, e.g. `_correlation_action`, which legitimately returns `(None, None)` elsewhere in the same file at line ~504). This kind of artifact is exactly what "Gemini damage" audits look for: evidence that an automated tool spliced code from one function into another.
- **Exact risk if ignored:** Currently benign (unreachable code has zero runtime effect), but it signals the file may have other, less obvious splicing damage that *does* have runtime effect. It also makes the file harder to trust/review and could confuse future automated refactors that pattern-match on trailing `return` statements.
- **Proposed fix:** Delete the stray `return (None, None)` line. Pure cleanup, zero behavior change (line is unreachable already).
- **Changes strategy logic?** No.
- **Changes backtest assumptions?** No.
- **Changes live/paper execution behavior?** No (line is dead code, never executes).

---

## FINDING 2 — Circuit breakers, Kelly sizing, correlation checks, gap protection

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_RISK_RULES.md ("Risk Manager Rules"), SKOOL_JARVIS_GAP_REPORT.md (§5 RISK MANAGEMENT)
- **Affected Jarvis files:** `core/risk_manager.py` (`CircuitBreaker`, `RiskManager.validate_signal`, `PortfolioRiskManager`), `config/settings.yaml`
- **Verified directly in code:**
  - Daily/weekly/peak drawdown breakers exist (`CircuitBreaker.update()`), peak breaker writes a manual-delete lock file (`_write_lock`) — confirmed.
  - `validate_signal()` is the single gate; mandatory ATR stop enforced (rejects if `stop_loss is None or atr <= 0`) — confirmed.
  - Max concurrent positions, max daily trades, max total exposure, max single-position cap — all present and enforced with explicit rejection messages.
  - Correlation check present (`_correlation_action`, `corr_threshold`/`corr_reduce`) with reject/reduce logic based on rolling correlation and sector matching.
  - Equity overnight-gap buffer present (`equity_gap_atr_mult`) — widens stop distance for `asset_class == "equity"`.
  - Fractional Kelly sizing present (`kelly_fraction_value()`), hard-capped by `risk_per_trade` (1.5% in settings.yaml) — matches the "survival first" 1–2% rule exactly.
  - All thresholds are sourced from `config/settings.yaml` via `RiskLimits.from_settings()` / `PortfolioRiskLimits.from_settings()`, not hardcoded.
  - Portfolio-level second veto layer (`PortfolioRiskManager`) exists above the per-strategy managers, confirmed wired into `execution/multistrat_engine.py._process_signal()` — both layers must approve.
- **Exact risk if ignored:** N/A — nothing to fix.
- **Proposed fix:** None needed.
- **Changes strategy logic / backtest / execution?** N/A.

**Note:** `settings.yaml` values (max_leverage 1.5x, max_total_exposure 1.0x/100%) are actually *more conservative* than the Skool note's stated defaults (max_leverage 1.25x mentioned in gap report vs `RiskLimits` dataclass default of 4.0x hard cap, overridden down to 1.5x in the actual live config). This is fine — the dataclass defaults are just permissive fallbacks; `settings.yaml` is what's actually loaded. Worth being aware that if `settings.yaml` fails to load (bad YAML, missing file) `RiskLimits()` falls back to the dataclass defaults, which are **much more aggressive** (max_total_exposure 3.0x, max_leverage 4.0x) than the intended "survival first" values. See Finding 8.

---

## FINDING 3 — HMM look-ahead safety (filtered forward algorithm, not Viterbi/predict())

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_CODE_PATTERNS.md ("HMM Regime Filter Engine Architecture" — "HMM uses predict_regime_filtered (not model.predict()) to avoid look-ahead bias", "Regime at bar t must be identical whether data ends at t+50 or t+500")
- **Affected Jarvis files:** `core/hmm_engine.py`
- **Verified directly in code:**
  - `_forward_log_alpha()` implements a hand-rolled forward algorithm in log-space; explicit docstring states "alpha_t depends ONLY on obs_1:t -> strictly causal, no look-ahead."
  - `predict_regime_filtered()` and `update()` both use this forward recursion, never `model.predict()` (Viterbi, which is non-causal because it revises past states using future observations).
  - The incremental `update()` method caches `_last_log_alpha` and recomputes only using the new bar's emission — mathematically identical to re-running the batch forward pass, satisfying "regime at bar t must be identical whether data ends at t+50 or t+500."
- **Exact risk if ignored:** N/A.
- **Proposed fix:** None needed. This is a genuine strength of the codebase and should be preserved carefully in any future edits — this file is the highest-value target for automated "fixes" that could silently reintroduce look-ahead bias (e.g. swapping in `model.predict()` for convenience).
- **Changes strategy logic / backtest / execution?** N/A.

---

## FINDING 4 — Feature engineering: rolling z-score, no bfill, no negative shifts

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_BACKTESTING_RULES.md ("Key Rules" — "Feature z-scores use 252-period rolling window, not global", "No fit_transform on the full dataset", "No .bfill() that could leak future values", "No center=True in rolling windows", "No negative shifts anywhere in features or signals")
- **Affected Jarvis files:** `data/feature_engineering.py`
- **Verified directly in code:**
  - `standardize_features()` uses `features.rolling(window).mean()` / `.std()` with `window=252` default — a genuinely rolling/trailing calculation, not a global `fit_transform`.
  - No `.bfill()` calls anywhere in the file (confirmed by full read).
  - No `center=True` anywhere in any `.rolling(...)` call (all default to trailing/right-aligned).
  - No negative-argument `.shift()` calls; all `log_returns()` / diff-based features use positive `period` shifts (backward-looking only).
  - Docstring explicitly states the causality guarantee: "Everything is causal (uses only trailing windows)... a prerequisite for the no-look-ahead guarantee enforced in the HMM layer."
- **Exact risk if ignored:** N/A.
- **Proposed fix:** None needed.
- **Changes strategy logic / backtest / execution?** N/A.

---

## FINDING 5 — Validation stack (walk-forward, CPCV, deflated Sharpe, triple-barrier, stress tests)

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_BACKTESTING_RULES.md, SKOOL_CODE_PATTERNS.md ("ML & Edge Discovery Build Library")
- **Affected Jarvis files:** `backtest/backtester.py`, `backtest/cpcv.py`, `backtest/deflated_sharpe.py`, `backtest/triple_barrier.py`, `backtest/stress_test.py`
- **Verified:** All files exist in `backtest/` as claimed (directory listing confirmed: `backtester.py`, `cpcv.py`, `deflated_sharpe.py`, `multistrat.py`, `pairs_backtest.py`, `performance.py`, `stress_test.py`, `triple_barrier.py`, `validation.py`). Contents of these files were **not individually re-read line-by-line** for this audit (only existence + `main.py`'s actual usage of `WalkForwardBacktester`, `stress_test.crash_injection/gap_risk/regime_misclassification` was confirmed via `main.py`). Recommend a follow-up pass if line-level correctness assurance on CPCV/deflated Sharpe math is required.
- **Exact risk if ignored:** Low — existence and wiring confirmed; internal correctness of the statistics not re-derived in this pass.
- **Proposed fix:** None required now; optional follow-up: dedicated audit of `backtest/cpcv.py` and `backtest/deflated_sharpe.py` math against the academic formulas (Lopez de Prado) if a stricter guarantee is wanted.
- **Changes strategy logic / backtest / execution?** N/A.

---

## FINDING 6 — Noise tests (testing against random data)

**Classification: 3. Missing**

- **Skool reference:** SKOOL_BACKTESTING_RULES.md ("Validation Methods" #6 — "Noise tests — test against random data to establish baseline"), SKOOL_JARVIS_GAP_REPORT.md (§3, listed as the one clear gap), SKOOL_CODE_PATTERNS.md (not one of the 12 ML build-library prompts explicitly, but related to "hostile leakage audit")
- **Affected Jarvis files:** None exist. Searched repository-wide for `noise_test|random_data|shuffle.*test|permutation_test` in all `.py` files — zero matches. (Note: `main.py`'s `bt.benchmark_random(result.close, seeds=100)` produces a *random strategy* benchmark for comparison purposes, which is related but is a benchmark, not a "does my strategy behave like noise" statistical test — different purpose.)
- **Exact risk if ignored:** A strategy could pass CPCV/deflated-Sharpe validation yet still be an artifact of the specific historical path, because there is no explicit test asserting "this strategy has near-zero edge when the underlying returns series is replaced with random noise of matching moments." This is the single gap the Skool curriculum calls "the real reason most discovered edges are fake" (multiple-comparisons/noise-fitting).
- **Proposed fix (not implemented — approval required):** Add a `backtest/noise_test.py` (or extend `backtest/stress_test.py`) that: (a) generates N random walks matching the real asset's mean/vol/autocorrelation, (b) runs the exact same strategy + walk-forward pipeline on each, (c) reports the distribution of Sharpe/Calmar on noise, and (d) flags if the real result falls inside that noise distribution (e.g. real Sharpe not statistically distinguishable from the 95th percentile of noise-Sharpe).
- **Changes strategy logic?** No — this is a new validation tool, not a strategy change.
- **Changes backtest assumptions?** No — purely additive; doesn't touch existing backtest logic.
- **Changes live/paper execution behavior?** No.

---

## FINDING 7 — Missing strategies: defensive long/short, correlation regime, pure regime allocation, residual momentum

**Classification: 3. Missing**

- **Skool reference:** SKOOL_STRATEGY_IDEAS.md ("GitHub Template Strategies" and "Priority Ranking for Jarvis"), SKOOL_JARVIS_GAP_REPORT.md (§2 STRATEGY)
- **Affected Jarvis files:** None exist under these names. Directory listing of `strategies/` confirmed: `base.py`, `baseline_ema_rsi.py`, `challenger_variants.py`, `constant_mix.py`, `hmm_adapter.py`, `hyper_alpha_kelly.py`, `meridian_lite.py`, `regime_blend.py`, `skool_variant_1.py`, `vol_allocation.py`. None of these map obviously to "defensive long/short", "correlation regime", or "pure regime allocation" by name — a closer content read of `regime_blend.py` and `skool_variant_1.py` would be needed to rule out an unlabeled equivalent, but this audit did not read those files' internals.
- **Exact risk if ignored:** None — these are pure strategy-breadth opportunities, not defects. Skipping them costs upside, not safety.
- **Proposed fix (not implemented — approval required):** Prioritized per the Skool note's own ranking: (1) Residual Momentum — medium effort, existing price data sufficient; (2) Defensive Long/Short — medium effort, existing data sufficient; (3) Correlation Regime — low effort, existing data sufficient; (4) Pure Regime Allocation — low effort, can reuse existing `core/hmm_engine.py` output directly.
- **Changes strategy logic?** Yes, if implemented — this is new strategy logic, which is explicitly out of scope for this audit (no implementation without approval).
- **Changes backtest assumptions?** No, unless/until implemented.
- **Changes live/paper execution behavior?** No, unless/until implemented and explicitly enabled in `config/settings.yaml`.

---

## FINDING 8 — RiskLimits dataclass defaults are materially more aggressive than settings.yaml

**Classification: 6. Unclear and needs human review**

- **Skool reference:** SKOOL_RISK_RULES.md ("Configuration" — "All thresholds in settings.yaml, nothing hardcoded")
- **Affected Jarvis files:** `core/risk_manager.py` (`RiskLimits` dataclass defaults, lines 60–93) vs `config/settings.yaml` (`risk:` section)
- **Details:** The dataclass field defaults in `RiskLimits` are:
  - `max_total_exposure: float = 3.0` (300% gross) vs settings.yaml `max_total_exposure: 1.0` (100%)
  - `max_leverage: float = 4.0` vs settings.yaml `max_leverage: 1.5`
  - `max_concurrent: int = 3` vs settings.yaml `max_concurrent: 5`
  - `crypto_max_leverage: float = 3.0` vs settings.yaml `crypto_max_leverage: 1.5`
  - `letf_max_leverage: float = 4.0` vs settings.yaml `letf_max_leverage: 1.0`

  The module's own docstring (lines 22–27) even flags this explicitly: *"RISK REALITY: 300% gross exposure with full Kelly on 3x LETFs is ~12x underlying beta... This module CONTAINS the aggressive path the rest of the config selects; it does not sanctify it."* This is intentional per the docstring — the dataclass defaults represent the theoretical max the code *supports*, while `settings.yaml` is the actual "survival first" operating config, and `RiskLimits.from_settings()` is the only production code path that constructs the object (confirmed: `paper_loop.py`, `backtest_harness.py`, `monitoring/dashboard.py` all call `.from_settings()`).

  However, `execution/multistrat_engine.py.build_live_engine()` calls `RiskManager(initial_capital=initial_capital)` with **no explicit limits argument**, which means `self.limits = limits or RiskLimits()` falls back to the **aggressive dataclass defaults** (300% exposure, 4x leverage), NOT the conservative settings.yaml values, in the multi-strategy live/dry-run engine path.
- **Exact risk if ignored:** In the multi-strategy live engine (`execution/multistrat_engine.py`, used by `main.py run_multistrat_live()`), every per-strategy `RiskManager` silently uses the permissive 3.0x/4.0x defaults instead of the intended 1.0x/1.5x settings.yaml values, because `build_live_engine()` never threads `RiskLimits.from_settings()` through. Today this only affects the dry-run/mock-executor path (no real broker is wired — confirmed via `main.py` "Refusing to start LIVE trading" guard), so no real capital is at risk yet. But if/when a real broker is wired into `MultiStratLiveEngine`, this becomes a live discrepancy between the config file operators believe they're running and the risk limits actually enforced.
- **Proposed fix (not implemented — approval required):** In `execution/multistrat_engine.py.build_live_engine()`, change:
  ```python
  risk_managers = {name: RiskManager(initial_capital=initial_capital) for name in registry.all()}
  ```
  to:
  ```python
  limits = RiskLimits.from_settings()
  risk_managers = {name: RiskManager(limits=limits, initial_capital=initial_capital) for name in registry.all()}
  ```
  Similarly, `PortfolioRiskManager()` (no args) should become `PortfolioRiskManager(PortfolioRiskLimits.from_settings())`.
- **Changes strategy logic?** No.
- **Changes backtest assumptions?** No (backtest_harness.py already correctly uses `.from_settings()`).
- **Changes live/paper execution behavior?** Yes, if implemented — it would make the multi-strategy dry-run/live engine enforce the conservative settings.yaml limits instead of the permissive dataclass defaults. This is a **safety-tightening** change, not a loosening one, but it does change observable behavior (e.g. tests that currently rely on the permissive defaults in `execution/multistrat_engine.py`'s dry-run demo may need their expectations revisited). Flagging for explicit approval per your "changes execution behavior" criterion.

---

## FINDING 9 — Live trading kill-switch / never-default-live discipline

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_BACKTESTING_RULES.md ("Go-Live Checklist" §6 — "default is paper, explicit config change required, runtime confirmation prompt, not bypassable")
- **Affected Jarvis files:** `main.py`, `broker/alpaca_client.py`, `broker/__init__.py`
- **Verified directly in code:**
  - `main.py cmd_live()`: refuses to start unless `--dry-run` is passed; prints explicit refusal message citing "01_CLAUDE.md rule 4 — never default to live" when `--dry-run` is absent. No broker is even wired in this path currently.
  - `broker/alpaca_client.py AlpacaBroker.__init__`: requires **both** `paper=False` **and** the environment variable `ALPACA_CONFIRM_LIVE == "YES"` to hit the live endpoint; otherwise raises `PermissionError`. Comment explicitly documents this was hardened after a prior incident ("LIVE WAS ONE KEYSTROKE AWAY: `paper=False` flipped the real-money endpoint").
  - `broker/__init__.py get_broker(name="alpaca", paper=True)`: defaults to `paper=True`.
- **Exact risk if ignored:** N/A.
- **Proposed fix:** None needed. This is a genuine strength — two independent gates (CLI flag + env var) must both be explicitly overridden to reach live trading.
- **Changes strategy logic / backtest / execution?** N/A.

---

## FINDING 10 — Credentials hygiene (.env, .gitignore)

**Classification: 1. Already implemented correctly**

- **Skool reference:** SKOOL_BACKTESTING_RULES.md ("Go-Live Checklist" §5 — "no API keys in .py files, .env in .gitignore, git history audited")
- **Affected Jarvis files:** `.gitignore`, `.env`
- **Verified directly in code:** `.gitignore` line 2 excludes `.env` and `.env.*` (with an explicit exception for `.env.example`), plus `credentials.yaml`, `*.key`, `*.pem`, `*.session`, `*.har`, and `skool_cookies.txt` variants. `private_research/` itself is also gitignored (line 58), which is correct given these Skool notes are explicitly marked "NOT FOR REDISTRIBUTION."
- **Note:** This audit did **not** run `git log -p` to check historical commits for leaked keys — that check ("git history audited") requires a separate, explicit git-history scan and was out of scope for a static file read. Recommend running `git log --all -p | grep -i "api_key\|secret"` (or a tool like `gitleaks`) as a follow-up if this hasn't been done since repo creation.
- **Exact risk if ignored:** Low today (current state is clean); the git-history check is the one unverified sub-claim.
- **Proposed fix:** Run a git-history secret scan as a follow-up (does not require code changes).
- **Changes strategy logic / backtest / execution?** N/A.

---

## FINDING 11 — Broker breadth (IBKR, TradeStation) not implemented

**Classification: 3. Missing**

- **Skool reference:** SKOOL_JARVIS_GAP_REPORT.md (§6 EXECUTION — "IBKR integration... No... YES", "TradeStation integration... No... YES")
- **Affected Jarvis files:** `broker/` directory contains only `__init__.py`, `alpaca_client.py`, `base.py`. Confirmed via directory listing — no IBKR or TradeStation adapter files exist.
- **Exact risk if ignored:** None — this is a breadth/optionality gap, not a defect. Alpaca is fully wired and is the only broker in active use.
- **Proposed fix (not implemented — approval required):** Use the existing `add-broker-adapter` skill (already present per SKOOL_CODE_PATTERNS.md's "Claude Skills" section, confirmed relevant skill exists in this environment) to scaffold a new adapter against `broker/base.py`'s `BaseBroker` abstract class when/if a second broker is actually needed.
- **Changes strategy logic?** No.
- **Changes backtest assumptions?** No.
- **Changes live/paper execution behavior?** No, unless/until implemented and selected via `get_broker(name=...)`.

---

## FINDING 12 — ML model variety gap (regime-conditioned GBM, skeptical feature importance)

**Classification: 3. Missing (partially — permutation importance exists elsewhere, but not "regime-conditioned")**

- **Skool reference:** SKOOL_CODE_PATTERNS.md ("ML & Edge Discovery Build Library" #5 and #6), SKOOL_JARVIS_GAP_REPORT.md (§4 ML/EDGE DISCOVERY)
- **Affected Jarvis files:** Searched repo-wide for `GradientBoosting|xgboost|lightgbm|permutation_importance`. Found `permutation_importance` usage (from `sklearn.inspection`) in **`alpha_hunter.py`** and **`analysis/multi_horizon_hunter.py`**, both paired with `sklearn.ensemble.RandomForestClassifier` — so a form of "skeptical feature importance" partially exists, but outside the core `edge_hunting/` pipeline referenced by the Skool notes, and using RandomForest rather than a GBM. No `xgboost`/`lightgbm`/regime-conditioned GBM implementation was found anywhere.
- **Exact risk if ignored:** None immediate — this is a model-variety enhancement opportunity, not a defect. The existing linear baseline (`analysis/linear_baseline.py`, confirmed to exist) plus CPCV/deflated-Sharpe validation already provide the core "don't trust a model that hasn't survived adversarial validation" discipline; GBM would add capacity, not safety.
- **Proposed fix (not implemented — approval required):** If pursued, add a `regime-conditioned GBM` model inside `edge_hunting/` (not `alpha_hunter.py`/`analysis/`) so it goes through the same `edge_hunting/gate.py` validation gate as everything else, using regime label (from `core/hmm_engine.py`) as an explicit categorical feature.
- **Changes strategy logic?** No, unless implemented.
- **Changes backtest assumptions?** No.
- **Changes live/paper execution behavior?** No.

---

## Summary Table

| # | Finding | Classification | Approval needed before acting? |
|---|---|---|---|
| 1 | Dead code in `PortfolioRiskManager.kill_switch_engaged()` | Dangerous / likely Gemini damage | Yes — trivial fix, but still a code change |
| 2 | Circuit breakers / Kelly / correlation / gap protection | Already implemented correctly | No action needed |
| 3 | HMM look-ahead safety (filtered forward algorithm) | Already implemented correctly | No action needed |
| 4 | Feature engineering causality (no bfill, no negative shift, rolling z-score) | Already implemented correctly | No action needed |
| 5 | Validation stack (walk-forward/CPCV/deflated Sharpe/triple-barrier) | Already implemented correctly (existence + wiring only) | Optional deep-dive follow-up |
| 6 | Noise tests | Missing | Yes — new test module |
| 7 | Missing strategies (defensive L/S, correlation regime, pure regime allocation, residual momentum) | Missing | Yes — new strategy logic |
| 8 | `RiskLimits` dataclass defaults vs settings.yaml drift in multistrat engine | Unclear / needs review | Yes — changes live/paper execution behavior |
| 9 | Never-default-live discipline | Already implemented correctly | No action needed |
| 10 | Credentials hygiene | Already implemented correctly (git-history scan not run) | Optional follow-up (no code change) |
| 11 | Broker breadth (IBKR/TradeStation) | Missing | Yes — new broker adapters |
| 12 | ML model variety (regime-conditioned GBM, feature importance) | Missing (partial) | Yes — new model work |

---

## What this audit did NOT do

- Did not read every line of `backtest/cpcv.py`, `backtest/deflated_sharpe.py`, `backtest/triple_barrier.py`, `backtest/stress_test.py`, `backtest/pairs_backtest.py`, or `backtest/validation.py` — only confirmed their existence and that `main.py` calls into `stress_test` and `WalkForwardBacktester` as claimed.
- Did not read `strategies/regime_blend.py`, `strategies/skool_variant_1.py`, `strategies/challenger_variants.py`, `strategies/meridian_lite.py`, `strategies/hyper_alpha_kelly.py`, or `strategies/constant_mix.py` internals — so it's possible one of these already implements "correlation regime" or "pure regime allocation" under a different name. This should be checked before treating Finding 7 as fully confirmed.
- Did not run `git log` / secret-scanning on repository history (Finding 10's one open sub-item).
- Did not execute `pytest` to confirm all the referenced tests (`tests/test_look_ahead.py`, `tests/test_risk_manager.py`, `tests/test_portfolio_risk.py`, `tests/test_tail_monitor.py`, `tests/test_decay_monitor.py`) currently pass — their existence was confirmed via `search_files` grep matches only.
- Made **no code changes**. All "Proposed fix" text above is a recommendation only, pending your explicit approval per item.
