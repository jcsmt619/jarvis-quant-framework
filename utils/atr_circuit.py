"""
ATR-Based Trailing Volatility Circuit Module
=============================================
Implements non-linear stop tightening based on Average True Range (ATR).
Detects extreme spikes and scales out positions to lock hyper-profits.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class ExitSignal(Enum):
    """ATR circuit exit signals."""
    HOLD = "hold"
    SCALE_OUT_50PCT = "scale_out_50pct"
    CLOSE_FULL = "close_full"
    PARTIAL_CLOSE = "partial_close"


@dataclass
class ATRState:
    """Current ATR-based trailing stop state."""
    entry_price: float
    current_price: float
    atr_14: float
    profit_atr: float  # Current profit measured in ATR units
    stop_price: float
    position_size: float  # Current position notional
    scale_out_count: int = 0  # Number of times already scaled out
    
    def __repr__(self) -> str:
        profit_pct = ((self.current_price - self.entry_price) / self.entry_price) * 100
        return (
            f"ATRState(entry={self.entry_price:.2f}, current={self.current_price:.2f}, "
            f"profit={profit_pct:.1f}%, {self.profit_atr:.2f}ATR, stop={self.stop_price:.2f})"
        )


class ATRCircuit:
    """
    Non-linear trailing stop management using ATR.
    
    Profit Escalation Levels:
    - 0-1 ATR: Entry stop (2x ATR below entry)
    - 1-2 ATR: Breakeven stop
    - 2-3 ATR: Tighten to +0.5 ATR
    - 3-4 ATR: Aggressive to +1.5 ATR
    - 4+ ATR: SPIKE DETECTED - scale out 50%, trail remainder at 2 ATR
    """
    
    def __init__(self, atr_period: int = 14, spike_threshold_atr: float = 4.0):
        """
        Parameters:
        -----------
        atr_period : int
            Period for ATR calculation (default 14)
        spike_threshold_atr : float
            Spike detection threshold in ATR units (default 4.0)
        """
        self.atr_period = atr_period
        self.spike_threshold_atr = spike_threshold_atr
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                      period: int = 14) -> np.ndarray:
        """
        Calculate Average True Range.
        
        Parameters:
        -----------
        high, low, close : np.ndarray
            OHLC price arrays
        period : int
            ATR lookback period
        
        Returns:
        --------
        atr : np.ndarray
            ATR values (same length as input)
        """
        if isinstance(high, pd.Series):
            high = high.values
        if isinstance(low, pd.Series):
            low = low.values
        if isinstance(close, pd.Series):
            close = close.values
        
        tr = np.zeros(len(close))
        tr[0] = high[0] - low[0]
        
        for i in range(1, len(close)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        
        # Simple moving average
        atr = np.convolve(tr, np.ones(period) / period, mode='same')
        return atr
    
    def calculate_trailing_stop(self, entry_price: float, current_price: float, 
                                atr_value: float) -> dict:
        """
        Calculate current trailing stop based on profit progression.
        
        Parameters:
        -----------
        entry_price : float
            Entry price of position
        current_price : float
            Current market price
        atr_value : float
            Current ATR(14) value
        
        Returns:
        --------
        dict with keys:
            'stop_price': float,
            'exit_signal': ExitSignal,
            'profit_atr': float,
            'reason': str,
        """
        profit = current_price - entry_price
        profit_atr = profit / atr_value if atr_value > 0 else 0.0
        
        if profit_atr < 1.0:
            # Profit stage 1: Entry protection
            stop_price = entry_price - (2.0 * atr_value)
            return {
                "stop_price": stop_price,
                "profit_atr": profit_atr,
                "exit_signal": ExitSignal.HOLD,
                "stage": "entry_protection",
                "reason": f"Entry stop: {profit_atr:.2f} ATR gain, stop at -2ATR",
            }
        
        elif profit_atr < 2.0:
            # Profit stage 2: Breakeven stop
            stop_price = entry_price
            return {
                "stop_price": stop_price,
                "profit_atr": profit_atr,
                "exit_signal": ExitSignal.HOLD,
                "stage": "breakeven",
                "reason": f"Breakeven protection: {profit_atr:.2f} ATR gain, stop at entry",
            }
        
        elif profit_atr < 3.0:
            # Profit stage 3: Tighten stop
            stop_price = entry_price + (0.5 * atr_value)
            return {
                "stop_price": stop_price,
                "profit_atr": profit_atr,
                "exit_signal": ExitSignal.HOLD,
                "stage": "tighten_mild",
                "reason": f"Mild tightening: {profit_atr:.2f} ATR gain, stop at +0.5ATR",
            }
        
        elif profit_atr < 4.0:
            # Profit stage 4: Aggressive tightening
            stop_price = entry_price + (1.5 * atr_value)
            return {
                "stop_price": stop_price,
                "profit_atr": profit_atr,
                "exit_signal": ExitSignal.HOLD,
                "stage": "tighten_aggressive",
                "reason": f"Aggressive tightening: {profit_atr:.2f} ATR gain, stop at +1.5ATR",
            }
        
        else:
            # Extreme spike: Scale out 50%
            stop_price = entry_price + (2.0 * atr_value)
            return {
                "stop_price": stop_price,
                "profit_atr": profit_atr,
                "exit_signal": ExitSignal.SCALE_OUT_50PCT,
                "stage": "extreme_spike",
                "reason": f"EXTREME SPIKE DETECTED: {profit_atr:.2f} ATR gain, "
                         f"scale out 50%, trail at +2ATR",
            }
    
    def detect_spike_exit(self, current_price: float, entry_price: float, 
                         atr_value: float, rsi: float) -> dict:
        """
        Detect extreme spike condition for partial exit.
        
        Conditions:
        - Profit > 4 ATR AND
        - RSI > 75 (overbought)
        
        Parameters:
        -----------
        current_price : float
            Current market price
        entry_price : float
            Entry price
        atr_value : float
            Current ATR value
        rsi : float
            Current RSI(14) value [0-100]
        
        Returns:
        --------
        dict with exit signal and details
        """
        profit = current_price - entry_price
        profit_atr = profit / atr_value if atr_value > 0 else 0.0
        
        is_spike = profit_atr > self.spike_threshold_atr
        is_overbought = rsi > 75
        
        if is_spike and is_overbought:
            return {
                "exit_signal": ExitSignal.SCALE_OUT_50PCT,
                "trigger": "spike_overbought",
                "profit_atr": profit_atr,
                "rsi": rsi,
                "reason": f"Spike {profit_atr:.2f}ATR + RSI {rsi:.0f} (overbought) → Scale 50%",
                "scale_price": entry_price + (2.0 * atr_value),
            }
        
        elif is_spike and not is_overbought:
            return {
                "exit_signal": ExitSignal.HOLD,
                "trigger": "spike_pending_overbought",
                "profit_atr": profit_atr,
                "rsi": rsi,
                "reason": f"Spike {profit_atr:.2f}ATR awaiting RSI overbought (current {rsi:.0f})",
                "scale_price": entry_price + (2.0 * atr_value),
            }
        
        else:
            return {
                "exit_signal": ExitSignal.HOLD,
                "trigger": "no_spike",
                "profit_atr": profit_atr,
                "rsi": rsi,
                "reason": f"Normal progression: {profit_atr:.2f}ATR, RSI {rsi:.0f}",
            }
    
    def detect_consolidation_exit(self, entry_price: float, current_price: float, 
                                 stop_price: float, atr_value: float) -> dict:
        """
        Detect consolidation pattern (exit circuit).
        
        When position has achieved extreme profit (3+ ATR) but suddenly
        consolidates (close - stop < 0.5 ATR), reversal risk is high.
        
        Parameters:
        -----------
        entry_price : float
            Entry price
        current_price : float
            Current price
        stop_price : float
            Current stop price
        atr_value : float
            Current ATR
        
        Returns:
        --------
        dict with exit recommendation
        """
        profit = current_price - entry_price
        profit_atr = profit / atr_value if atr_value > 0 else 0.0
        
        distance_to_stop = current_price - stop_price
        distance_atr = distance_to_stop / atr_value if atr_value > 0 else 0.0
        
        if profit_atr >= 3.0 and distance_atr < 0.5:
            return {
                "exit_signal": ExitSignal.CLOSE_FULL,
                "trigger": "consolidation_reversal_risk",
                "profit_atr": profit_atr,
                "distance_to_stop_atr": distance_atr,
                "reason": f"Extreme profit {profit_atr:.2f}ATR with tight consolidation "
                         f"({distance_atr:.2f}ATR to stop) → Reversal risk HIGH → CLOSE",
            }
        
        else:
            return {
                "exit_signal": ExitSignal.HOLD,
                "trigger": "consolidation_ok",
                "profit_atr": profit_atr,
                "distance_to_stop_atr": distance_atr,
                "reason": f"Profit {profit_atr:.2f}ATR, comfortable distance to stop "
                         f"({distance_atr:.2f}ATR) → Hold",
            }


# Example usage
if __name__ == "__main__":
    circuit = ATRCircuit()
    
    # Simulate price progression
    entry = 100.0
    prices = [100.5, 101.0, 102.0, 104.0, 108.0, 110.0]
    atr = 1.0
    rsi_values = [55, 58, 62, 70, 78, 82]
    
    print("=== ATR Circuit Simulation ===\n")
    for price, rsi in zip(prices, rsi_values):
        stop_result = circuit.calculate_trailing_stop(entry, price, atr)
        spike_result = circuit.detect_spike_exit(price, entry, atr, rsi)
        
        print(f"Price: ${price:.2f}")
        print(f"  Stop: {stop_result['reason']}")
        print(f"  Spike: {spike_result['reason']}")
        print()
