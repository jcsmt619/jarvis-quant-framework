"""
tests/test_regime_strategies.py
===============================
Verifies the STEP 3 allocation blueprint against its 4 operational specs:
strategy allocations/leverage/stops, volatility-ranked orchestration (independent
of return labels), confidence/uncertainty/rebalance logic, and legacy aliases.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.regime_strategies import (
    STRATEGY_ALIASES,
    HighVolDefensiveStrategy,
    LowVolBullStrategy,
    MidVolCautiousStrategy,
    StrategyOrchestrator,
    get_strategy,
)


@dataclass
class FakeRegimeInfo:
    regime_id: int
    expected_volatility: float
    expected_return: float = 0.0


# --- spec 1: strategy classes ---------------------------------------------
def test_low_vol_bull_signal():
    sig = LowVolBullStrategy().generate_signal(price=100.0, ema50=98.0, atr=2.0)
    assert sig.allocation == 0.95 and sig.leverage == 1.25
    # stop = max(100 - 3*2, 98 - 0.5*2) = max(94, 97) = 97
    assert sig.stop_price == pytest.approx(97.0)


def test_mid_vol_cautious_trend_gate():
    up = MidVolCautiousStrategy().generate_signal(price=100.0, ema50=98.0, atr=2.0)
    down = MidVolCautiousStrategy().generate_signal(price=96.0, ema50=98.0, atr=2.0)
    assert up.allocation == 0.95 and up.leverage == 1.0
    assert down.allocation == 0.60 and down.leverage == 1.0
    assert up.stop_price == pytest.approx(97.0)  # 98 - 0.5*2


def test_high_vol_defensive_is_long_only():
    sig = HighVolDefensiveStrategy().generate_signal(price=100.0, ema50=98.0, atr=2.0)
    assert sig.allocation == 0.60 and sig.leverage == 1.0
    assert sig.orientation == "long"
    assert sig.stop_price == pytest.approx(96.0)  # 98 - 1.0*2


# --- spec 2: volatility-ranked orchestration ------------------------------
def _orch_5():
    # Deliberately scramble return vs volatility so the mapping cannot rely on labels.
    infos = {
        10: FakeRegimeInfo(10, expected_volatility=0.005, expected_return=-0.01),  # calmest, worst return
        11: FakeRegimeInfo(11, expected_volatility=0.010, expected_return=0.02),
        12: FakeRegimeInfo(12, expected_volatility=0.020, expected_return=-0.03),
        13: FakeRegimeInfo(13, expected_volatility=0.030, expected_return=0.05),
        14: FakeRegimeInfo(14, expected_volatility=0.050, expected_return=0.01),   # most turbulent
    }
    return StrategyOrchestrator(infos)


def test_orchestrator_maps_by_volatility_not_return():
    orch = _orch_5()
    # rank 0 (calmest, id=10) -> LowVolBull despite having the WORST return.
    assert isinstance(orch.strategy_for_regime(10), LowVolBullStrategy)
    # middle rank -> MidVolCautious
    assert isinstance(orch.strategy_for_regime(12), MidVolCautiousStrategy)
    # most turbulent (id=14) -> HighVolDefensive despite a positive return.
    assert isinstance(orch.strategy_for_regime(14), HighVolDefensiveStrategy)
    assert orch.vol_rank_fraction(10) == 0.0
    assert orch.vol_rank_fraction(14) == pytest.approx(1.0)


# --- spec 3: confidence / uncertainty / rebalance -------------------------
def test_uncertainty_halves_and_forces_flat_leverage():
    orch = _orch_5()
    confident = orch.get_signal(10, 100, 98, 2.0, probability=0.80, is_flickering=False)
    uncertain = orch.get_signal(10, 100, 98, 2.0, probability=0.40, is_flickering=False)
    flicker = orch.get_signal(10, 100, 98, 2.0, probability=0.90, is_flickering=True)
    assert confident.leverage == 1.25 and confident.allocation == 0.95
    assert uncertain.allocation == pytest.approx(0.475) and uncertain.leverage == 1.0
    assert flicker.uncertain is True and flicker.leverage == 1.0


def test_rebalance_threshold():
    orch = _orch_5()
    # LowVolBull target exposure = 0.95*1.25 = 1.1875
    d_far = orch.get_signal(10, 100, 98, 2.0, 0.8, False, active_allocation=1.0)
    d_near = orch.get_signal(10, 100, 98, 2.0, 0.8, False, active_allocation=1.15)
    assert d_far.rebalance is True     # |1.1875 - 1.0| = 0.1875 > 0.10
    assert d_near.rebalance is False   # |1.1875 - 1.15| = 0.0375 < 0.10


# --- LETF volatility stop widening ----------------------------------------
def test_letf_stop_is_widened():
    infos = {
        10: FakeRegimeInfo(10, expected_volatility=0.005),
        11: FakeRegimeInfo(11, expected_volatility=0.010),
        12: FakeRegimeInfo(12, expected_volatility=0.020),
    }
    soxl = StrategyOrchestrator(infos, symbol="SOXL")
    spy = StrategyOrchestrator(infos, symbol="SPY")
    d_soxl = soxl.get_signal(10, 100.0, 98.0, 2.0, 0.8, False)
    d_spy = spy.get_signal(10, 100.0, 98.0, 2.0, 0.8, False)
    assert d_soxl.stop_widened is True and d_spy.stop_widened is False
    # Wider berth -> the LETF stop sits LOWER (further below price).
    assert d_soxl.stop_price < d_spy.stop_price


# --- spec 4: backward-compatible aliases ----------------------------------
def test_aliases():
    assert STRATEGY_ALIASES["BearTrendStrategy"] is HighVolDefensiveStrategy
    assert STRATEGY_ALIASES["CrashDefensiveStrategy"] is HighVolDefensiveStrategy
    assert STRATEGY_ALIASES["MeanReversionStrategy"] is MidVolCautiousStrategy


# --- Capped Satellite doctrine (SOXL/TQQQ never exceed 10% of equity) ------
def test_satellite_cap_hard_limits_letf_exposure():
    from core.regime_strategies import SATELLITE_CAP

    infos = {
        10: FakeRegimeInfo(10, expected_volatility=0.005),
        11: FakeRegimeInfo(11, expected_volatility=0.010),
        12: FakeRegimeInfo(12, expected_volatility=0.020),
    }
    for sym in ("SOXL", "TQQQ"):
        orch = StrategyOrchestrator(infos, symbol=sym)
        # Strongest possible signal: low-vol regime, high confidence, no flicker.
        d = orch.get_signal(10, 100.0, 98.0, 2.0, 0.99, False)
        assert d.target_exposure <= SATELLITE_CAP + 1e-12
        assert d.satellite_capped is True
        # A -75% LETF crash at max allocation costs <= 7.5% of the portfolio.
        assert d.target_exposure * 0.75 <= 0.075 + 1e-12


def test_satellite_cap_does_not_touch_core_assets():
    infos = {
        10: FakeRegimeInfo(10, expected_volatility=0.005),
        11: FakeRegimeInfo(11, expected_volatility=0.010),
        12: FakeRegimeInfo(12, expected_volatility=0.020),
    }
    spy = StrategyOrchestrator(infos, symbol="SPY")
    d = spy.get_signal(10, 100.0, 98.0, 2.0, 0.99, False)
    assert d.target_exposure > 0.10          # SPY keeps its full regime allocation
    assert d.satellite_capped is False
    assert STRATEGY_ALIASES["BullTrendStrategy"] is LowVolBullStrategy
    assert STRATEGY_ALIASES["EuphoriaCautiousStrategy"] is LowVolBullStrategy
    assert get_strategy("CrashDefensiveStrategy") is HighVolDefensiveStrategy
    assert get_strategy("LowVolBull") is LowVolBullStrategy
