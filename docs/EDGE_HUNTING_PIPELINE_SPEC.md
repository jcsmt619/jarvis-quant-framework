# Edge Hunting Pipeline — Architecture Specification

> **Status:** DRAFT — awaiting user approval before implementation.
> **Scope:** Stocks/ETFs only. No options, no futures, no live trading.
> **Goal:** Find genuine, robust, out-of-sample edges — not maximize return.

---

## 1. Purpose

The edge-hunting pipeline systematically searches for trading edges across
configured strategy experiments, evaluates each one with rigorous walk-forward
backtesting + CPCV + deflated Sharpe, and produces honest reports that surface
both the edge AND its failure modes. The pipeline is a **research tool**, not a
trading system — it never places orders, never connects to a broker, and never
optimizes for highest return.

## 2. Design Principles

1. **Honesty over performance.** Every experiment reports what it found AND
   where it breaks. A strategy that fails robustness tests is reported as
   failed, not hidden.
2. **No look-ahead bias.** All features, signals, and labels are causal. The
   existing `tests/test_look_ahead.py` gate is extended to cover every new
   strategy before it enters the pipeline.
3. **Deflation by default.** Every Sharpe is deflated by the number of trials
   searched. A raw Sharpe of 2.0 found after 300 trials is reported as
   statistically meaningless unless DSR ≥ 0.95.
4. **Reproducibility.** Every experiment is fully specified by its config file
   and a random seed. Re-running the same config produces the same output.
5. **Separation of concerns.** Strategy logic, backtest infrastructure,
   validation, and reporting are independent modules. A new strategy plugs in
   via a standard interface; the pipeline does not change.
6. **Stocks/ETFs only.** The pipeline enforces `asset_class: stocks_etfs` and
   rejects configs that reference options, futures, crypto, or forex.

