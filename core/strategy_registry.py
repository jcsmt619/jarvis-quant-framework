"""
core/strategy_registry.py
=========================
A process-wide registry for strategies running in parallel. Strategies
self-register with a decorator, can be toggled on/off without a restart, and are
auto-disabled (never removed) when their health check fails.

    @register_strategy("hmm_regime")
    class HmmRegimeStrategy(BaseStrategy): ...

    reg = get_registry()
    reg.active()            # only is_enabled=True strategies
    reg.enforce_health()    # auto-disable unhealthy strategies (with alert)
"""

from __future__ import annotations

import logging
from typing import Callable

from core.regime_strategies import BaseStrategy, StrategyHealth

logger = logging.getLogger("strategy_registry")


class StrategyRegistry:
    """Maintains {strategy_name: strategy_instance}."""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, name: str, strategy: BaseStrategy) -> None:
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")
        strategy.name = name
        self._strategies[name] = strategy

    def unregister(self, name: str) -> None:
        self._strategies.pop(name, None)

    def get(self, name: str) -> BaseStrategy:
        return self._strategies[name]

    def all(self) -> dict[str, BaseStrategy]:
        return dict(self._strategies)

    def active(self) -> dict[str, BaseStrategy]:
        return {n: s for n, s in self._strategies.items() if getattr(s, "is_enabled", False)}

    def clear(self) -> None:
        self._strategies.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._strategies

    def __len__(self) -> int:
        return len(self._strategies)

    def enforce_health(self, on_alert: Callable[[str, StrategyHealth], None] | None = None) -> list[str]:
        """
        Health-check every ENABLED strategy; auto-disable (but do not remove) any
        that are unhealthy, firing an alert. Returns the list of disabled names.
        """
        disabled: list[str] = []
        for name, strategy in list(self._strategies.items()):
            if not getattr(strategy, "is_enabled", False):
                continue
            health = strategy.health_check()
            if not health.is_healthy:
                strategy.on_disable()
                disabled.append(name)
                logger.warning("Auto-disabled strategy '%s': %s", name, health.reason_if_unhealthy)
                if on_alert is not None:
                    on_alert(name, health)
        return disabled


# --- process-wide singleton -------------------------------------------------
_GLOBAL_REGISTRY = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """Return the one-per-process global registry."""
    return _GLOBAL_REGISTRY


def register_strategy(name: str) -> Callable[[type[BaseStrategy]], type[BaseStrategy]]:
    """Class decorator: instantiate the strategy and register it under `name`."""
    def decorator(cls: type[BaseStrategy]) -> type[BaseStrategy]:
        instance = cls()
        get_registry().register(name, instance)
        return cls
    return decorator
