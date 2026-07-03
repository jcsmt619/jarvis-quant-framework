"""Regime-conditioned intraday scalping strategies.

Be clear about what the regime layer does and does not do. It does not call
direction tick by tick. It reads the current volatility environment and decides
which playbook is allowed to fire and how big it is allowed to be. The setup
inside that playbook decides long or short. This is regime-aware intraday
trading on short timeframes, not tick-by-tick HFT, and the system is honest
about that limit.

The volatility-rank mapping mirrors the stock template:

    rank = regime_id / (n_regimes - 1)   # 0.0 quietest .. 1.0 most violent
    rank <= 0.33  -> QuietRangeScalp        (fade extremes back to VWAP)
    rank >= 0.67  -> VolatileBreakoutScalp   (momentum, wider stops)
    EXTREME / top -> stand aside (FLAT)
    otherwise     -> NormalTrendScalp        (trade with the short trend)

Stops and targets are expressed in ticks so they translate to dollars through
the instrument spec, and so a member can reason about them the way a futures
trader actually does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

from core.hmm_engine import RegimeInfo, RegimeState
from core.instruments import InstrumentSpec


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    symbol: str
    direction: Direction
    confidence: float
    entry_price: float
    stop_price: float
    target_price: Optional[float]
    stop_ticks: float
    target_ticks: Optional[float]
    regime_id: int
    regime_name: str
    regime_probability: float
    timestamp: Optional[pd.Timestamp]
    reasoning: str
    strategy_name: str
    metadata: dict = field(default_factory=dict)


class BaseScalpStrategy(ABC):
    strategy_name: str = "base"

    def __init__(self, config: dict, regime_info: RegimeInfo) -> None:
        self.cfg = config or {}
        self.regime = regime_info

    @abstractmethod
    def generate_signal(
        self, symbol: str, feats: pd.DataFrame, regime_state: RegimeState,
        instrument: InstrumentSpec,
    ) -> Optional[Signal]:
        ...

    def _build(self, symbol, direction, entry, stop_ticks, target_ticks,
               regime_state, instrument, reasoning, conf_boost=0.0, **meta) -> Signal:
        tick = instrument.tick_size
        if direction is Direction.LONG:
            stop = instrument.round_to_tick(entry - stop_ticks * tick)
            target = instrument.round_to_tick(entry + target_ticks * tick) if target_ticks else None
        elif direction is Direction.SHORT:
            stop = instrument.round_to_tick(entry + stop_ticks * tick)
            target = instrument.round_to_tick(entry - target_ticks * tick) if target_ticks else None
        else:
            stop, target = entry, None
        return Signal(
            symbol=symbol, direction=direction,
            confidence=min(1.0, regime_state.probability + conf_boost),
            entry_price=instrument.round_to_tick(entry),
            stop_price=stop, target_price=target,
            stop_ticks=stop_ticks, target_ticks=target_ticks,
            regime_id=regime_state.state_id, regime_name=regime_state.label,
            regime_probability=regime_state.probability, timestamp=regime_state.timestamp,
            reasoning=reasoning, strategy_name=self.strategy_name, metadata=meta,
        )


class QuietRangeScalp(BaseScalpStrategy):
    """Low-vol mean reversion: fade stretches away from VWAP back toward it."""
    strategy_name = "quiet_range_scalp"

    def generate_signal(self, symbol, feats, regime_state, instrument):
        if len(feats) < 2:
            return None
        row = feats.iloc[-1]
        atr = float(row["atr"])
        if atr <= 0:
            return None
        price = float(row["close"])
        vwap = float(row["vwap"])
        rsi = float(row["rsi"])
        stretch = (price - vwap) / atr
        stop_ticks = max(2.0, _ticks(self.cfg.get("stop_atr", 1.0) * atr, instrument))
        target_ticks = max(2.0, _ticks(self.cfg.get("target_atr", 0.8) * atr, instrument))
        band = float(self.cfg.get("stretch_atr", 0.8))

        if stretch > band and rsi > 60:
            return self._build(symbol, Direction.SHORT, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Quiet fade: {stretch:.1f} ATR above VWAP, RSI {rsi:.0f}")
        if stretch < -band and rsi < 40:
            return self._build(symbol, Direction.LONG, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Quiet fade: {abs(stretch):.1f} ATR below VWAP, RSI {rsi:.0f}")
        return None


class NormalTrendScalp(BaseScalpStrategy):
    """Mid-vol momentum: trade in the direction of the short EMA trend."""
    strategy_name = "normal_trend_scalp"

    def generate_signal(self, symbol, feats, regime_state, instrument):
        if len(feats) < 2:
            return None
        row = feats.iloc[-1]
        atr = float(row["atr"])
        if atr <= 0:
            return None
        price = float(row["close"])
        ema9, ema21 = float(row["ema_9"]), float(row["ema_21"])
        adx = float(row["adx"]) if pd.notna(row["adx"]) else 0.0
        roc5 = float(row["roc_5"]) if pd.notna(row["roc_5"]) else 0.0
        adx_min = float(self.cfg.get("adx_min", 18))
        stop_ticks = max(3.0, _ticks(self.cfg.get("stop_atr", 1.25) * atr, instrument))
        target_ticks = max(3.0, _ticks(self.cfg.get("target_atr", 2.0) * atr, instrument))

        if adx < adx_min:
            return None
        if ema9 > ema21 and roc5 > 0:
            return self._build(symbol, Direction.LONG, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Trend long: EMA9>EMA21, ADX {adx:.0f}", conf_boost=0.05)
        if ema9 < ema21 and roc5 < 0:
            return self._build(symbol, Direction.SHORT, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Trend short: EMA9<EMA21, ADX {adx:.0f}", conf_boost=0.05)
        return None


class VolatileBreakoutScalp(BaseScalpStrategy):
    """High-vol breakout: trade continuation through a recent extreme, wider stop."""
    strategy_name = "volatile_breakout_scalp"

    def generate_signal(self, symbol, feats, regime_state, instrument):
        lookback = int(self.cfg.get("breakout_lookback", 20))
        if len(feats) < lookback + 1:
            return None
        row = feats.iloc[-1]
        atr = float(row["atr"])
        if atr <= 0:
            return None
        price = float(row["close"])
        window = feats["close"].iloc[-(lookback + 1):-1]
        hi, lo = float(window.max()), float(window.min())
        stop_ticks = max(4.0, _ticks(self.cfg.get("stop_atr", 1.75) * atr, instrument))
        target_ticks = max(4.0, _ticks(self.cfg.get("target_atr", 2.5) * atr, instrument))

        if price > hi:
            return self._build(symbol, Direction.LONG, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Breakout long above {lookback}-bar high {hi:.2f}")
        if price < lo:
            return self._build(symbol, Direction.SHORT, price, stop_ticks, target_ticks,
                               regime_state, instrument,
                               f"Breakout short below {lookback}-bar low {lo:.2f}")
        return None


class StandAside(BaseScalpStrategy):
    """Extreme-vol regime: take no new risk."""
    strategy_name = "stand_aside"

    def generate_signal(self, symbol, feats, regime_state, instrument):
        return None


def _ticks(price_distance: float, instrument: InstrumentSpec) -> float:
    return abs(price_distance) / instrument.tick_size


def strategy_for_vol_rank(vol_rank: float, label: str) -> type[BaseScalpStrategy]:
    if label in ("EXTREME", "DEAD"):
        # Most violent tape: stand aside. Deadest tape: also skip (no edge).
        return StandAside if label == "EXTREME" else QuietRangeScalp
    if vol_rank <= 0.33:
        return QuietRangeScalp
    if vol_rank >= 0.67:
        return VolatileBreakoutScalp
    return NormalTrendScalp


class ScalpOrchestrator:
    """Binds one strategy instance to each regime, sorted by volatility rank."""

    def __init__(self, config: dict, regime_infos: list[RegimeInfo]) -> None:
        self.cfg = config or {}
        self._by_regime: dict[int, BaseScalpStrategy] = {}
        self.set_regime_infos(regime_infos)

    def set_regime_infos(self, regime_infos: list[RegimeInfo]) -> None:
        self._by_regime = {}
        for info in regime_infos:
            cls = strategy_for_vol_rank(info.vol_rank, info.regime_name)
            self._by_regime[info.regime_id] = cls(self.cfg, info)

    def generate_signal(
        self, symbol, feats, regime_state, instrument,
    ) -> Optional[Signal]:
        # Unconfirmed regime or flicker handled by caller via min_confidence.
        strat = self._by_regime.get(regime_state.state_id)
        if strat is None:
            return None
        return strat.generate_signal(symbol, feats, regime_state, instrument)

    def strategy_name_for(self, regime_id: int) -> str:
        s = self._by_regime.get(regime_id)
        return s.strategy_name if s else "none"
