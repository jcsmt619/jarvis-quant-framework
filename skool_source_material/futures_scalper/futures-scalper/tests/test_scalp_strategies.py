"""Strategy tests focus on the contract that matters downstream: signals carry a
correct-side stop, can go both long and short, and the most violent regime takes
no new risk.
"""

import numpy as np
import pandas as pd

from core.hmm_engine import RegimeInfo, RegimeState
from core.instruments import get_instrument
from core.scalp_strategies import (Direction, NormalTrendScalp, QuietRangeScalp,
                                   StandAside, ScalpOrchestrator, strategy_for_vol_rank)


def _regime_state(label="NORMAL", state_id=1, prob=0.8):
    return RegimeState(label=label, state_id=state_id, probability=prob,
                       state_probabilities=np.array([0.1, 0.8, 0.1]),
                       timestamp=pd.Timestamp("2024-01-02 10:00"), is_confirmed=True,
                       consecutive_bars=5)


def _trend_feats(up=True):
    idx = pd.date_range("2024-01-02 09:30", periods=30, freq="5min")
    base = np.linspace(18000, 18050, 30) if up else np.linspace(18050, 18000, 30)
    df = pd.DataFrame(index=idx)
    df["close"] = base
    df["ema_9"] = base + (2 if up else -2)
    df["ema_21"] = base
    df["atr"] = 5.0
    df["rsi"] = 60 if up else 40
    df["adx"] = 30.0
    df["vwap"] = base - (1 if up else -1)
    df["roc_5"] = 0.001 if up else -0.001
    return df


def test_vol_rank_mapping():
    assert strategy_for_vol_rank(0.0, "QUIET") is QuietRangeScalp
    assert strategy_for_vol_rank(0.5, "NORMAL") is NormalTrendScalp
    assert strategy_for_vol_rank(1.0, "EXTREME") is StandAside


def test_trend_scalp_goes_long_in_uptrend():
    info = RegimeInfo(1, "NORMAL", 0.0001, 0.002, 0.5)
    strat = NormalTrendScalp({"adx_min": 18}, info)
    sig = strat.generate_signal("MNQ", _trend_feats(up=True), _regime_state(), get_instrument("MNQ"))
    assert sig is not None and sig.direction is Direction.LONG
    assert sig.stop_price < sig.entry_price       # long stop below entry
    assert sig.target_price > sig.entry_price


def test_trend_scalp_goes_short_in_downtrend():
    info = RegimeInfo(1, "NORMAL", -0.0001, 0.002, 0.5)
    strat = NormalTrendScalp({"adx_min": 18}, info)
    sig = strat.generate_signal("MNQ", _trend_feats(up=False), _regime_state(), get_instrument("MNQ"))
    assert sig is not None and sig.direction is Direction.SHORT
    assert sig.stop_price > sig.entry_price       # short stop above entry
    assert sig.target_price < sig.entry_price


def test_stand_aside_returns_none():
    info = RegimeInfo(2, "EXTREME", 0.0, 0.01, 1.0)
    strat = StandAside({}, info)
    sig = strat.generate_signal("MNQ", _trend_feats(), _regime_state("EXTREME", 2), get_instrument("MNQ"))
    assert sig is None


def test_orchestrator_binds_strategy_per_regime():
    infos = [RegimeInfo(0, "QUIET", 0.0, 0.001, 0.0),
             RegimeInfo(1, "NORMAL", 0.0, 0.002, 0.5),
             RegimeInfo(2, "VOLATILE", 0.0, 0.004, 1.0)]
    orch = ScalpOrchestrator({"adx_min": 18}, infos)
    assert orch.strategy_name_for(0) == "quiet_range_scalp"
    assert orch.strategy_name_for(1) == "normal_trend_scalp"
    assert orch.strategy_name_for(2) == "volatile_breakout_scalp"
