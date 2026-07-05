# Strategy Validation Gate

> **Status:** DRAFT — awaiting user approval before implementation.
> **Purpose:** Define the pass/fail criteria a strategy must clear before it
> graduates from edge hunting to paper-trading eligibility.

---

## 1. Philosophy

A strategy that passes the gate is not "good" — it is **not obviously broken**.
The gate is a filter, not an endorsement. Its job is to reject strategies that
are statistically meaningless, overfit, fragile, or look-ahead contaminated
before they waste paper-trading time.

**A strategy that fails ANY hard gate criterion is REJECTED.** No partial
credit, no "almost passed." The failure is documented in
`failure_reasons.md` with the specific metric and threshold.

## 2. Gate Criteria

### 2.1 Hard Gates (any failure = REJECT)

| # | Criterion | Threshold | Metric Source | Why |
|---|---|---|---|---|
| H1 | Out-of-sample Sharpe | ≥ 0.5 (annualized) | `performance.compute_metrics` | Below 0.5 is indistinguishable from noise |
| H2 | Max drawdown | ≤ 25% | `performance._max_drawdown` | Beyond 25% is unrecoverable for most accounts |
| H3 | Deflated Sharpe (DSR) | ≥ 0.80 | `deflated_sharpe.deflated_sharpe` | < 0.80 = likely a product of search, not edge |
| H4 | CPCV % paths positive | ≥ 60% | `cpcv.backtest_paths` | Majority of OOS paths must be profitable |
| H5 | Beats random allocation | YES | `backtester.benchmark_random` | Must beat the luck ceiling, not just zero |
| H6 | Look-ahead test | PASS | `tests/test_look_ahead.py` extended | Non-negotiable; no future data leakage |
| H7 | Crash stress worst DD | ≤ 35% | `stress_test.crash_injection` | Must survive injected -5% to -15% gaps |
| H8 | Parameter sensitivity | Stable | ±20% perturbation grid | Sharpe must not flip sign or collapse >50% |

### 2.2 Soft Gates (reported, not blocking)

| # | Criterion | Threshold | Notes |
|---|---|---|---|
| S1 | Beats buy & hold | optional | Risk-managed edge may underperform in bull markets |
| S2 | CPCV Sharpe std | ≤ 1.5 | High variance = unstable edge; reported as warning |
| S3 | Profit factor | ≥ 1.2 | Below 1.2 = marginal; reported as warning |
| S4 | Win rate | ≥ 35% | Below 35% = relies on rare big wins; reported |
| S5 | Avg holding period | ≥ 2 bars | Sub-2-bar = likely overtrading / noise fitting |
| S6 | Regime misclassification contained | YES | `stress_test.regime_misclassification.contained` |

### 2.3 Informational (always reported, never blocking)

- Total return, CAGR, Sortino, Calmar
- Worst day/week/month
- Max consecutive losses
- Longest underwater period
- Regime breakdown table
- Confidence-bucketed performance
- Benchmark comparison table

## 3. Gate Evaluation Procedure

```
gate.evaluate(metrics, robustness_results, look_ahead_passed) → GateVerdict

  hard_failures = []
  soft_warnings = []

  # Hard gates
  if metrics.sharpe < config.min_oos_sharpe:
      hard_failures.append("H1: OOS Sharpe {sharpe} < {min}")
  if metrics.max_drawdown > config.max_max_drawdown:
      hard_failures.append("H2: Max DD {dd} > {max}")
  if dsr < config.min_dsr:
      hard_failures.append("H3: DSR {dsr} < {min}")
  if cpcv_pct_positive < config.min_cpcv_pct_positive:
      hard_failures.append("H4: CPCV {pct}% positive < {min}%")
  if not beats_random:
      hard_failures.append("H5: does not beat random allocation")
  if not look_ahead_passed:
      hard_failures.append("H6: look-ahead test FAILED")
  if crash_worst_dd < -0.35:
      hard_failures.append("H7: crash stress worst DD {dd} < -35%")
  if param_sensitivity_unstable:
      hard_failures.append("H8: parameter sensitivity unstable")

  # Soft gates
  if not beats_buy_hold:
      soft_warnings.append("S1: does not beat buy & hold (informational)")
  ... etc ...

  verdict = "PASS" if not hard_failures else "FAIL"
  return GateVerdict(verdict, hard_failures, soft_warnings)
```

