"""Risk manager: contract sizing, prop-firm rules, and circuit breakers.

This is the final gatekeeper and it has absolute veto over any signal. It runs
independently of the HMM, so even if regime detection is completely wrong the
breakers still cap the damage off actual P&L.

Two things make it different from the stock risk manager. First, sizing is in
contracts, not dollars: the number of contracts comes from how many ticks sit
between entry and stop and what each tick is worth, then it is capped by margin
and a hard contract limit. Second, prop-firm rules are first-class. Funded
accounts (Topstep and similar) enforce a daily loss limit and a trailing
maximum drawdown, and a single breach ends the account. Those are modelled here
as hard halts, and the trailing-drawdown halt writes a lock file that has to be
deleted by hand before the bot will trade again.

Default prop-firm numbers below are placeholders. Set them to your account's
real limits in config before trading a funded account.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from core.instruments import InstrumentSpec
from core.scalp_strategies import Direction, Signal


class HaltLevel(str, Enum):
    NONE = "none"
    REDUCED = "reduced"      # size cut, still trading
    HALTED_SESSION = "halted_session"
    HALTED_LOCKED = "halted_locked"  # trailing DD breach, manual reset required


@dataclass
class AccountState:
    equity: float
    starting_equity: float
    session_start_equity: float
    high_water_mark: float
    open_contracts: int = 0
    trades_today: int = 0
    realized_pnl_today: float = 0.0


@dataclass
class RiskDecision:
    approved: bool
    contracts: int = 0
    sized_signal: Optional[Signal] = None
    rejection_reason: str = ""
    modifications: list[str] = field(default_factory=list)


@dataclass
class BreakerState:
    level: HaltLevel = HaltLevel.NONE
    reason: str = ""
    triggered_at: Optional[str] = None
    size_multiplier: float = 1.0


class RiskManager:
    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.risk_per_trade = float(cfg.get("risk_per_trade", 0.005))   # fraction of equity
        self.max_contracts = int(cfg.get("max_contracts", 3))
        self.max_margin_util = float(cfg.get("max_margin_utilization", 0.50))
        self.max_daily_trades = int(cfg.get("max_daily_trades", 30))
        self.min_stop_ticks = float(cfg.get("min_stop_ticks", 2.0))
        self.use_overnight_margin = bool(cfg.get("use_overnight_margin", False))

        pf = cfg.get("prop_firm", {}) or {}
        self.pf_enabled = bool(pf.get("enabled", True))
        self.daily_loss_limit = float(pf.get("daily_loss_limit", 1000.0))   # USD, absolute
        self.daily_loss_reduce_at = float(pf.get("daily_loss_reduce_at", 0.6))  # fraction of limit
        self.trailing_max_drawdown = float(pf.get("trailing_max_drawdown", 2000.0))  # USD
        self.trailing_locks_at_start = bool(pf.get("trailing_locks_at_start", True))
        self.lock_file = pf.get("lock_file", "trading_halted.lock")

        self.breaker = BreakerState()
        self.rejection_log: list[dict] = []
        self.trigger_log: list[dict] = []

    # -- sizing ------------------------------------------------------------
    def size_contracts(self, account: AccountState, signal: Signal,
                        instrument: InstrumentSpec) -> tuple[int, list[str]]:
        notes: list[str] = []
        stop_ticks = instrument.stop_distance_ticks(signal.entry_price, signal.stop_price)
        if stop_ticks < self.min_stop_ticks:
            return 0, [f"stop too tight ({stop_ticks:.1f} < {self.min_stop_ticks} ticks)"]

        risk_dollars = account.equity * self.risk_per_trade * self.breaker.size_multiplier
        per_contract_risk = instrument.ticks_to_dollars(stop_ticks, 1)
        if per_contract_risk <= 0:
            return 0, ["zero per-contract risk"]

        by_risk = int(math.floor(risk_dollars / per_contract_risk))

        margin_capital = account.equity * self.max_margin_util
        per = instrument.overnight_margin if self.use_overnight_margin else instrument.day_margin
        by_margin = int(math.floor(margin_capital / per)) if per > 0 else by_risk

        contracts = max(0, min(by_risk, by_margin, self.max_contracts))
        if contracts < by_risk:
            if contracts == by_margin:
                notes.append(f"margin-capped to {contracts}")
            elif contracts == self.max_contracts:
                notes.append(f"hard cap to {self.max_contracts}")
        if self.breaker.size_multiplier < 1.0:
            notes.append(f"size x{self.breaker.size_multiplier:.2f} (breaker reduced)")
        return contracts, notes

    # -- validation --------------------------------------------------------
    def validate_signal(self, account: AccountState, signal: Signal,
                         instrument: InstrumentSpec) -> RiskDecision:
        # 0. Hard locks first.
        if self.breaker.level is HaltLevel.HALTED_LOCKED:
            return self._reject(signal, "account locked (trailing drawdown breach)")
        if self.breaker.level is HaltLevel.HALTED_SESSION:
            return self._reject(signal, "session halted by circuit breaker")
        if signal.direction is Direction.FLAT:
            return RiskDecision(approved=True, contracts=0, sized_signal=signal)

        # 1. Trade count.
        if account.trades_today >= self.max_daily_trades:
            return self._reject(signal, f"daily trade cap reached ({self.max_daily_trades})")

        # 2. Stop must exist and be on the correct side.
        if signal.stop_price <= 0:
            return self._reject(signal, "missing stop loss")
        if signal.direction is Direction.LONG and signal.stop_price >= signal.entry_price:
            return self._reject(signal, "long stop not below entry")
        if signal.direction is Direction.SHORT and signal.stop_price <= signal.entry_price:
            return self._reject(signal, "short stop not above entry")

        # 3. Size.
        contracts, notes = self.size_contracts(account, signal, instrument)
        if contracts < 1:
            return self._reject(signal, "sized to zero contracts " + ("; ".join(notes) if notes else ""))

        return RiskDecision(approved=True, contracts=contracts, sized_signal=signal, modifications=notes)

    # -- P&L driven breakers ----------------------------------------------
    def update_after_fill_or_mark(self, account: AccountState) -> BreakerState:
        """Re-evaluate breakers off the current account state. Call every loop."""
        # Maintain high-water mark.
        if account.equity > account.high_water_mark:
            account.high_water_mark = account.equity

        # Prop-firm: trailing maximum drawdown (hard, locks the account).
        if self.pf_enabled and self.trailing_max_drawdown > 0:
            floor = account.high_water_mark - self.trailing_max_drawdown
            if self.trailing_locks_at_start:
                floor = max(floor, account.starting_equity - self.trailing_max_drawdown)
            if account.equity <= floor:
                self._set(HaltLevel.HALTED_LOCKED,
                          f"trailing drawdown breach: equity {account.equity:.0f} <= floor {floor:.0f}",
                          account, write_lock=True)
                return self.breaker

        # Prop-firm: daily loss limit (hard, halts for the session).
        if self.pf_enabled and self.daily_loss_limit > 0:
            day_loss = account.session_start_equity - account.equity
            if day_loss >= self.daily_loss_limit:
                self._set(HaltLevel.HALTED_SESSION,
                          f"daily loss limit hit: -{day_loss:.0f} >= {self.daily_loss_limit:.0f}",
                          account)
                return self.breaker
            if day_loss >= self.daily_loss_limit * self.daily_loss_reduce_at:
                if self.breaker.level is not HaltLevel.REDUCED:
                    self._set(HaltLevel.REDUCED,
                              f"approaching daily loss limit (-{day_loss:.0f}), size halved",
                              account)
                    self.breaker.size_multiplier = 0.5
                return self.breaker

        return self.breaker

    # -- session lifecycle -------------------------------------------------
    def start_session(self, account: AccountState) -> None:
        account.session_start_equity = account.equity
        account.trades_today = 0
        account.realized_pnl_today = 0.0
        if self.breaker.level is HaltLevel.HALTED_SESSION:
            self._clear()

    def is_halted(self) -> bool:
        return self.breaker.level in (HaltLevel.HALTED_SESSION, HaltLevel.HALTED_LOCKED)

    def check_lock_file(self) -> bool:
        return Path(self.lock_file).exists()

    # -- internals ---------------------------------------------------------
    def _set(self, level: HaltLevel, reason: str, account: AccountState,
             write_lock: bool = False) -> None:
        self.breaker = BreakerState(level=level, reason=reason,
                                    triggered_at=datetime.now(timezone.utc).isoformat(),
                                    size_multiplier=0.5 if level is HaltLevel.REDUCED else
                                    (0.0 if level in (HaltLevel.HALTED_SESSION, HaltLevel.HALTED_LOCKED) else 1.0))
        self.trigger_log.append({
            "level": level.value, "reason": reason,
            "equity": account.equity, "hwm": account.high_water_mark,
            "at": self.breaker.triggered_at,
        })
        if write_lock:
            try:
                Path(self.lock_file).write_text(
                    f"HALTED {self.breaker.triggered_at}\n{reason}\n"
                    f"Delete this file to allow trading to resume.\n")
            except Exception:
                pass

    def _clear(self) -> None:
        self.breaker = BreakerState()

    def _reject(self, signal: Signal, reason: str) -> RiskDecision:
        self.rejection_log.append({
            "symbol": signal.symbol, "direction": signal.direction.value,
            "reason": reason, "at": datetime.now(timezone.utc).isoformat(),
        })
        return RiskDecision(approved=False, rejection_reason=reason)
