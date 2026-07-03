"""
core/risk_manager.py
====================
STEP 5 (weaponized) — an asymmetric hyper-alpha RISK MATRIX with ABSOLUTE VETO
power over every signal. It operates INDEPENDENTLY of the HMM: circuit breakers
fire on realized P&L drawdown even if the regime engine is completely wrong.

Layers:
  * CircuitBreaker      — daily / weekly / peak-account drawdown hard stops,
                          with a manual-delete kill-switch lock file. Logs every
                          trigger (type, DD, equity, positions closed, regime).
  * Kelly sizing        — full-Kelly fraction, concentration + leverage capped.
  * Dynamic leverage    — 1.0x default; up to 3.0x crypto / 4.0x LETF ONLY on a
                          confirmed low-vol breakout; forced to 1.0x/cash when
                          the regime is uncertain, any breaker is active, or the
                          rolling win rate slips below the floor.
  * validate_signal()   — the single gate every order passes through: mandatory
                          ATR stop, spread/liquidity, duplicate block, max
                          concurrent / daily-trade caps, portfolio exposure cap,
                          correlation spectrum reduction, min-size floor.

--------------------------------------------------------------------------------
RISK REALITY: 300% gross exposure with full Kelly on 3x LETFs is ~12x underlying
beta. These breakers make ruin LESS likely, not impossible — an overnight gap
can still leap the stop before the breaker flattens. This module CONTAINS the
aggressive path the rest of the config selects; it does not sanctify it.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field, fields, replace
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCK = ROOT / "logs" / "trading_halted.lock"
DEFAULT_SETTINGS = ROOT / "config" / "settings.yaml"

logger = logging.getLogger("risk_manager")


class RiskAction(Enum):
    NORMAL = "normal"
    REDUCE_50 = "reduce_50"
    CLOSE_ALL_HALT_DAY = "halt_day"
    CLOSE_ALL_HALT_WEEK = "halt_week"
    CLOSE_ALL_HALT_HARD = "halt_hard"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class RiskLimits:
    # portfolio exposure
    max_total_exposure: float = 3.0
    max_position_pct: float = 0.75        # single-position concentration cap
    max_concurrent: int = 3
    max_daily_trades: int = 50
    max_leverage: float = 4.0             # hard intraday leverage cap
    max_overnight_leverage: float = 2.0
    # dynamic leverage matrix
    crypto_max_leverage: float = 3.0
    letf_max_leverage: float = 4.0
    win_rate_floor: float = 0.42
    equity_gap_atr_mult: float = 3.0
    # kelly sizing
    kelly_fraction: float = 0.5
    risk_per_trade: float = 0.015      # course "survival first" rule: cap loss per trade at 1-2%
    min_trades: int = 20
    lookback: int = 100
    warmup_fraction: float = 0.20
    min_position_usd: float = 100.0
    # circuit breakers
    daily_dd_reduce: float = 0.04
    daily_dd_halt: float = 0.06
    weekly_dd_reduce: float = 0.10
    weekly_dd_halt: float = 0.15
    peak_dd_lock: float = 0.25
    reduce_factor: float = 0.50
    # order validation
    max_spread: float = 0.01
    dup_window_seconds: float = 10.0
    # correlation spectrum
    corr_threshold: float = 0.85
    corr_reduce: float = 0.25

    @classmethod
    def from_settings(cls, path: Path | str | None = None) -> "RiskLimits":
        """Load thresholds from settings.yaml (risk section). Falls back to defaults."""
        path = Path(path) if path else DEFAULT_SETTINGS
        try:
            import yaml
            data = yaml.safe_load(path.read_text()) or {}
            risk = data.get("risk", {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not load settings %s (%s); using defaults", path, exc)
            return cls()
        alias = {"max_single_position": "max_position_pct"}
        valid = {f.name for f in fields(cls)}
        kwargs = {}
        for k, v in risk.items():
            key = alias.get(k, k)
            if key in valid:
                kwargs[key] = v
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Signal / state / decision dataclasses
# ---------------------------------------------------------------------------
@dataclass
class TradeSignal:
    symbol: str
    direction: int                     # +1 long, -1 short
    asset_class: str = "crypto"        # "crypto" | "letf" | "equity"
    price: float = 0.0
    atr: float = 0.0
    stop_loss: float | None = None     # MANDATORY ATR trailing stop
    regime: str = "uncertain"          # "confirmed_low_vol" | "uncertain" | ...
    confirmed_breakout: bool = False
    win_rate: float = 0.50
    bid_ask_spread: float = 0.0
    sector: str | None = None
    returns: np.ndarray | None = None  # recent returns for correlation check
    timestamp: datetime | None = None
    # filled in by validate_signal():
    target_notional: float = 0.0
    leverage: float = 1.0


@dataclass
class PortfolioState:
    equity: float
    cash: float
    buying_power: float
    positions: dict[str, dict] = field(default_factory=dict)  # symbol -> {notional, direction, returns, sector}
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    peak_equity: float = 0.0
    drawdown: float = 0.0                 # peak-to-current drawdown (fraction)
    daily_drawdown: float = 0.0           # intraday drawdown (fraction)
    weekly_drawdown: float = 0.0          # week-to-date drawdown (fraction)
    circuit_breaker_status: str = "normal"
    flicker_rate: int = 0


@dataclass
class RiskDecision:
    approved: bool
    modified_signal: TradeSignal | None = None
    rejection_reason: str | None = None
    modifications: list[str] = field(default_factory=list)


@dataclass
class CircuitBreakerEvent:
    breaker_type: str
    drawdown: float
    equity: float
    positions_closed: int
    regime: str | None
    timestamp: Any


# ---------------------------------------------------------------------------
# Circuit breaker engine
# ---------------------------------------------------------------------------
class CircuitBreaker:
    def __init__(self, limits: RiskLimits, initial_capital: float, lock_file: Path):
        self.limits = limits
        self.lock_file = Path(lock_file)
        self.peak_equity = float(initial_capital)
        self.day_open = float(initial_capital)
        self.week_open = float(initial_capital)
        self.current_day: date | None = None
        self.current_week: tuple | None = None
        self.halted_today = False
        self.halted_week = False
        self.hard_halted = False
        self.history: list[CircuitBreakerEvent] = []
        self._last_action = RiskAction.NORMAL

    def reset_daily(self, equity: float) -> None:
        self.day_open = equity if equity > 0 else self.day_open
        self.halted_today = False

    def reset_weekly(self, equity: float) -> None:
        self.week_open = equity if equity > 0 else self.week_open
        self.halted_week = False

    def _log(self, breaker_type: str, dd: float, equity: float, regime, positions_closed: int, ts=None) -> None:
        self.history.append(CircuitBreakerEvent(breaker_type, dd, equity, positions_closed, regime, ts))
        logger.warning("BREAKER %s | DD=%.2f%% equity=%.0f regime=%s closed=%d",
                       breaker_type, dd * 100, equity, regime, positions_closed)

    def update(self, timestamp, equity: float, regime=None, open_positions: int = 0) -> RiskAction:
        d = timestamp.date() if hasattr(timestamp, "date") else timestamp
        w = timestamp.isocalendar()[:2] if hasattr(timestamp, "isocalendar") else None
        if self.current_day != d:
            self.current_day = d
            self.reset_daily(equity)
        if w is not None and self.current_week != w:
            self.current_week = w
            self.reset_weekly(equity)

        self.peak_equity = max(self.peak_equity, equity)
        peak_dd = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0.0

        # 1. hard, account-level kill switch (highest priority)
        if peak_dd > self.limits.peak_dd_lock or equity <= 0:
            self._write_lock(peak_dd, equity)
            if not self.hard_halted:
                self._log("PEAK_HARD_HALT", peak_dd, equity, regime, open_positions, d)
            self.hard_halted = True
            self._last_action = RiskAction.CLOSE_ALL_HALT_HARD
            return self._last_action
        if self.hard_halted:
            return RiskAction.CLOSE_ALL_HALT_HARD

        weekly_dd = (self.week_open - equity) / self.week_open if self.week_open > 0 else 0.0
        daily_dd = (self.day_open - equity) / self.day_open if self.day_open > 0 else 0.0

        # 2. weekly halt
        if self.halted_week:
            return RiskAction.CLOSE_ALL_HALT_WEEK
        if weekly_dd > self.limits.weekly_dd_halt:
            self.halted_week = True
            self._log("WEEKLY_HALT", weekly_dd, equity, regime, open_positions, d)
            self._last_action = RiskAction.CLOSE_ALL_HALT_WEEK
            return self._last_action

        # 3. daily halt
        if self.halted_today:
            return RiskAction.CLOSE_ALL_HALT_DAY
        if daily_dd > self.limits.daily_dd_halt:
            self.halted_today = True
            self._log("DAILY_HALT", daily_dd, equity, regime, open_positions, d)
            self._last_action = RiskAction.CLOSE_ALL_HALT_DAY
            return self._last_action

        # 4. reduce (daily OR weekly soft threshold)
        if daily_dd > self.limits.daily_dd_reduce or weekly_dd > self.limits.weekly_dd_reduce:
            self._log("REDUCE_50", max(daily_dd, weekly_dd), equity, regime, open_positions, d)
            self._last_action = RiskAction.REDUCE_50
            return self._last_action

        self._last_action = RiskAction.NORMAL
        return self._last_action

    def check(self) -> RiskAction:
        return self._last_action

    def get_history(self) -> list[CircuitBreakerEvent]:
        return self.history

    def _write_lock(self, peak_dd: float, equity: float) -> None:
        if not self.lock_file.exists():
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(
                "TRADING HALTED — hard peak-drawdown breaker (manual delete required)\n"
                f"peak_dd={peak_dd:.4f}\nequity={equity:.2f}\npeak_equity={self.peak_equity:.2f}\n"
                f"timestamp={datetime.now(timezone.utc).isoformat()}\n"
            )
            logger.error("PEAK DD %.2f%% > %.0f%% -> HARD HALT. Lock: %s",
                         peak_dd * 100, self.limits.peak_dd_lock * 100, self.lock_file)


# ---------------------------------------------------------------------------
# Risk manager (veto authority)
# ---------------------------------------------------------------------------
def _rolling_corr(a: np.ndarray | None, b: np.ndarray | None, window: int = 30) -> float | None:
    if a is None or b is None:
        return None
    a = np.asarray(a, dtype=float)[-window:]
    b = np.asarray(b, dtype=float)[-window:]
    m = min(len(a), len(b))
    if m < 5:
        return None
    a, b = a[-m:], b[-m:]
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None, initial_capital: float = 100000.0,
                 lock_file: Path | str | None = None, tail_monitor=None):
        self.limits = limits or RiskLimits()
        self.initial_capital = float(initial_capital)
        self.lock_file = Path(lock_file) if lock_file else DEFAULT_LOCK
        self.breaker = CircuitBreaker(self.limits, initial_capital, self.lock_file)
        # Optional proactive tail-risk governor (risk/tail_monitor.py). When set,
        # it holds absolute veto power as the FINAL check in validate_signal.
        self.tail_monitor = tail_monitor
        self._pnls: deque[float] = deque(maxlen=self.limits.lookback)
        self._recent_orders: list[tuple] = []
        self._daily_trades = 0
        self._trades_day: date | None = None

    # ---- circuit-breaker delegation / state ----
    @property
    def hard_halted(self) -> bool:
        return self.breaker.hard_halted

    @property
    def halted_today(self) -> bool:
        return self.breaker.halted_today

    @property
    def halted_week(self) -> bool:
        return self.breaker.halted_week

    @property
    def peak_equity(self) -> float:
        return self.breaker.peak_equity

    def update(self, timestamp, equity: float, regime=None, open_positions: int = 0) -> RiskAction:
        return self.breaker.update(timestamp, equity, regime, open_positions)

    def size_multiplier(self, action: RiskAction) -> float:
        if action in (RiskAction.CLOSE_ALL_HALT_DAY, RiskAction.CLOSE_ALL_HALT_WEEK, RiskAction.CLOSE_ALL_HALT_HARD):
            return 0.0
        if action == RiskAction.REDUCE_50:
            return self.limits.reduce_factor
        return 1.0

    # ---- kill switch ----
    def kill_switch_engaged(self) -> bool:
        if self.lock_file.exists():
            self.breaker.hard_halted = True
            return True
        return False

    def clear_lock(self) -> None:
        if self.lock_file.exists():
            self.lock_file.unlink()
        self.breaker.hard_halted = False

    # ---- kelly sizing ----
    def record_trade_pnl(self, pnl: float) -> None:
        self._pnls.append(float(pnl))

    def kelly_fraction_value(self) -> float:
        pnls = list(self._pnls)
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        if len(pnls) < self.limits.min_trades or not wins or not losses:
            return 0.0
        p = len(wins) / len(pnls)
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        if avg_loss <= 0:
            return 0.0
        b = avg_win / avg_loss
        f = (p - (1.0 - p) / b) * self.limits.kelly_fraction
        return max(0.0, min(f, self.limits.max_position_pct))

    def rolling_win_rate(self) -> float:
        pnls = list(self._pnls)
        if not pnls:
            return 0.5
        return sum(1 for x in pnls if x > 0) / len(pnls)

    def target_leverage(self, accelerating: bool) -> float:
        """Notional as a fraction of equity for the single-asset simulator path."""
        f = self.kelly_fraction_value()
        base = f if f > 0.0 else self.limits.warmup_fraction
        if accelerating:
            scaled = base / self.limits.max_position_pct * self.limits.max_leverage
            return float(min(scaled, self.limits.max_leverage))
        return float(min(base, self.limits.max_position_pct))

    # ---- dynamic leverage matrix ----
    def leverage_for(self, signal: TradeSignal, state: PortfolioState) -> float:
        breaker_active = state.circuit_breaker_status not in ("normal", "", None)
        if signal.regime == "uncertain":
            return 0.0  # sit in cash
        if (signal.win_rate < self.limits.win_rate_floor
                or breaker_active or state.flicker_rate > 4):
            return 1.0  # forced flat leverage
        if not signal.confirmed_breakout:
            return 1.0
        if signal.asset_class == "crypto":
            return self.limits.crypto_max_leverage
        if signal.asset_class == "letf":
            return self.limits.letf_max_leverage
        return 1.0

    # ---- the veto gate ----
    def validate_signal(self, signal: TradeSignal, state: PortfolioState) -> RiskDecision:
        mods: list[str] = []

        # 0. hard halts have absolute veto
        if self.hard_halted or self.kill_switch_engaged():
            return RiskDecision(False, None, "hard-halt lock active (manual delete required)", mods)
        if state.circuit_breaker_status in ("halt_day", "halt_week", "halt_hard"):
            return RiskDecision(False, None, f"circuit breaker active: {state.circuit_breaker_status}", mods)

        # 1. mandatory ATR trailing stop — refuse orders without one
        if signal.stop_loss is None or signal.atr <= 0:
            return RiskDecision(False, None, "no ATR trailing stop (mandatory)", mods)
        stop_dist = abs(signal.price - signal.stop_loss)
        if stop_dist <= 0 or signal.price <= 0:
            return RiskDecision(False, None, "invalid stop distance / price", mods)
        if signal.asset_class == "equity":
            buffered = max(stop_dist, self.limits.equity_gap_atr_mult * signal.atr)
            if buffered > stop_dist:
                mods.append(f"equity overnight-gap buffer: stop dist {stop_dist:.4f}->{buffered:.4f}")
                stop_dist = buffered

        # 2. speed order validation
        if signal.bid_ask_spread > self.limits.max_spread:
            return RiskDecision(False, None,
                                f"spread {signal.bid_ask_spread:.2%} > {self.limits.max_spread:.2%}", mods)
        if signal.timestamp is not None:
            for sym, dr, ts in self._recent_orders:
                if sym == signal.symbol and dr == signal.direction \
                        and (signal.timestamp - ts).total_seconds() < self.limits.dup_window_seconds:
                    return RiskDecision(False, None, "duplicate order within block window", mods)

        # 3. concurrency / frequency caps
        is_new = signal.symbol not in state.positions
        if is_new and len(state.positions) >= self.limits.max_concurrent:
            return RiskDecision(False, None, f"max concurrent positions ({self.limits.max_concurrent})", mods)
        if self._daily_trades >= self.limits.max_daily_trades:
            return RiskDecision(False, None, f"max daily trades ({self.limits.max_daily_trades})", mods)

        # 4. dynamic leverage matrix
        leverage = self.leverage_for(signal, state)
        if leverage <= 0.0:
            return RiskDecision(False, None, "leverage forced to cash (uncertain regime)", mods)

        # 5. fractional-Kelly, risk-based sizing:  size = equity * risk_f / stop_dist
        #    risk_f is HARD-CAPPED at risk_per_trade (course rule: loss if the stop
        #    is hit can never exceed 1-2% of equity).
        kelly_f = self.kelly_fraction_value() or self.limits.warmup_fraction
        risk_f = min(kelly_f, self.limits.risk_per_trade)
        if risk_f < kelly_f:
            mods.append(f"per-trade risk capped at {self.limits.risk_per_trade:.1%} (kelly wanted {kelly_f:.1%})")
        shares = (state.equity * risk_f) / stop_dist
        notional = shares * signal.price * leverage

        max_single = state.equity * self.limits.max_position_pct
        if notional > max_single:
            notional = max_single
            mods.append(f"clipped to {self.limits.max_position_pct:.0%} single-position cap")

        current_exposure = sum(abs(p.get("notional", 0.0)) for p in state.positions.values())
        max_total = state.equity * self.limits.max_total_exposure
        if current_exposure + notional > max_total:
            allowed = max(0.0, max_total - current_exposure)
            if allowed < self.limits.min_position_usd:
                return RiskDecision(False, None,
                                    f"max total exposure ({self.limits.max_total_exposure:.0%}) reached", mods)
            notional = allowed
            mods.append(f"clipped to {self.limits.max_total_exposure:.0%} total-exposure cap")

        # 6. correlation spectrum
        action, reason = self._correlation_action(signal, state)
        if action == "reject":
            return RiskDecision(False, None, reason, mods)
        if action == "reduce":
            notional *= (1.0 - self.limits.corr_reduce)
            mods.append(f"correlated co-hold: aggregate size -{self.limits.corr_reduce:.0%}")

        # 7. min-size floor
        if notional < self.limits.min_position_usd:
            return RiskDecision(False, None, f"below min position ${self.limits.min_position_usd:.0f}", mods)

        modified = replace(signal, target_notional=float(notional), leverage=float(leverage))

        # 8. PROACTIVE TAIL RISK (absolute veto, runs LAST so its cap is final).
        if self.tail_monitor is not None:
            tail = self.tail_monitor.validate_signal(modified, state)
            if tail is not None:
                if not tail.approved:
                    return RiskDecision(False, None, tail.rejection_reason, mods + tail.modifications)
                modified = tail.modified_signal
                mods.extend(tail.modifications)

        return RiskDecision(True, modified, None, mods)

    def register_fill(self, signal: TradeSignal) -> None:
        """Record a fill for duplicate-blocking and the daily-trade counter."""
        if signal.timestamp is not None:
            d = signal.timestamp.date()
            if self._trades_day != d:
                self._trades_day = d
                self._daily_trades = 0
            self._daily_trades += 1
            self._recent_orders.append((signal.symbol, signal.direction, signal.timestamp))
            self._recent_orders = self._recent_orders[-50:]

    def _correlation_action(self, signal: TradeSignal, state: PortfolioState) -> tuple[str | None, str | None]:
        if signal.returns is None:
            return (None, None)
        for sym, pos in state.positions.items():
            corr = _rolling_corr(signal.returns, pos.get("returns"), 30)
            if corr is not None and corr > self.limits.corr_threshold:
                same_sector = bool(signal.sector) and pos.get("sector") == signal.sector
                if not same_sector:
                    return ("reject", f"corr {corr:.2f} > {self.limits.corr_threshold} with {sym} (different sector)")
                return ("reduce", None)


# ===========================================================================
# PORTFOLIO-LEVEL RISK MANAGER (sits ABOVE the per-strategy managers)
# ===========================================================================
PORTFOLIO_LOCK = ROOT / "logs" / "portfolio_halted.lock"


@dataclass
class PortfolioRiskLimits:
    max_aggregate_exposure: float = 0.80   # gross positions <= 80% of portfolio
    max_single_symbol: float = 0.15        # aggregate per-symbol cap across strategies
    max_portfolio_leverage: float = 1.25   # gross leverage cap regardless of allocations
    daily_dd_reduce: float = 0.02          # portfolio daily DD -> halve new sizes
    daily_dd_zero: float = 0.03            # portfolio daily DD -> block new orders
    peak_dd_halt: float = 0.10             # portfolio peak DD -> halt + lock file
    corr_window: int = 60
    corr_cluster_threshold: float = 0.80
    max_cluster_exposure: float = 0.30     # combined correlated exposure cap
    min_position_usd: float = 100.0

    @classmethod
    def from_settings(cls, path: Path | str | None = None) -> "PortfolioRiskLimits":
        path = Path(path) if path else DEFAULT_SETTINGS
        try:
            import yaml
            data = (yaml.safe_load(path.read_text()) or {}).get("portfolio_risk", {})
        except Exception:
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


class PortfolioRiskManager:
    """
    Portfolio-wide risk layer with ABSOLUTE veto power on top of the per-strategy
    risk managers. Both layers must approve for an order to reach the executor.
    It aggregates exposure, single-symbol size, leverage, drawdown and correlated
    clusters ACROSS all strategies -- things a single strategy's manager cannot see.
    """

    def __init__(self, limits: PortfolioRiskLimits | None = None, lock_file: Path | str | None = None):
        self.limits = limits or PortfolioRiskLimits()
        self.lock_file = Path(lock_file) if lock_file else PORTFOLIO_LOCK
        self.blocked_log: list[dict] = []

    # ------------------------------------------------------------------
    @staticmethod
    def _gross_exposure(state: PortfolioState) -> float:
        return sum(abs(p.get("notional", 0.0)) for p in state.positions.values())

    @staticmethod
    def _symbol_signed(state: PortfolioState, symbol: str) -> float:
        p = state.positions.get(symbol)
        if not p:
            return 0.0
        return abs(p.get("notional", 0.0)) * float(p.get("direction", 1))

    def _block(self, strategy_name: str, reason: str, mods: list[str] | None = None) -> RiskDecision:
        self.blocked_log.append({
            "strategy": strategy_name, "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.warning("PortfolioRisk BLOCK [%s]: %s", strategy_name, reason)
        return RiskDecision(False, None, reason, mods or [])

    # ------------------------------------------------------------------
    # Individual checks (each returns None to pass, or a RiskDecision)
    # ------------------------------------------------------------------
    def check_portfolio_dd(self, portfolio_state: PortfolioState, signal: TradeSignal | None = None) -> RiskDecision | None:
        peak_dd = portfolio_state.drawdown
        daily_dd = portfolio_state.daily_drawdown
        if peak_dd > self.limits.peak_dd_halt:
            self._write_lock(peak_dd, portfolio_state.equity)
            return RiskDecision(False, None,
                                f"portfolio peak DD {peak_dd:.1%} > {self.limits.peak_dd_halt:.0%} -> HALT all trading (lock written)", [])
        if daily_dd > self.limits.daily_dd_zero:
            return RiskDecision(False, None,
                                f"portfolio daily DD {daily_dd:.1%} > {self.limits.daily_dd_zero:.0%} -> allocations to 0", [])
        if daily_dd > self.limits.daily_dd_reduce:
            mod = f"portfolio daily DD {daily_dd:.1%} > {self.limits.daily_dd_reduce:.0%} -> new size halved"
            if signal is not None:
                return RiskDecision(True, replace(signal, target_notional=signal.target_notional * 0.5), None, [mod])
            return RiskDecision(True, None, None, [mod])
        return None

    def check_aggregate_exposure(self, signal: TradeSignal, portfolio_state: PortfolioState) -> RiskDecision | None:
        gross = self._gross_exposure(portfolio_state)
        new = abs(signal.target_notional)
        cap = portfolio_state.equity * self.limits.max_aggregate_exposure
        if gross + new > cap + 1e-9:
            return RiskDecision(False, None,
                                f"aggregate exposure {(gross + new) / portfolio_state.equity:.0%} would exceed "
                                f"{self.limits.max_aggregate_exposure:.0%} (current {gross / portfolio_state.equity:.0%})", [])
        return None

    def check_symbol_aggregation(self, signal: TradeSignal, portfolio_state: PortfolioState) -> RiskDecision | None:
        cap = portfolio_state.equity * self.limits.max_single_symbol
        existing_signed = self._symbol_signed(portfolio_state, signal.symbol)
        desired_signed = abs(signal.target_notional) * signal.direction
        combined = existing_signed + desired_signed
        if abs(combined) <= cap + 1e-9:
            return None
        # Reduce the incoming size so the aggregate per-symbol exposure fits the cap.
        allowed_signed = (cap if desired_signed >= 0 else -cap) - existing_signed
        allowed_mag = max(0.0, allowed_signed * signal.direction)
        if allowed_mag < self.limits.min_position_usd:
            return RiskDecision(False, None,
                                f"{signal.symbol}: aggregate {abs(combined) / portfolio_state.equity:.0%} "
                                f"> {self.limits.max_single_symbol:.0%} single-symbol cap", [])
        return RiskDecision(True, replace(signal, target_notional=float(allowed_mag)), None,
                            [f"{signal.symbol}: reduced to respect {self.limits.max_single_symbol:.0%} single-symbol cap "
                             f"(existing {abs(existing_signed) / portfolio_state.equity:.0%})"])

    def check_total_leverage(self, signal: TradeSignal, portfolio_state: PortfolioState) -> RiskDecision | None:
        gross = self._gross_exposure(portfolio_state)
        new = abs(signal.target_notional)
        lev = (gross + new) / portfolio_state.equity if portfolio_state.equity else 0.0
        if lev > self.limits.max_portfolio_leverage + 1e-9:
            return RiskDecision(False, None,
                                f"portfolio leverage {lev:.2f}x would exceed {self.limits.max_portfolio_leverage:.2f}x cap", [])
        return None

    def check_correlation_cluster(self, signal: TradeSignal, portfolio_state: PortfolioState) -> RiskDecision | None:
        if signal.returns is None:
            return None
        cluster_exposure = abs(signal.target_notional)
        members: list[str] = []
        for sym, pos in portfolio_state.positions.items():
            corr = _rolling_corr(signal.returns, pos.get("returns"), self.limits.corr_window)
            if corr is not None and corr > self.limits.corr_cluster_threshold:
                cluster_exposure += abs(pos.get("notional", 0.0))
                members.append(sym)
        if members and cluster_exposure > portfolio_state.equity * self.limits.max_cluster_exposure + 1e-9:
            return RiskDecision(False, None,
                                f"correlated cluster {[signal.symbol] + members} exposure "
                                f"{cluster_exposure / portfolio_state.equity:.0%} > {self.limits.max_cluster_exposure:.0%}", [])
        return None

    # ------------------------------------------------------------------
    # Combined gate
    # ------------------------------------------------------------------
    def validate_signal(self, signal: TradeSignal, strategy_name: str, portfolio_state: PortfolioState) -> RiskDecision:
        sig = signal
        mods: list[str] = []
        checks = [
            lambda s: self.check_portfolio_dd(portfolio_state, s),
            lambda s: self.check_aggregate_exposure(s, portfolio_state),
            lambda s: self.check_symbol_aggregation(s, portfolio_state),
            lambda s: self.check_total_leverage(s, portfolio_state),
            lambda s: self.check_correlation_cluster(s, portfolio_state),
        ]
        for check in checks:
            result = check(sig)
            if result is None:
                continue
            if not result.approved:
                return self._block(strategy_name, result.rejection_reason, mods + result.modifications)
            if result.modified_signal is not None:
                sig = result.modified_signal
            mods.extend(result.modifications)
        return RiskDecision(True, sig, None, mods)

    # ------------------------------------------------------------------
    def _write_lock(self, peak_dd: float, equity: float) -> None:
        if not self.lock_file.exists():
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(
                "PORTFOLIO TRADING HALTED - peak drawdown breaker\n"
                f"peak_dd={peak_dd:.4f}\nequity={equity:.2f}\n"
                f"timestamp={datetime.now(timezone.utc).isoformat()}\n"
            )
            logger.error("PORTFOLIO peak DD %.1f%% -> HALT. Lock: %s", peak_dd * 100, self.lock_file)

    def clear_lock(self) -> None:
        if self.lock_file.exists():
            self.lock_file.unlink()

    def kill_switch_engaged(self) -> bool:
        return self.lock_file.exists()
        return (None, None)
