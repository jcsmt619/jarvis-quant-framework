"""
core/registered_strategies.py
=============================
The concrete strategy engines that self-register into the process-wide registry.
Importing this module wires them into `get_registry()`. Per-strategy enablement,
symbols and weight bounds are driven from config/settings.yaml (no magic numbers).

These are thin engine shells for the parallel-strategy framework; the mean
reversion one is an intentional stub (disabled by default in settings.yaml).
"""

from __future__ import annotations

from pathlib import Path

from core.regime_strategies import AllocationSignal, BaseStrategy
from core.strategy_registry import StrategyRegistry, get_registry, register_strategy

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.yaml"


@register_strategy("hmm_regime")
class HmmRegimeStrategy(BaseStrategy):
    """HMM regime-allocation engine (SPY/QQQ)."""

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=ema50 - stop_widen * atr)


@register_strategy("momentum_breakout")
class MomentumBreakoutStrategy(BaseStrategy):
    """Donchian breakout momentum engine (AAPL/NVDA/TSLA)."""

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - 2.0 * stop_widen * atr)


@register_strategy("mean_reversion")
class MeanReversionStrategy(BaseStrategy):
    """Mean-reversion engine -- stub for later (disabled by default)."""

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - 2.0 * stop_widen * atr)


_CLASSES = {
    "hmm_regime": HmmRegimeStrategy,
    "momentum_breakout": MomentumBreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
}


def register_all(registry: StrategyRegistry) -> None:
    """Register fresh instances of all engines into an arbitrary registry."""
    for name, cls in _CLASSES.items():
        if name not in registry:
            registry.register(name, cls())


def apply_config(registry: StrategyRegistry | None = None, settings_path: Path | None = None) -> None:
    """Apply the settings.yaml `strategies` section: enable/disable + symbols + weights."""
    import yaml

    registry = registry or get_registry()
    path = settings_path or SETTINGS
    data = yaml.safe_load(path.read_text()) or {}
    for name, cfg in (data.get("strategies") or {}).items():
        if name not in registry:
            continue
        strat = registry.get(name)
        strat.symbols = list(cfg.get("symbols", []))
        strat.weight_min = float(cfg.get("weight_min", 0.0))
        strat.weight_max = float(cfg.get("weight_max", 1.0))
        if cfg.get("enabled", True):
            strat.on_enable()
        else:
            strat.on_disable()