## 3. Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EDGE HUNTING PIPELINE                            │
│                                                                     │
│  1. LOAD CONFIG                                                      │
│     configs/experiments/{name}.yaml                                  │
│     → validate schema, enforce asset_class, check data availability  │
│                                                                     │
│  2. FETCH / LOAD DATA                                                │
│     → yfinance (or local CSV cache in data/raw/)                     │
│     → enforce start/end dates, timeframe, symbol list                │
│     → OHLCV only; no fundamental/alt-data yet                        │
│                                                                     │
│  3. BUILD FEATURES                                                   │
│     → data/feature_engineering.build_features() (existing, causal)   │
│     → config specifies which feature columns to use                  │
│     → rolling z-score standardization (252-bar, causal)              │
│                                                                     │
│  4. GENERATE SIGNALS                                                 │
│     → strategy module produces {target_exposure: float, stop: float} │
│     → signals are SHIFTED by fill_delay bars (no same-bar execution) │
│     → look-ahead gate: test_signals_no_lookahead() must pass         │
│                                                                     │
│  5. WALK-FORWARD BACKTEST                                            │
│     → backtest/backtester.py WalkForwardBacktester (existing)        │
│     → train/test windows from config; slippage + commission applied  │
│     → equity curve, trade log, regime history recorded               │
│                                                                     │
│  6. BENCHMARK COMPARISON                                             │
│     → buy & hold, 200-SMA trend follower, random allocation control  │
│     → all benchmarks use SAME covered region + SAME risk rules       │
│                                                                     │
│  7. ROBUSTNESS BATTERY                                               │
│     → CPCV (backtest/cpcv.py): Sharpe distribution across phi paths  │
│     → Deflated Sharpe (backtest/deflated_sharpe.py): DSR verdict     │
│     → Stress tests (backtest/stress_test.py): crash, gap, regime     │
│     → Parameter sensitivity: ±20% on key params, re-run              │
│                                                                     │
│  8. REPORT GENERATION                                                │
│     → reports/experiments/{strategy_name}/                           │
│        metrics.json, trades.csv, equity_curve.csv,                   │
│        drawdown.csv, assumptions.md, failure_reasons.md              │
│                                                                     │
│  9. VALIDATION GATE                                                  │
│     → docs/STRATEGY_VALIDATION_GATE.md criteria checked              │
│     → PASS → eligible for paper trading (separate system)            │
│     → FAIL → failure_reasons.md documents why                        │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. Module Map (what exists vs. what's new)

| Component | Status | Module |
|---|---|---|
| Feature engineering | **exists** | `data/feature_engineering.py` |
| Walk-forward backtester | **exists** | `backtest/backtester.py` |
| Performance metrics | **exists** | `backtest/performance.py` |
| CPCV (purged CV) | **exists** | `backtest/cpcv.py` |
| Deflated Sharpe | **exists** | `backtest/deflated_sharpe.py` |
| Stress tests | **exists** | `backtest/stress_test.py` |
| Triple-barrier labeling | **exists** | `backtest/triple_barrier.py` |
| Data fetcher | **exists** | `data_fetcher.py` (yfinance + Alpaca) |
| Strategy base interface | **new** | `strategies/base.py` (abstract) |
| Experiment config loader | **new** | `edge_hunting/config_loader.py` |
| Experiment runner | **new** | `edge_hunting/runner.py` |
| Report writer | **new** | `edge_hunting/reporter.py` |
| Validation gate checker | **new** | `edge_hunting/gate.py` |
| CLI entry point | **new** | `edge_hunting/__main__.py` |

**Key principle:** the pipeline orchestrates existing modules. It does NOT
rewrite the backtester, CPCV, or deflated Sharpe — it wires them together with
a config-driven runner and a report writer.

## 5. Strategy Interface

Every strategy implements a minimal interface so the pipeline can run it
without knowing its internals:

```python
class EdgeStrategy(ABC):
    """A strategy's signal generator. Pure function of features + price."""

    @abstractmethod
    def fit(self, train_features: pd.DataFrame, train_close: pd.Series) -> None:
        """Train on the in-sample slice. No future data."""

    @abstractmethod
    def signal(self, bar_idx: int, features: pd.DataFrame,
               close: pd.Series) -> Signal:
        """Return target exposure + stop for bar `bar_idx`.
        Uses only data at or before `bar_idx`. Called bar-by-bar on OOS."""

    @property
    @abstractmethod
    def name(self) -> str: ...
```

The existing HMM allocation strategy (`core/hmm_engine.py` +
`core/regime_strategies.py`) will be wrapped as an `EdgeStrategy` adapter —
its logic is NOT modified, only wrapped.

## 6. Experiment Execution Flow

```
runner.run_experiment(config_path) → ExperimentReport

  1. Load + validate config (schema, asset_class, data availability)
  2. Fetch/load OHLCV for all symbols in config
  3. Build features (config-specified subset of FEATURE_COLUMNS)
  4. For each walk-forward window:
     a. Split train/test by config dates + window sizes
     b. strategy.fit(train_features, train_close)
     c. Walk OOS bar-by-bar: strategy.signal() → target_exposure
     d. Simulate with slippage + commission (existing _simulate)
  5. Compute metrics (existing performance.compute_metrics)
  6. Run benchmarks (buy&hold, SMA200, random) on same covered region
  7. Run robustness battery:
     a. CPCV: phi paths → Sharpe distribution
     b. Deflated Sharpe: DSR with honest trial count
     c. Stress: crash injection, gap risk, regime misclassification
     d. Parameter sensitivity: ±20% grid on top-3 params
  8. Write reports to reports/experiments/{name}/
  9. Run validation gate → PASS/FAIL verdict
```

## 7. Output Directory Structure

```
reports/experiments/{strategy_name}/
├── metrics.json              # all metrics + benchmarks + robustness summary
├── trades.csv                # one row per closed trade
├── equity_curve.csv          # date, equity, target, close
├── drawdown.csv              # date, drawdown_pct, underwater_bars
├── assumptions.md            # what was assumed (fees, slippage, data source)
├── failure_reasons.md        # what broke (or "none" if gate passed)
├── cpcv_sharpe_distribution.csv   # phi path Sharpes (robustness)
├── stress_test_summary.json       # crash/gap/regime stress results
└── config_snapshot.yaml           # the exact config that produced this run
```

## 8. What the Pipeline Does NOT Do

- ❌ No live trading (no broker connection, no order submission)
- ❌ No return optimization (no hyperparameter search for max Sharpe)
- ❌ No options or futures (enforced by config schema)
- ❌ No crypto or forex (enforced by asset_class check)
- ❌ No modification of existing strategy logic (adapter pattern only)
- ❌ No modification of existing backtest/validation modules (orchestration only)

## 9. Constraints Enforced by the Pipeline

| Constraint | How enforced |
|---|---|
| Stocks/ETFs only | Config schema rejects `asset_class != stocks_etfs` |
| No look-ahead | `test_signals_no_lookahead()` gate before backtest |
| Deflation | DSR computed with honest trial count; reported in metrics.json |
| Reproducibility | Random seed in config; all stochastic ops seeded |
| Data integrity | Fetcher verifies OHLCV columns, date range, no NaN gaps |
| Fee/slippage realism | Config specifies both; defaults are conservative |

## 10. Initial Experiment Set (proposed, not yet implemented)

| Experiment | Strategy | Symbols | Timeframe | Period |
|---|---|---|---|---|
| `hmm_spy_daily` | HMM regime allocation | SPY | 1Day | 2010-2025 |
| `hmm_soxl_daily` | HMM regime allocation | SOXL | 1Day | 2010-2025 |
| `ema_rsi_spy_daily` | EMA+RSI baseline | SPY | 1Day | 2010-2025 |
| `momentum_spy_daily` | ROC momentum | SPY, QQQ | 1Day | 2010-2025 |

Each experiment config lives at `configs/experiments/{name}.yaml` and follows
the schema in `docs/EXPERIMENT_CONFIG_SCHEMA.md`.

---

**Approval required:** Do not implement until this architecture is approved.