## 4. Output: `failure_reasons.md`

When a strategy FAILS the gate, `failure_reasons.md` is written with:

```markdown
# Failure Reasons — {strategy_name}

## Verdict: FAIL

## Hard Gate Failures

- **H1: OOS Sharpe 0.32 < 0.50**
  The out-of-sample annualized Sharpe ratio is below the minimum threshold.
  This means the strategy's risk-adjusted return is indistinguishable from
  noise at this confidence level.

- **H3: DSR 0.61 < 0.80**
  The deflated Sharpe ratio indicates a 61% probability that the true Sharpe
  exceeds the search ceiling. Below 80%, the edge is likely a product of the
  search process, not a genuine signal.

## Soft Warnings

- **S2: CPCV Sharpe std 1.82 > 1.50**
  High variance across CPCV paths suggests the edge is unstable across
  time periods.

## Recommendation

Do not paper trade. The strategy fails 2 hard gates. Review the signal
logic and feature set; consider whether the edge exists at all or is an
artifact of in-sample fitting.
```

When a strategy PASSES, `failure_reasons.md` contains:

```markdown
# Failure Reasons — {strategy_name}

## Verdict: PASS

No hard gate failures.

## Soft Warnings

(none or listed)

## Note

Passing the validation gate means the strategy is NOT OBVIOUSLY BROKEN.
It does not mean the strategy will be profitable in live trading.
Paper trading is the next step, not deployment.
```

## 5. Output: `assumptions.md`

Every experiment writes `assumptions.md` documenting what was assumed:

```markdown
# Assumptions — {strategy_name}

## Data
- Source: yfinance (daily OHLCV)
- Symbols: SPY
- Period: 2010-01-01 to 2025-12-31
- Adjusted for splits/dividends: yes (auto_adjust=False, adjustment=all)

## Costs
- Commission: $0.00 per trade
- Slippage: 5.0 bps (0.05%) per fill
- Borrow cost: not modeled (long-only)

## Backtest
- Walk-forward: 252 train / 126 test / 126 step
- Fill delay: 1 bar (signal at t, fill at t+1)
- Rebalance threshold: 10% drift
- Initial capital: $100,000

## Robustness
- CPCV: 6 groups, 2 test, 1% embargo
- Deflated Sharpe trials: 1 (single hypothesis)
- Stress: 100 sims crash, 100 sims gap, 20 sims regime shuffle
- Parameter sensitivity: ±20% on 3 key params

## Limitations
- No intraday data (daily bars only)
- No transaction cost for borrow/shorting
- No market impact modeling
- No regime change detection in the data source
- Past performance does not guarantee future results
```

## 6. Gate Thresholds by Config

All gate thresholds are configurable per experiment (see
`validation_gate` section in `docs/EXPERIMENT_CONFIG_SCHEMA.md`). The
defaults above are conservative starting points. A strategy may tighten
thresholds (e.g., `min_oos_sharpe: 0.8`) but may NOT loosen them beyond
the hard ceilings defined in the schema validation rules:

| Threshold | Hard Ceiling | Rationale |
|---|---|---|
| `min_oos_sharpe` | ≥ 0.0 | No negative-Sharpe strategies, ever |
| `max_max_drawdown` | ≤ 0.50 | 50% DD is the absolute survival limit |
| `min_dsr` | ≥ 0.50 | Below 50% is a coin flip, not edge |
| `min_cpcv_pct_positive` | ≥ 0.50 | Majority of paths must be positive |
| `fill_delay` | ≥ 1 | No same-bar execution, ever |

---

**Approval required:** Do not implement until this gate is approved.