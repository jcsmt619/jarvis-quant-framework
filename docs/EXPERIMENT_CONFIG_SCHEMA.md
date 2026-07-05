# Experiment Config Schema

> **Status:** DRAFT — awaiting user approval before implementation.
> **Format:** YAML (one file per experiment under `configs/experiments/`)

---

## 1. Full Schema with Annotations

```yaml
# ─── IDENTITY ───────────────────────────────────────────────────────
strategy_name: hmm_spy_daily          # unique; used as output dir name
strategy_module: strategies.hmm_adapter  # importable module path
strategy_class: HMMAllocationAdapter  # class implementing EdgeStrategy
asset_class: stocks_etfs              # MUST be stocks_etfs (enforced)

# ─── UNIVERSE ───────────────────────────────────────────────────────
symbols:
  - SPY                               # tickers; stocks/ETFs only
#  - QQQ                              # multi-symbol experiments supported

timeframe: 1Day                       # 1Day | 1Hour | 5Min (yfinance)
start_date: "2010-01-01"              # inclusive; data fetch start
end_date: "2025-12-31"                # inclusive; data fetch end

# ─── FEATURES ───────────────────────────────────────────────────────
features_used:                        # subset of FEATURE_COLUMNS
  - logret_1
  - logret_5
  - logret_20
  - realized_vol_20
  - vol_ratio_5_20
  - downside_dev_20
  - vol_asymmetry_20
  - volume_z_50
  - volume_trend_10
  - adx_14
  - sma_slope_50
  - rsi_z_14
  - dist_from_sma_200
  - roc_10
  - roc_20
  - atr_norm_14
standardization_window: 252           # rolling z-score window (causal)

# ─── ENTRY RULES ────────────────────────────────────────────────────
entry_rules:
  # Strategy-specific; the strategy module interprets these.
  # Example for HMM adapter:
  min_confidence: 0.55                # regime probability threshold
  rebalance_threshold: 0.10           # drift trigger for rebalance
  uncertainty_size_mult: 0.50         # size cut when regime unconfirmed

# ─── EXIT RULES ─────────────────────────────────────────────────────
exit_rules:
  stop_type: atr                      # atr | fixed_pct | none
  atr_multiplier: 2.0                 # stop = entry - mult * ATR
  letf_stop_multiplier: 1.5           # wider stop for 3x LETFs
  # Optional runner mode (bank partial, trail rest)
  runner_mode: false
  runner_trigger_r: 1.5
  runner_trail_atr: 2.0

# ─── POSITION SIZING ────────────────────────────────────────────────
position_sizing:
  method: allocation                  # allocation | fixed_frac | kelly
  max_leverage: 1.0                   # gross exposure cap
  initial_capital: 100000.0
  # For allocation method: target_exposure comes from strategy.signal()
  # For fixed_frac: risk_per_trade as fraction of equity
  # For kelly: kelly_fraction (0.5 = half Kelly)

# ─── FEES & SLIPPAGE ────────────────────────────────────────────────
fees:
  commission_per_trade: 0.0           # flat $ per trade (0 = free)
  slippage_bps: 5.0                   # 0.05% per fill (5 basis points)
  # slippage is applied as price * (1 + slippage * sign(delta))
  borrow_cost_bps: 0.0                # daily borrow for shorts (not yet)

# ─── TRAIN / TEST SPLIT ─────────────────────────────────────────────
train_test_split:
  method: walk_forward                # walk_forward | cpcv | single
  train_window: 252                   # bars (trading days for 1Day)
  test_window: 126                    # bars
  step_size: 126                      # non-overlapping by default
  fill_delay: 1                       # signal at t, fill at t+1 (no peek)

# ─── WALK-FORWARD PARAMETERS ────────────────────────────────────────
walk_forward:
  n_candidates: [3, 4, 5]             # HMM state candidates (BIC select)
  n_init: 4                           # EM restarts per candidate
  random_state: 42                    # reproducibility seed
  ensemble_seeds: null                # [42, 43, 44] for seed-ensemble

# ─── BENCHMARK COMPARISON ───────────────────────────────────────────
benchmark:
  buy_hold: true                      # always-on long
  sma200: true                        # 200-SMA trend follower
  random:
    enabled: true
    seeds: 100                        # Monte Carlo random allocations
  # All benchmarks use the SAME covered region + SAME risk rules.

# ─── ROBUSTNESS TESTS ───────────────────────────────────────────────
robustness:
  cpcv:
    enabled: true
    n_groups: 6
    n_test_groups: 2
    embargo_pct: 0.01

  deflated_sharpe:
    enabled: true
    n_trials: 1                       # honest count: how many strategies
                                      # were searched to find this one?
                                      # 1 = no search (single hypothesis)
                                      # 40 = this was 1 of ~40 tried

  stress_tests:
    crash_injection:
      enabled: true
      n_sims: 100
      n_gaps: 10
    gap_risk:
      enabled: true
      n_sims: 100
      n_gaps: 10
    regime_misclassification:
      enabled: true
      n_sims: 20

  parameter_sensitivity:
    enabled: true
    perturbation_pct: 0.20            # ±20% on key params
    params_to_perturb:
      - min_confidence
      - atr_multiplier
      - rebalance_threshold

# ─── VALIDATION GATE ────────────────────────────────────────────────
validation_gate:
  # Criteria from docs/STRATEGY_VALIDATION_GATE.md
  min_oos_sharpe: 0.5                 # absolute floor
  min_dsr: 0.80                       # deflated Sharpe probability
  max_max_drawdown: 0.25              # 25% max DD hard limit
  min_cpcv_pct_positive: 0.60         # 60% of phi paths must be positive
  must_beat_random: true              # must beat random allocation mean
  must_beat_buy_hold: false           # NOT required (edge may be risk-managed)
```

