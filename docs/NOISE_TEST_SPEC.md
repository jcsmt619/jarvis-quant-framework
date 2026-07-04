# Noise Test — Architecture Specification

> **Status:** DRAFT — awaiting user approval before implementation.
> **Origin:** `docs/SKOOL_VS_JARVIS_IMPLEMENTATION_AUDIT.md`, Finding 6 (Missing).
> **Goal:** Add an explicit statistical check that a strategy's edge is
> distinguishable from noise, not just "a strategy that passed CPCV."

---

## 1. Purpose

Every current validation layer (`backtest/cpcv.py`, `backtest/deflated_sharpe.py`,
`backtest/triple_barrier.py`) asks "is this result robust across resampled
paths of the REAL data?" None of them ask the more basic question: "would a
strategy with a similarly-shaped signal have produced a similarly good result
on data that contains no exploitable structure at all?"

The Skool curriculum calls this "the real reason most discovered edges are
fake" — a strategy can survive walk-forward + CPCV + deflated Sharpe purely
because the specific historical path it was tuned on happened to reward its
particular rules, not because the rules encode genuine structure.

This spec adds a **noise test**: run the exact same strategy + pipeline
against N synthetic random walks matching the real asset's return moments,
and report where the real result falls in that noise distribution.

## 2. Design Principles

1. **Same pipeline, different data.** The noise test does NOT reimplement
   backtesting logic. It reuses `backtest/backtester.py`'s
   `WalkForwardBacktester` and the strategy's existing `signal()`/`fit()`
   interface unchanged.
2. **Matched moments, not matched structure.** Synthetic series match the
   real asset's mean, volatility, and (optionally) lag-1 autocorrelation, but
   contain no genuine multi-day/cyclical exploitable pattern by construction.
3. **Distributional verdict, not pass/fail on a single number.** The output
   is a full distribution of noise-Sharpes (and noise-Calmars), so the real
   result's percentile rank is reported, not a single boolean.
4. **Reproducibility.** All random walk generation is seeded; re-running the
   same config produces the same noise distribution.
5. **No change to existing strategy or backtest logic.** This is purely an
   additional read-only validation stage.

## 3. What "noise" means here

Two synthetic-data generators, selectable per experiment config:

| Generator | Method | Preserves |
|---|---|---|
| `gaussian_walk` | i.i.d. Gaussian daily returns, mean/std matched to real series | mean, volatility |
| `block_bootstrap_shuffled` | Block-bootstrap the REAL daily returns (block length ~20 bars) then randomly reorder the blocks | marginal return distribution + short-run autocorrelation within a block, but destroys the actual chronological sequence/trend/regime structure the strategy might be keying off |

`block_bootstrap_shuffled` is the harder, more honest test — it keeps the
exact same historical return distribution (fat tails, vol clustering) but
scrambles the calendar-time structure a regime/trend strategy would need.
`gaussian_walk` is a simpler sanity baseline. Both should be run.

## 4. Module Map (what exists vs. what's new)

| Component | Status | Module |
|---|---|---|
| Walk-forward backtester | **exists (reused unchanged)** | `backtest/backtester.py` |
| Performance metrics | **exists (reused unchanged)** | `backtest/performance.py` |
| Synthetic series generator | **new** | `backtest/noise_test.py` |
| Noise distribution report writer | **new** | `backtest/noise_test.py` (same module) |
| CLI/report integration | **new** | wired into `edge_hunting/runner.py` robustness battery (step 7) as an additional item, and/or `main.py --stress-test` |

## 5. Proposed Interface

```python
# backtest/noise_test.py

@dataclass
class NoiseTestResult:
    real_sharpe: float
    real_calmar: float
    noise_sharpes: np.ndarray       # shape (n_sims,)
    noise_calmars: np.ndarray
    sharpe_percentile: float        # where real_sharpe ranks vs noise distribution
    calmar_percentile: float
    generator: str                  # "gaussian_walk" | "block_bootstrap_shuffled"
    n_sims: int
    verdict: str                    # "DISTINGUISHABLE_FROM_NOISE" | "INDISTINGUISHABLE_FROM_NOISE"

def generate_gaussian_walk(real_close: pd.Series, seed: int) -> pd.Series: ...
def generate_block_bootstrap(real_close: pd.Series, block_len: int, seed: int) -> pd.Series: ...

def run_noise_test(
    strategy_factory: Callable[[], "EdgeStrategy"],
    bt: WalkForwardBacktester,
    real_close: pd.Series,
    generator: str = "block_bootstrap_shuffled",
    n_sims: int = 200,
    percentile_threshold: float = 95.0,
) -> NoiseTestResult:
    """Run `bt` against n_sims synthetic series using a FRESH strategy instance
    each time (no state leaks from the real run), collect Sharpe/Calmar,
    and report the real result's percentile rank against that distribution."""
```

**Verdict rule (proposed, tune-able):** `DISTINGUISHABLE_FROM_NOISE` only if
`real_sharpe` is at or above the `percentile_threshold`-th percentile (default
95th) of the noise distribution. Anything below is
`INDISTINGUISHABLE_FROM_NOISE` — a hard signal that the strategy's edge could
plausibly be a historical-path artifact, and the validation gate
(`docs/STRATEGY_VALIDATION_GATE.md`) should treat this as a blocking failure,
not a soft warning.

## 6. Output

Extends the existing `reports/experiments/{name}/` structure (see
`docs/EDGE_HUNTING_PIPELINE_SPEC.md` §7) with:

```
reports/experiments/{strategy_name}/
├── noise_test_gaussian.json          # NoiseTestResult, generator=gaussian_walk
├── noise_test_block_bootstrap.json   # NoiseTestResult, generator=block_bootstrap_shuffled
└── noise_test_sharpe_distribution.csv  # raw per-sim Sharpe/Calmar for plotting
```

## 7. Integration with the validation gate

`docs/STRATEGY_VALIDATION_GATE.md` should add a new gate criterion:
"Noise test: real Sharpe >= 95th percentile of block-bootstrap-shuffled noise
distribution (n_sims >= 200)." A strategy that fails CPCV/DSR but passes the
noise test, or vice versa, is still reported honestly — both are independent
checks, and the gate should require **both** to pass, not either/or.

## 8. What this does NOT do

- ❌ Does not modify `backtest/backtester.py`, `backtest/cpcv.py`, or
  `backtest/deflated_sharpe.py` — pure addition.
- ❌ Does not change any existing strategy's `fit()`/`signal()` logic — the
  noise test calls the strategy through the exact same interface as a normal
  backtest run.
- ❌ Does not touch live/paper execution in any way.
- ❌ Does not replace CPCV/DSR — it is a complementary, orthogonal check.

## 9. Effort estimate

Low-medium. `generate_gaussian_walk` and `generate_block_bootstrap` are
~20-30 lines each. `run_noise_test` orchestrates the existing backtester in a
loop — no new simulation logic. The main design decision requiring your
approval is the verdict threshold (95th percentile default) and whether the
gate should hard-block on failure or just flag it.

---

**Approval required:** Do not implement until this architecture is approved.
