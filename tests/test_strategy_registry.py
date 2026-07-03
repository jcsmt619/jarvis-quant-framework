"""
tests/test_strategy_registry.py
===============================
Covers the parallel-strategy framework: registration/lookup, lifecycle hooks,
duplicate-registration guard, health-check logic for every failure mode, and
unhealthy auto-disable.
"""

from __future__ import annotations

import pytest

from core.regime_strategies import AllocationSignal, BaseStrategy
from core.strategy_registry import StrategyRegistry, get_registry


class DummyStrategy(BaseStrategy):
    def generate_signal(self, price, ema50, atr, stop_widen=1.0):
        return AllocationSignal(allocation=0.0, leverage=1.0, stop_price=price - atr)


class HookStrategy(DummyStrategy):
    def __init__(self, name=None):
        super().__init__(name)
        self.enabled_calls = 0
        self.disabled_calls = 0

    def on_enable(self):
        super().on_enable()
        self.enabled_calls += 1

    def on_disable(self):
        super().on_disable()
        self.disabled_calls += 1


# --- registration + lookup -------------------------------------------------
def test_register_and_lookup():
    reg = StrategyRegistry()
    s = DummyStrategy()
    reg.register("alpha", s)
    assert reg.get("alpha") is s
    assert reg.get("alpha").name == "alpha"      # register sets the name
    assert "alpha" in reg.all()
    assert len(reg) == 1


def test_unregister_and_active_filter():
    reg = StrategyRegistry()
    a, b = DummyStrategy(), DummyStrategy()
    reg.register("a", a)
    reg.register("b", b)
    b.on_disable()
    assert set(reg.active().keys()) == {"a"}
    reg.unregister("a")
    assert "a" not in reg.all()


def test_duplicate_registration_raises():
    reg = StrategyRegistry()
    reg.register("dup", DummyStrategy())
    with pytest.raises(ValueError):
        reg.register("dup", DummyStrategy())


# --- lifecycle hooks -------------------------------------------------------
def test_lifecycle_hooks_fire():
    s = HookStrategy(name="h")
    assert s.is_enabled is True
    s.on_disable()
    assert s.is_enabled is False and s.disabled_calls == 1
    s.on_enable()
    assert s.is_enabled is True and s.enabled_calls == 1


# --- health-check failure modes -------------------------------------------
def test_health_drawdown_breach():
    s = DummyStrategy(name="dd")
    s.record_daily_return(0.05)    # peak
    s.record_daily_return(-0.20)   # ~20% drawdown > 15%
    h = s.health_check()
    assert not h.is_healthy and "drawdown" in h.reason_if_unhealthy


def test_health_sharpe_breach():
    s = DummyStrategy(name="sh")
    for _ in range(30):            # net-negative, low-vol, no long streak, small DD
        s.record_daily_return(-0.003)
        s.record_daily_return(0.001)
    h = s.health_check()
    assert not h.is_healthy
    assert h.recent_sharpe < -1.0 and "Sharpe" in h.reason_if_unhealthy


def test_health_consecutive_losses_breach():
    s = DummyStrategy(name="ld")
    for _ in range(10):            # 10 tiny losses: DD small, Sharpe undefined(0)
        s.record_daily_return(-0.001)
    h = s.health_check()
    assert not h.is_healthy
    assert h.consecutive_losing_days == 10 and "consecutive" in h.reason_if_unhealthy


def test_health_healthy_strategy():
    s = DummyStrategy(name="ok")
    for _ in range(30):
        s.record_daily_return(0.002)
        s.record_daily_return(-0.001)
    h = s.health_check()
    assert h.is_healthy and h.reason_if_unhealthy is None


# --- auto-disable ----------------------------------------------------------
def test_enforce_health_auto_disables_with_alert():
    reg = StrategyRegistry()
    bad, good = DummyStrategy(), DummyStrategy()
    reg.register("bad", bad)
    reg.register("good", good)
    bad.record_daily_return(0.05)
    bad.record_daily_return(-0.20)   # unhealthy (drawdown)
    good.record_daily_return(0.01)   # healthy

    alerts = []
    disabled = reg.enforce_health(on_alert=lambda name, health: alerts.append((name, health)))
    assert disabled == ["bad"]
    assert bad.is_enabled is False       # disabled, not removed
    assert "bad" in reg.all()
    assert good.is_enabled is True
    assert alerts and alerts[0][0] == "bad" and not alerts[0][1].is_healthy


# --- registered engines + settings.yaml config ----------------------------
def test_registered_strategies_and_config():
    from core.registered_strategies import apply_config, register_all

    reg = StrategyRegistry()
    register_all(reg)
    assert set(reg.all().keys()) == {"hmm_regime", "momentum_breakout", "mean_reversion"}

    apply_config(reg)
    assert reg.get("hmm_regime").is_enabled is True
    assert reg.get("mean_reversion").is_enabled is False   # stub disabled in config
    assert reg.get("hmm_regime").symbols == ["SPY", "QQQ"]
    assert reg.get("hmm_regime").weight_max == 0.50
    assert set(reg.active().keys()) == {"hmm_regime", "momentum_breakout"}


def test_decorator_registers_into_global_singleton():
    import core.registered_strategies  # noqa: F401  (import side-effect self-registers)
    assert "hmm_regime" in get_registry()
    assert get_registry() is get_registry()   # singleton