## 2. Required Fields

Every experiment config MUST define all of the following. The config loader
rejects configs with missing or invalid fields.

| Field | Type | Required | Notes |
|---|---|---|---|
| `strategy_name` | str | ✅ | unique identifier, used as output dir |
| `strategy_module` | str | ✅ | importable Python module path |
| `strategy_class` | str | ✅ | class implementing `EdgeStrategy` |
| `asset_class` | str | ✅ | must be `stocks_etfs` |
| `symbols` | list[str] | ✅ | ≥1 ticker; stocks/ETFs only |
| `timeframe` | str | ✅ | `1Day` initially |
| `start_date` | str | ✅ | ISO date, inclusive |
| `end_date` | str | ✅ | ISO date, inclusive |
| `features_used` | list[str] | ✅ | subset of `FEATURE_COLUMNS` |
| `entry_rules` | dict | ✅ | strategy-specific |
| `exit_rules` | dict | ✅ | stop type + multiplier |
| `position_sizing` | dict | ✅ | method + caps |
| `fees` | dict | ✅ | commission + slippage |
| `train_test_split` | dict | ✅ | method + windows |
| `walk_forward` | dict | ✅ | HMM/strategy params |
| `benchmark` | dict | ✅ | at least buy_hold |
| `robustness` | dict | ✅ | CPCV + DSR + stress |
| `validation_gate` | dict | ✅ | pass/fail thresholds |

## 3. Validation Rules (enforced by config loader)

1. `asset_class` must equal `stocks_etfs`. Any other value is rejected.
2. `symbols` must be non-empty. Each symbol is checked against a denylist
   of known crypto/forex tickers (e.g., `BTCUSD`, `EURUSD`).
3. `start_date` must be before `end_date`.
4. `features_used` must be a subset of `data.feature_engineering.FEATURE_COLUMNS`.
5. `fees.slippage_bps` must be ≥ 0 (no negative slippage / free money).
6. `train_test_split.train_window` must be ≥ 126 (6 months daily).
7. `train_test_split.fill_delay` must be ≥ 1 (no same-bar execution).
8. `robustness.deflated_sharpe.n_trials` must be ≥ 1 (honest minimum).
9. `validation_gate.min_oos_sharpe` must be > 0 (no negative-Sharpe strategies).
10. `validation_gate.max_max_drawdown` must be ≤ 0.50 (50% hard ceiling).

## 4. Example Minimal Config

```yaml
strategy_name: ema_rsi_spy_daily
strategy_module: strategies.baseline_ema_rsi
strategy_class: EmaRsiStrategy
asset_class: stocks_etfs
symbols: [SPY]
timeframe: 1Day
start_date: "2010-01-01"
end_date: "2025-12-31"
features_used: [rsi_z_14, dist_from_sma_200, atr_norm_14]
entry_rules:
  ema_fast: 20
  ema_slow: 50
  rsi_oversold: 30
  rsi_overbought: 70
exit_rules:
  stop_type: atr
  atr_multiplier: 2.0
position_sizing:
  method: allocation
  max_leverage: 1.0
  initial_capital: 100000.0
fees:
  commission_per_trade: 0.0
  slippage_bps: 5.0
train_test_split:
  method: walk_forward
  train_window: 252
  test_window: 126
  step_size: 126
  fill_delay: 1
walk_forward:
  random_state: 42
benchmark:
  buy_hold: true
  sma200: true
  random: {enabled: true, seeds: 100}
robustness:
  cpcv: {enabled: true, n_groups: 6, n_test_groups: 2, embargo_pct: 0.01}
  deflated_sharpe: {enabled: true, n_trials: 1}
  stress_tests:
    crash_injection: {enabled: true, n_sims: 100, n_gaps: 10}
    gap_risk: {enabled: true, n_sims: 100, n_gaps: 10}
    regime_misclassification: {enabled: true, n_sims: 20}
  parameter_sensitivity:
    enabled: true
    perturbation_pct: 0.20
    params_to_perturb: [atr_multiplier, rsi_oversold]
validation_gate:
  min_oos_sharpe: 0.5
  min_dsr: 0.80
  max_max_drawdown: 0.25
  min_cpcv_pct_positive: 0.60
  must_beat_random: true
  must_beat_buy_hold: false
```

---

**Approval required:** Do not implement until this schema is approved.