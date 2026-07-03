"""
tests/test_friction.py
======================
Friction engine: spread floor for small orders, sqrt-impact scaling,
commission minimum, per-leg borrow rates, and compounding.
"""

from __future__ import annotations

import numpy as np
import pytest

from utils.friction import FrictionConfig, InstitutionalFrictionEngine


@pytest.fixture
def eng() -> InstitutionalFrictionEngine:
    return InstitutionalFrictionEngine(FrictionConfig())


def test_small_orders_still_pay_spread(eng):
    """Impact -> 0 as size -> 0, but the half-spread never disappears."""
    tiny = eng.execution_cost(price=100.0, order_shares=1, atr=2.0,
                              adv_shares=10_000_000, daily_range=1.0)
    assert tiny >= 1.00                       # min commission
    assert eng.half_spread(100.0, 1.0) == pytest.approx(0.025)  # 5% * 1.0 / 2


def test_impact_scales_with_sqrt_of_size(eng):
    i1 = eng.market_impact(100.0, 2.0, 10_000, 1_000_000)
    i4 = eng.market_impact(100.0, 2.0, 40_000, 1_000_000)
    assert i4 == pytest.approx(2.0 * i1)      # 4x size -> 2x impact (sqrt law)


def test_impact_scales_with_volatility(eng):
    calm = eng.market_impact(100.0, 1.0, 10_000, 1_000_000)
    wild = eng.market_impact(100.0, 4.0, 10_000, 1_000_000)
    assert wild == pytest.approx(4.0 * calm)


def test_commission_floor(eng):
    assert eng.execution_cost(100.0, 10, atr=0.0, adv_shares=0) == pytest.approx(1.00)
    assert eng.execution_cost(100.0, 100_000, atr=0.0, adv_shares=0) == pytest.approx(500.0)


def test_borrow_per_leg_rates(eng):
    gc = eng.short_borrow_cost(100_000, 365.25, hard_to_borrow=False)
    htb = eng.short_borrow_cost(100_000, 365.25, hard_to_borrow=True)
    assert gc == pytest.approx(100_000 * ((1 + 0.005 / 365.25) ** 365.25 - 1), rel=1e-9)
    assert htb / gc > 10                       # HTB ~16x GC
    assert eng.short_borrow_cost(0, 10) == 0.0
    assert eng.short_borrow_cost(100_000, 0) == 0.0


def test_daily_borrow_drag(eng):
    drag = eng.daily_borrow_drag(0.75, hard_to_borrow=False)
    assert drag == pytest.approx(0.75 * 0.005 / 252)
    # A year of drag on a 0.75 short book ~ 37.5 bps
    assert drag * 252 == pytest.approx(0.00375)
