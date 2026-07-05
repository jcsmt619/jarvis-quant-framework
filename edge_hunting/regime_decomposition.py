"""
edge_hunting/regime_decomposition.py
========================================
Regime decomposition for the 7 slippage-stress-surviving paper-trading-
eligible candidates identified in docs/JARVIS_EDGE_HUNTING_ANALYSIS.md
Section 12:

    MSFT keltner_revert, AMZN keltner_revert, EEM rsi_revert(14,30/70),
    EEM rsi_revert(14,25/70), SPY dual_momentum(60,126),
    HYG dual_momentum(126,126), QQQ rsi_revert(14,30/75)

Rules followed
--------------
- No parameter tuning, no strategy-logic changes, no entry/exit rule
  changes, no funnel threshold changes.
- Does NOT rerun the full sweep -- reuses the existing, unmodified
  edge_hunting.walk_forward.run_walk_forward engine at its default 1bp cost
  (the same baseline cost used by the original sweep) to get each
  candidate's OOS returns/position series, then decomposes those OOS
  returns by regime. No new backtest logic; this is pure post-hoc
  attribution of results that were already being produced.
- Uses only the existing on-disk cached data (edge_hunting.data_loader).
- Regime labels are DESCRIPTIVE/analytical only (used to slice already-
  computed OOS returns for reporting) -- they are not fed back into any
  strategy signal, so this has no bearing on the look-ahead/anti-lookahead
  contract enforced by edge_hunting.backtest_engine.compute_position.
- Nothing is promoted to paper trading here; this is diagnostic only.

Regime labeling methodology
----------------------------
Six regimes, one label per trading day, assigned by priority (a day cannot
be in two regimes at once -- crisis takes priority over vol takes priority
over trend, since a crash is definitionally both high-vol and often
trend-breaking):

1. CRISIS       : drawdown from trailing 252-day peak <= -20%
2. HIGH_VOL     : (not crisis) and 60-day realized vol (annualized) is in
                   the asset's own top quartile (>= 75th percentile)
3. LOW_VOL      : (not crisis, not high-vol) and 60-day realized vol is in
                   the asset's own bottom quartile (<= 25th percentile)
4. BULL         : (none of the above) and trailing 60-day return > +5%
5. BEAR         : (none of the above) and trailing 60-day return < -5%
6. SIDEWAYS     : everything else (trailing 60-day return in [-5%, +5%],
                   normal vol)

Vol/return thresholds are computed per-asset from that asset's own full
history (simple descriptive quantiles, not a tuned strategy parameter).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edge_hunting import data_loader
from edge_hunting.backtest_engine import TRADING_DAYS, _max_drawdown, _sharpe, _trade_count
from edge_hunting.strategy_library import STRATEGY_REGISTRY
from edge_hunting.walk_forward import run_walk_forward

OUT_DIR = Path("reports/edge_hunting")

CANDIDATES = [
    ("MSFT", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "keltner_revert__window20_atr_mult2.0"),
    ("AMZN", "keltner_revert", {"window": 20, "atr_mult": 2.0}, "keltner_revert__window20_atr_mult2.0"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 70}, "rsi_revert__window14_oversold30_overbought70"),
    ("EEM", "rsi_revert", {"window": 14, "oversold": 25, "overbought": 70}, "rsi_revert__window14_oversold25_overbought70"),
    ("SPY", "dual_momentum", {"window": 60, "rel_window": 126}, "dual_momentum__window60_rel_window126"),
    ("HYG", "dual_momentum", {"window": 126, "rel_window": 126}, "dual_momentum__window126_rel_window126"),
    ("QQQ", "rsi_revert", {"window": 14, "oversold": 30, "overbought": 75}, "rsi_revert__window14_oversold30_overbought75"),
]

REGIMES = ["CRISIS", "HIGH_VOL", "LOW_VOL", "BULL", "BEAR", "SIDEWAYS"]


def label_regimes(df: pd.DataFrame) -> pd.Series:
    """Assign one of the 6 regime labels to every day in df, by priority."""
    close = df["Close"]
    daily_ret = close.pct_change()
    trail_ret_60 = close.pct_change(60)
    vol_60 = daily_ret.rolling(60).std() * np.sqrt(TRADING_DAYS)
    rolling_peak_252 = close.rolling(252, min_periods=1).max()
    drawdown = (close - rolling_peak_252) / rolling_peak_252

    vol_hi = vol_60.quantile(0.75)
    vol_lo = vol_60.quantile(0.25)

    label = pd.Series(index=df.index, dtype=object)
    label[:] = "SIDEWAYS"

    is_bull = trail_ret_60 > 0.05
    is_bear = trail_ret_60 < -0.05
    is_high_vol = vol_60 >= vol_hi
    is_low_vol = vol_60 <= vol_lo
    is_crisis = drawdown <= -0.20

    label[is_bull] = "BULL"
    label[is_bear] = "BEAR"
    label[is_low_vol] = "LOW_VOL"
    label[is_high_vol] = "HIGH_VOL"
    label[is_crisis] = "CRISIS"  # highest priority, applied last

    return label


def _regime_metrics(returns: pd.Series, position: pd.Series) -> dict:
    if len(returns) == 0:
        return {
            "oos_sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0,
            "trade_count": 0, "exposure": 0.0, "turnover": 0.0, "n_days": 0,
        }
    equity = (1.0 + returns).cumprod()
    return {
        "oos_sharpe": _sharpe(returns.to_numpy()),
        "total_return": float(equity.iloc[-1] - 1.0),
        "max_drawdown": _max_drawdown(equity.to_numpy()),
        "trade_count": _trade_count(position),
        "exposure": float((position != 0).mean()),
        "turnover": float(position.diff().abs().fillna(0.0).sum()),
        "n_days": len(returns),
    }


def _classify(regime_rows: list[dict]) -> tuple[str, str, str, bool]:
    """Return (classification, best_regime, worst_regime, concentrated)."""
    # Only consider regimes with a meaningful number of OOS days present.
    populated = [r for r in regime_rows if r["n_days"] >= 10]
    if not populated:
        return "INSUFFICIENT_DATA", "n/a", "n/a", True

    by_sharpe = sorted(populated, key=lambda r: r["oos_sharpe"])
    worst = by_sharpe[0]
    best = by_sharpe[-1]

    positive = [r for r in populated if r["oos_sharpe"] > 0]
    # Concentrated: only one (or zero) regime is positive, or one regime's
    # total_return dominates (>=80%) the sum of all positive-return regimes.
    concentrated = len(positive) <= 1
    if not concentrated and positive:
        total_pos_return = sum(max(r["total_return"], 0.0) for r in positive)
        if total_pos_return > 0:
            top = max(positive, key=lambda r: r["total_return"])
            if top["total_return"] / total_pos_return >= 0.80:
                concentrated = True

    stress_regimes = [r for r in populated if r["regime"] in ("BEAR", "HIGH_VOL", "CRISIS")]
    collapses_in_stress = any(r["oos_sharpe"] <= 0 for r in stress_regimes)

    if collapses_in_stress and (concentrated or len(positive) <= 2):
        classification = "REGIME_FRAGILE"
    elif concentrated:
        classification = "REGIME_DEPENDENT"
    else:
        classification = "REGIME_ROBUST"

    return classification, best["regime"], worst["regime"], concentrated


def main():
    assets_needed = sorted({a for a, _, _, _ in CANDIDATES})
    print(f"Loading assets from cache: {assets_needed}")
    universe = data_loader.load_universe(symbols=assets_needed)

    rows = []
    summary_rows = []

    for asset, family, params, display_name in CANDIDATES:
        if asset not in universe:
            print(f"SKIP {asset} {display_name}: data unavailable")
            continue
        df = universe[asset]
        fn, _, _ = STRATEGY_REGISTRY[family]

        # Baseline 1bp cost -- identical to the original sweep's assumption;
        # this call is unmodified/reused, not a new backtest methodology.
        wf = run_walk_forward(df, fn, params, cost_bps=1.0)

        regime_labels = label_regimes(df)
        regime_labels_aligned = regime_labels.reindex(wf.oos_returns.index)

        regime_rows_for_candidate = []
        for regime in REGIMES:
            mask = regime_labels_aligned == regime
            r_returns = wf.oos_returns[mask]
            r_position = wf.oos_position[mask]
            m = _regime_metrics(r_returns, r_position)
            m["regime"] = regime
            regime_rows_for_candidate.append(m)
            rows.append({
                "asset": asset,
                "strategy_name": display_name,
                "regime": regime,
                **m,
            })

        classification, best_regime, worst_regime, concentrated = _classify(regime_rows_for_candidate)
        for r in rows[-len(REGIMES):]:
            r["classification"] = classification
            r["best_regime"] = best_regime
            r["worst_regime"] = worst_regime
            r["concentrated_in_one_regime"] = concentrated

        summary_rows.append({
            "asset": asset,
            "strategy_name": display_name,
            "overall_oos_sharpe": wf.oos_sharpe,
            "best_regime": best_regime,
            "worst_regime": worst_regime,
            "concentrated_in_one_regime": concentrated,
            "classification": classification,
        })

        print(f"{asset:6s} {display_name:50s} overall_sharpe={wf.oos_sharpe:+.3f} "
              f"best={best_regime:10s} worst={worst_regime:10s} "
              f"concentrated={concentrated} -> {classification}")
        for m in regime_rows_for_candidate:
            print(f"    {m['regime']:10s} n={m['n_days']:4d} sharpe={m['oos_sharpe']:+.3f} "
                  f"ret={m['total_return']:+.3f} dd={m['max_drawdown']:+.3f} "
                  f"trades={m['trade_count']:3d} exposure={m['exposure']:.2f} turnover={m['turnover']:.1f}")

    out_df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "regime_decomposition.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv} ({len(out_df)} rows)")

    return out_df, pd.DataFrame(summary_rows)


if __name__ == "__main__":
    main()
