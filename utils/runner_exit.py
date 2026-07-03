"""
utils/runner_exit.py
====================
"Runner Mode" exit management -- transforms capped ~1.35R winners into
open-ended runners while ONLY EVER TIGHTENING risk after entry (01_CLAUDE.md
stop rule):

  Trigger  : unrealized profit reaches +1.5R  (R = entry - initial stop)
  Action A : bank 50% of the position (realize profit, halve exposure)
  Action B : stop -> breakeven (trade can no longer lose)
  Action C : trail the remaining 50% at 2.0x ATR, ratcheting UP only

The state machine is framework-agnostic so the walk-forward backtester, the
backtrader strategy, and unit tests all share the exact same logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunnerAction:
    size_multiplier: float     # fraction of the ORIGINAL position to keep (1.0 / 0.5 / 0.0)
    stop_level: float          # current protective stop (never decreases)
    banked_this_bar: bool      # True on the single bar where the 50% bank fires
    exited: bool               # True when the stop is breached -> flatten


class RunnerManager:
    """Per-trade exit state machine. Supports long (direction=+1) and short (-1);
    all actions are mirrored and remain strictly tighten-only in both directions."""

    def __init__(self, trigger_r: float = 1.5, bank_fraction: float = 0.5,
                 trail_atr_mult: float = 2.0):
        self.trigger_r = trigger_r
        self.bank_fraction = bank_fraction
        self.trail_atr_mult = trail_atr_mult
        self._reset()

    def _reset(self) -> None:
        self.entry_price: float | None = None
        self.initial_stop: float | None = None
        self.r_distance: float = 0.0
        self.stop: float = 0.0
        self.banked: bool = False
        self.active: bool = False
        self.direction: int = 1

    # ------------------------------------------------------------------
    def open_trade(self, entry_price: float, initial_stop: float, direction: int = 1) -> bool:
        """Arm the manager at entry. Returns False (inactive) if the stop is invalid."""
        self._reset()
        d = 1 if direction >= 0 else -1
        if entry_price <= 0 or (entry_price - initial_stop) * d <= 0:
            return False   # stop must sit on the LOSING side of entry
        self.entry_price = float(entry_price)
        self.initial_stop = float(initial_stop)
        self.r_distance = abs(self.entry_price - self.initial_stop)
        self.stop = self.initial_stop
        self.direction = d
        self.active = True
        return True

    def close_trade(self) -> None:
        self._reset()

    # ------------------------------------------------------------------
    def update(self, price: float, atr: float) -> RunnerAction:
        """Advance one bar. Stop can only ratchet toward profit; size only shrinks."""
        if not self.active:
            return RunnerAction(1.0, 0.0, False, False)

        banked_this_bar = False
        d = self.direction
        profit_r = d * (price - self.entry_price) / self.r_distance if self.r_distance > 0 else 0.0
        tighten = max if d > 0 else min   # longs ratchet the stop UP, shorts DOWN

        # Trigger: bank 50%, move stop to breakeven, start the ATR trail.
        if not self.banked and profit_r >= self.trigger_r:
            self.banked = True
            banked_this_bar = True
            self.stop = tighten(self.stop, self.entry_price)      # breakeven, tighten-only

        # Trail phase: trail_atr_mult x ATR behind price, ratcheting toward profit only.
        if self.banked and atr > 0:
            self.stop = tighten(self.stop, price - d * self.trail_atr_mult * atr)

        exited = d * (price - self.stop) < 0
        mult = 0.0 if exited else (1.0 - self.bank_fraction if self.banked else 1.0)
        action = RunnerAction(mult, self.stop, banked_this_bar, exited)
        if exited:
            self._reset()
        return action
