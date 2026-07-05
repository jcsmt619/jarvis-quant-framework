"""
edge_hunting/parameter_grid.py
================================
Builds the full list of StrategyConfig objects (name, function, params,
category, description) from small per-family parameter grids defined
below. Combined with the ~30-asset universe this produces a sweep in the
hundreds-of-configs / thousands-of-backtests range, per spec.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

from edge_hunting.strategy_library import STRATEGY_REGISTRY


@dataclass
class StrategyConfig:
    name: str
    function: Callable
    params: dict[str, Any]
    category: str
    description: str
    family: str = field(default="")

    def __post_init__(self):
        if not self.family:
            self.family = self.name.split("__")[0]


# ---------------------------------------------------------------------------
# Small grids per family. Kept intentionally small ("small but meaningful")
# -- combinatorics across ~47 families already yields hundreds of configs.
# ---------------------------------------------------------------------------
FAMILY_GRIDS: dict[str, dict[str, list]] = {
    "ma_crossover": {"fast": [10, 20], "slow": [50, 100]},
    "ts_momentum": {"window": [20, 60, 120]},
    "roc_momentum": {"window": [20, 60], "threshold": [0.0, 0.02]},
    "macd": {"fast": [12], "slow": [26], "signal": [9]},
    "donchian_breakout": {"window": [20, 55]},
    "bollinger_breakout": {"window": [20], "num_std": [2.0, 2.5]},
    "supertrend": {"window": [10, 14], "mult": [2.0, 3.0]},
    "parabolic_sar": {"step": [0.02], "max_step": [0.2]},
    "adx_trend": {"window": [14], "adx_threshold": [20, 25]},
    "ichimoku": {"tenkan": [9], "kijun": [26], "senkou_b": [52]},
    "linreg_slope": {"window": [20, 60]},
    "aroon": {"window": [14, 25]},
    "vortex": {"window": [14, 21]},
    "trix": {"window": [15, 30]},
    "hull_ma": {"window": [20, 55]},
    "kama": {"window": [10], "fast": [2], "slow": [30]},
    "turtle_breakout": {"entry_window": [20, 55], "exit_window": [10, 20]},
    "dual_momentum": {"window": [60, 126], "rel_window": [126]},
    "elder_ray": {"window": [13, 21]},
    "rsi_revert": {"window": [7, 14], "oversold": [25, 30], "overbought": [70, 75]},
    "bollinger_revert": {"window": [20], "num_std": [2.0, 2.5]},
    "zscore_revert": {"window": [20, 60], "threshold": [1.5, 2.0]},
    "stochastic_revert": {"window": [14], "oversold": [20], "overbought": [80]},
    "cci_revert": {"window": [20], "threshold": [100, 150]},
    "williams_r_revert": {"window": [14], "oversold": [-80], "overbought": [-20]},
    "keltner_revert": {"window": [20], "atr_mult": [2.0]},
    "vwap_revert": {"window": [20], "threshold": [0.01, 0.02]},
    "percent_b_revert": {"window": [20], "lower": [0.05], "upper": [0.95]},
    "connors_rsi_revert": {"rsi_window": [3], "streak_window": [2], "rank_window": [100]},
    "ultimate_oscillator_revert": {"w1": [7], "w2": [14], "w3": [28]},
    "gap_fade": {"threshold": [0.01, 0.02]},
    "obv_trend": {"window": [20, 50]},
    "chaikin_money_flow": {"window": [20], "threshold": [0.0, 0.05]},
    "money_flow_index": {"window": [14], "oversold": [20], "overbought": [80]},
    "volume_surge": {"window": [20], "mult": [2.0, 3.0]},
    "force_index": {"window": [13]},
    "chaikin_oscillator": {"fast": [3], "slow": [10]},
    "atr_breakout": {"window": [14, 20], "mult": [1.5, 2.0]},
    "volatility_breakout": {"window": [20], "mult": [2.0]},
    "squeeze_breakout": {"window": [20], "num_std": [2.0], "atr_mult": [1.5]},
    "engulfing": {},
    "three_bar_reversal": {},
    "higher_highs_lower_lows": {"window": [10, 20]},
    "pivot_bounce": {"window": [5, 10], "tolerance": [0.01]},
    "macd_rsi_confirm": {"fast": [12], "slow": [26], "signal": [9], "rsi_window": [14]},
    "triple_screen": {"trend_window": [50], "rsi_window": [14], "oversold": [40], "overbought": [60]},
    "chandelier_exit": {"window": [22], "mult": [3.0], "trend_window": [50]},
}


def _grid_combinations(grid: dict[str, list]) -> list[dict]:
    if not grid:
        return [{}]
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    return [dict(zip(keys, combo)) for combo in combos]


def build_strategy_configs() -> list[StrategyConfig]:
    configs: list[StrategyConfig] = []
    for family, (fn, category, description) in STRATEGY_REGISTRY.items():
        grid = FAMILY_GRIDS.get(family, {})
        for params in _grid_combinations(grid):
            param_str = "_".join(f"{k}{v}" for k, v in params.items())
            name = f"{family}__{param_str}" if param_str else family
            configs.append(StrategyConfig(
                name=name, function=fn, params=dict(params),
                category=category, description=description, family=family,
            ))
    return configs


def summarize(configs: list[StrategyConfig], n_assets: int) -> str:
    by_cat: dict[str, int] = {}
    for c in configs:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
    lines = [
        f"Total strategy configs generated: {len(configs)}",
        f"Assets in universe: {n_assets}",
        f"Expected total backtests: {len(configs) * n_assets}",
        "By category:",
    ]
    for cat, n in sorted(by_cat.items()):
        lines.append(f"  {cat}: {n}")
    return "\n".join(lines)


if __name__ == "__main__":
    cfgs = build_strategy_configs()
    print(summarize(cfgs, n_assets=27))
