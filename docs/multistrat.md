# Multi-Strategy Mode

Run several strategies at once, let a capital allocator split money between them
on a schedule, and put a portfolio-wide risk layer on top. Both the per-strategy
risk manager **and** the portfolio risk manager hold absolute veto power — an
order reaches the executor only if both approve.

```
data → features → [strategy_1, strategy_2, …] → allocator → portfolio_risk → executor
```

---

## Overview: why multi-strat

A single strategy is a single point of failure. It has one edge, one regime it
likes, and one way to blow up. Running several *uncorrelated* strategies:

- **Smooths equity** — drawdowns rarely line up, so the portfolio curve is calmer.
- **Raises risk-adjusted return** — diversification lifts Calmar/Sharpe even when
  each strategy is mediocre on its own.
- **Fails gracefully** — if one strategy breaks, health checks disable it and the
  allocator moves its capital to the survivors instead of taking the whole book down.

The catch: diversification only helps if the strategies are *actually* different.
Two strategies that are secretly the same just double your position size. The
allocator's correlation merge (below) is the defense against that.

---

## How to add a new strategy (5-minute walkthrough)

**1. Write the engine.** Subclass `BaseStrategy` and register it. The registry
decorator wires it into the process-wide registry on import.

```python
# core/registered_strategies.py
from core.strategy_registry import register_strategy
from core.regime_strategies import BaseStrategy
from core.risk_manager import TradeSignal

@register_strategy("my_strategy")
class MyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        # single-asset allocation hook (used by the walk-forward backtester)
        ...

    def generate_signals(self, bars, regime_state):
        # LIVE hook: return a list of core.risk_manager.TradeSignal.
        # A stop_loss is MANDATORY — the risk manager rejects orders without one.
        return [TradeSignal(symbol="SPY", direction=1, asset_class="equity",
                            price=..., atr=..., stop_loss=...)]
```

**2. Configure it** in `config/settings.yaml` under `strategies:`. Nothing is
hardcoded — enablement, symbols and weight bounds all live here.

```yaml
strategies:
  my_strategy:
    enabled: true
    symbols: [SPY]
    weight_min: 0.05      # never gets less than 5% of trading capital
    weight_max: 0.40      # never gets more than 40%
```

**3. Run it.** No code change needed to activate:

```powershell
python main.py backtest --multi-strat --start 2018-01-01 --end 2024-12-31 --compare
python main.py live --dry-run --multi-strat
```

**4. Verify.** Check the CSVs in `logs/multistrat/` (backtest) and the
`MULTI-STRAT ALLOCATIONS` dashboard panel (live). The guiding question is always:
*does the multi-strat portfolio have a better Calmar than the best single
strategy?* If not, the complexity isn't paying for itself.

---

## Allocator approaches compared

Set with `allocator.approach` in settings, or `--allocator` on the CLI.

| Approach | Weight rule | Best when | Watch out for |
|---|---|---|---|
| `equal_weight` | 1/N | You have no reliable vol/return estimates | Ignores that one strategy may be 5× riskier |
| `inverse_vol` *(default)* | wᵢ ∝ 1/volᵢ | Strategies have very different volatilities | A low-vol dud can hoard capital |
| `risk_parity` | Equalize each strategy's contribution to portfolio variance | You care about balanced *risk*, not balanced *capital* | Needs a stable covariance estimate; falls back to inverse-vol if the solver struggles |
| `performance_weighted` | wᵢ ∝ max(Sharpeᵢ, 0) | Recent performance is persistent | Chases hot hands; overfits to the last 60 days |

On top of **every** approach the allocator applies, in order:

1. **Correlation merge** — pairs with rolling correlation above
   `corr_merge_threshold` (default 0.80) are treated as **one** strategy for
   weighting, then that group's weight is split evenly. This stops two
   near-identical strategies from getting double the intended exposure.
2. **Constraints** — each strategy's `weight_min`/`weight_max`, weights re-normalized to sum to 1.
3. **Reserve** — a cash buffer (`reserve`, default 10%) is always held back, so
   deployed capital is `1 − reserve`.
4. **Kill switch** — portfolio daily drawdown > 2% halves all sizes; > 3% zeros them.

---

## Common pitfalls

### Two strategies that are secretly the same
High correlation (> 0.80) means you don't have two strategies — you have one
strategy at 2× size. The allocator's correlation merge collapses them so they
share a single slot, and a `CORRELATION_CLUSTER` alert fires. If you *keep*
seeing merges, your "diversification" is an illusion; replace one of them.

### Strategies overfit to recent data (auto-disable kicks in too late)
Health checks disable a strategy after it has *already* breached a limit
(drawdown > 15%, 60-day Sharpe < −1.0, or ≥ 10 consecutive losing days). That is
by design — it reacts to *realized* damage, not predicted damage. If a strategy
was curve-fit to the last year, it can still lose 15% before the circuit trips.
The fix is upstream: validate with walk-forward out-of-sample data before
enabling, not tighter health thresholds.

### Allocator over-fitting to the backtest
`performance_weighted` and, to a lesser extent, `risk_parity` can latch onto
whatever worked in the sample window. If your multi-strat Calmar only beats the
best single strategy under one specific approach + window, you've fit the
allocator to noise. Prefer `inverse_vol` or `equal_weight` unless a diversified
edge survives across approaches **and** across walk-forward windows.

---

## FAQ

**Why is one strategy always at minimum weight?**
It probably has high volatility (under `inverse_vol`) or a low/negative recent
Sharpe (under `performance_weighted`), so the approach keeps starving it — and
`weight_min` is the only thing keeping it funded at all. Check its vol and
60-day Sharpe in `logs/allocator.jsonl`.

**Why didn't the allocator rebalance?**
Either it isn't a scheduled run yet (default cadence is weekly), or the target
weight change was smaller than `rebalance_threshold` (default 0.05). The
allocator deliberately ignores sub-threshold drift to avoid churning turnover.

**Why is a strategy disabled?**
A health check failed. The reason (drawdown / Sharpe / losing streak) is written
to the structured logs and emitted as a `STRATEGY_DISABLED` alert — grep
`logs/alerts.jsonl` (and `logs/trading.jsonl` for the `strategy_disabled`
record). A disabled strategy gets 0 capital on the allocator's next pass and is
excluded until it is re-enabled.
