"""
execution/multistrat_engine.py
==============================
Multi-strategy LIVE orchestration engine (dry-run / simulation).

It wires the REAL risk architecture together exactly as a production loop would,
but drives it with a mock feed + mock order executor so nothing hits a broker
(01_CLAUDE.md rule 4 -- never default to live). Each bar:

    for each ACTIVE strategy:
        signals = signal_source(strategy, bars, regime_state)
        for signal:
            strat_decision = strategy.risk_manager.validate_signal(signal, state)
            if approved:
                port_decision = portfolio_risk.validate_signal(mod_signal, name, state)
                if approved:
                    executor.submit(final_signal); log_decision(...)

Both risk layers hold ABSOLUTE veto power; both must approve. Health checks run
every bar (unhealthy -> on_disable + alert); the allocator runs on its weekly
schedule and excludes disabled strategies on its next pass.

Everything here is deterministic given a seed, so tests can assert exact
propagation (disable -> allocator, portfolio override, rebalance cadence).
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capital_allocator import CapitalAllocator, PortfolioSnapshot
from core.regime_strategies import BaseStrategy
from core.risk_manager import (
    PortfolioRiskManager,
    PortfolioState,
    RiskDecision,
    RiskManager,
    TradeSignal,
)
from core.strategy_registry import StrategyRegistry
from monitoring.alerts import AlertManager
from monitoring.dashboard import DashboardState, Position, StrategyAllocation
from monitoring.logger import get_logger

# A signal source turns (strategy, bars, regime_state) into candidate TradeSignals.
SignalSource = Callable[[BaseStrategy, dict, dict], "list[TradeSignal]"]


@dataclass
class BarContext:
    timestamp: datetime
    bars: dict                                  # symbol -> recent price info
    regime_state: dict                          # {label, risk_on, probability, vol_level, stability}
    strategy_returns: dict | None = None        # optional per-strategy realized return this bar


@dataclass
class ExecutionRecord:
    strategy: str
    symbol: str
    stage: str                                  # submitted | blocked_strategy | blocked_portfolio
    approved: bool
    reason: str | None = None
    notional: float = 0.0


class MockOrderExecutor:
    """Records orders instead of routing them. NEVER sends to a broker."""

    def __init__(self):
        self.submitted: list[tuple[str, TradeSignal]] = []
        self._log = get_logger("execution", log_file="execution.jsonl")

    def submit(self, signal: TradeSignal, strategy_name: str) -> bool:
        self.submitted.append((strategy_name, signal))
        self._log.info(
            "order_submitted",
            extra={"extra_fields": {
                "strategy": strategy_name, "symbol": signal.symbol,
                "direction": signal.direction, "notional": round(signal.target_notional, 2),
                "leverage": signal.leverage, "dry_run": True,
            }},
        )
        return True


class MultiStratLiveEngine:
    def __init__(
        self,
        registry: StrategyRegistry,
        allocator: CapitalAllocator,
        portfolio_risk: PortfolioRiskManager | None,
        risk_managers: dict[str, RiskManager],
        signal_source: SignalSource | None = None,
        executor: MockOrderExecutor | None = None,
        alerts: AlertManager | None = None,
        initial_capital: float = 100000.0,
    ):
        self.registry = registry
        self.allocator = allocator
        self.portfolio_risk = portfolio_risk
        self.risk_managers = risk_managers
        self.signal_source = signal_source or (lambda strat, bars, regime: strat.generate_signals(bars, regime))
        self.executor = executor or MockOrderExecutor()
        self.alerts = alerts or AlertManager()
        self._log = get_logger("trading")

        self.equity = float(initial_capital)
        self.peak_equity = float(initial_capital)
        self.day_start_equity = float(initial_capital)
        self.week_start_equity = float(initial_capital)
        self.positions: dict[str, dict] = {}
        self.position_meta: dict[str, dict] = {}       # symbol -> {price, stop}

        self._last_rebalance_week: tuple[int, int] | None = None
        self._last_day: datetime.date | None = None
        self.last_changes: list = []
        self.disabled: set[str] = set()

        # Attach each risk manager to its strategy so `strategy.risk_manager` works
        # (matches the production call site) without changing the class definition.
        for name, rm in self.risk_managers.items():
            if name in self.registry:
                setattr(self.registry.get(name), "risk_manager", rm)

    # ------------------------------------------------------------------
    def initialize(self, timestamp: datetime | None = None) -> list:
        """Set day/week baselines and run the INITIAL allocator pass."""
        ts = timestamp or datetime.now(timezone.utc)
        self._last_day = ts.date()
        return self._rebalance(ts, initial=True)

    # ------------------------------------------------------------------
    def on_bar(self, ctx: BarContext) -> list[ExecutionRecord]:
        # roll daily / weekly P&L baselines
        self._roll_periods(ctx.timestamp)

        # feed realized returns so health checks + allocator vol have data
        if ctx.strategy_returns:
            for name, r in ctx.strategy_returns.items():
                if name in self.registry:
                    self.registry.get(name).record_daily_return(float(r))

        # 1. allocator runs on its weekly schedule (before signals so weights apply)
        self._maybe_rebalance(ctx.timestamp)

        # 2. per-bar signal processing through BOTH risk layers
        records: list[ExecutionRecord] = []
        for name, strat in list(self.registry.active().items()):
            signals = self.signal_source(strat, ctx.bars, ctx.regime_state) or []
            for sig in signals:
                records.append(self._process_signal(name, strat, sig))

        # 3. health checks every bar (disable + alert; allocator excludes next run)
        self._run_health_checks()

        # 4. correlation-cluster surveillance
        self._detect_correlation_clusters(ctx.timestamp)

        return records

    # ------------------------------------------------------------------
    def _process_signal(self, name: str, strat: BaseStrategy, sig: TradeSignal) -> ExecutionRecord:
        state = self.portfolio_state()
        rm: RiskManager = getattr(strat, "risk_manager", None) or self.risk_managers[name]
        strat_dec = rm.validate_signal(sig, state)
        if not strat_dec.approved:
            self._log_decision(name, sig, strat_dec, None)
            return ExecutionRecord(name, sig.symbol, "blocked_strategy", False, strat_dec.rejection_reason)

        mod_sig = strat_dec.modified_signal
        if self.portfolio_risk is not None:
            port_dec = self.portfolio_risk.validate_signal(mod_sig, name, state)
        else:  # --no-portfolio-risk debug mode
            port_dec = RiskDecision(True, mod_sig, None, ["portfolio-risk DISABLED (debug)"])

        self._log_decision(name, sig, strat_dec, port_dec)
        if not port_dec.approved:
            reason = port_dec.rejection_reason or ""
            if "DD" in reason:
                self.alerts.portfolio_dd_breaker("portfolio", state.drawdown, state.equity)
            return ExecutionRecord(name, mod_sig.symbol, "blocked_portfolio", False, reason)

        final = port_dec.modified_signal
        self.executor.submit(final, name)
        self._apply_fill(final)
        return ExecutionRecord(name, final.symbol, "submitted", True, None, final.target_notional)

    # ------------------------------------------------------------------
    def _run_health_checks(self) -> None:
        for name, strat in list(self.registry.active().items()):
            health = strat.health_check()
            if not health.is_healthy:
                strat.on_disable()
                self.disabled.add(name)
                self.alerts.strategy_disabled(name, health.reason_if_unhealthy)
                self._log.info(
                    "strategy_disabled",
                    extra={"extra_fields": {"strategy": name, "reason": health.reason_if_unhealthy}},
                )

    # ------------------------------------------------------------------
    def _detect_correlation_clusters(self, ts: datetime) -> None:
        corr = self.allocator.compute_correlation_matrix()
        names = list(corr.columns)
        threshold = self.allocator.config.corr_merge_threshold
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                c = corr.loc[a, b]
                if c == c and c > threshold:  # c==c filters NaN
                    self.alerts.correlation_cluster((a, b), float(c), ts)

    # ------------------------------------------------------------------
    def _maybe_rebalance(self, ts: datetime) -> list | None:
        week = ts.isocalendar()[:2]
        if self._last_rebalance_week is not None and week == self._last_rebalance_week:
            return None
        return self._rebalance(ts)

    def force_rebalance(self, ts: datetime | None = None) -> list:
        return self._rebalance(ts or datetime.now(timezone.utc))

    def _rebalance(self, ts: datetime, initial: bool = False) -> list:
        self._last_rebalance_week = ts.isocalendar()[:2]
        snapshot = PortfolioSnapshot(total_capital=self.equity, daily_drawdown=self._daily_dd())
        changes = self.allocator.rebalance(self.registry, snapshot)
        self.last_changes = changes
        if changes:
            self.alerts.allocator_rebalance(len(changes), ts)
        self._log.info(
            "allocator_rebalance",
            extra={"extra_fields": {
                "initial": initial, "timestamp": ts.isoformat(),
                "weights": {n: round(s.allocated_capital / self.equity, 4) if self.equity else 0.0
                            for n, s in self.registry.all().items()},
            }},
        )
        return changes

    # ------------------------------------------------------------------
    # Portfolio bookkeeping
    # ------------------------------------------------------------------
    def _roll_periods(self, ts: datetime) -> None:
        day = ts.date()
        if self._last_day is None:
            self._last_day = day
        if day != self._last_day:
            self.day_start_equity = self.equity
            if ts.weekday() == 0:  # Monday -> new trading week
                self.week_start_equity = self.equity
            self._last_day = day

    def _daily_dd(self) -> float:
        if self.day_start_equity <= 0:
            return 0.0
        return max(0.0, (self.day_start_equity - self.equity) / self.day_start_equity)

    def apply_pnl(self, pnl: float) -> None:
        """Advance simulated equity (dry-run only)."""
        self.equity += float(pnl)
        self.peak_equity = max(self.peak_equity, self.equity)

    def portfolio_state(self) -> PortfolioState:
        peak = max(self.peak_equity, self.equity)
        drawdown = (peak - self.equity) / peak if peak > 0 else 0.0
        weekly_dd = (max(0.0, (self.week_start_equity - self.equity) / self.week_start_equity)
                     if self.week_start_equity > 0 else 0.0)
        return PortfolioState(
            equity=self.equity, cash=self.equity, buying_power=self.equity,
            positions=self.positions, daily_pnl=self.equity - self.day_start_equity,
            weekly_pnl=self.equity - self.week_start_equity, peak_equity=peak,
            drawdown=drawdown, daily_drawdown=self._daily_dd(), weekly_drawdown=weekly_dd,
            circuit_breaker_status="normal", flicker_rate=0,
        )

    def _apply_fill(self, signal: TradeSignal) -> None:
        pos = self.positions.setdefault(
            signal.symbol, {"notional": 0.0, "direction": signal.direction, "returns": None, "sector": None})
        pos["notional"] = abs(pos.get("notional", 0.0)) + abs(signal.target_notional)
        pos["direction"] = signal.direction
        if signal.returns is not None:
            pos["returns"] = signal.returns
        pos["sector"] = signal.sector
        self.position_meta[signal.symbol] = {"price": signal.price, "stop": signal.stop_loss or 0.0}

    def seed_position(self, symbol: str, notional: float, direction: int = 1,
                      price: float = 100.0, stop: float = 95.0, returns=None, sector=None) -> None:
        """Test/helper: place an existing position without going through the pipeline."""
        self.positions[symbol] = {"notional": abs(notional), "direction": direction,
                                   "returns": returns, "sector": sector}
        self.position_meta[symbol] = {"price": price, "stop": stop}

    # ------------------------------------------------------------------
    def _log_decision(self, name: str, signal: TradeSignal, strat_dec: RiskDecision,
                      port_dec: RiskDecision | None) -> None:
        self._log.info(
            "trade_decision",
            extra={"extra_fields": {
                "strategy": name, "symbol": signal.symbol, "direction": signal.direction,
                "strategy_approved": strat_dec.approved,
                "strategy_reason": strat_dec.rejection_reason,
                "strategy_mods": strat_dec.modifications,
                "portfolio_approved": None if port_dec is None else port_dec.approved,
                "portfolio_reason": None if port_dec is None else port_dec.rejection_reason,
            }},
        )

    # ------------------------------------------------------------------
    def _status(self, strat: BaseStrategy) -> str:
        if not strat.is_enabled:
            return "Disabled"
        health = strat.health_check()
        if not health.is_healthy:
            return "Watch"
        return "Watch" if health.recent_sharpe < 0 else "Healthy"

    def build_dashboard_state(self, ctx: BarContext) -> DashboardState:
        rows: list[StrategyAllocation] = []
        for name, strat in self.registry.all().items():
            weight = (strat.allocated_capital / self.equity * 100.0) if self.equity else 0.0
            rows.append(StrategyAllocation(
                name=name, weight_pct=weight,
                sharpe=strat.get_recent_sharpe(60), status=self._status(strat)))

        positions = []
        for sym, pos in self.positions.items():
            meta = self.position_meta.get(sym, {})
            positions.append(Position(
                symbol=sym, side="LONG" if pos.get("direction", 1) >= 0 else "SHORT",
                price=meta.get("price", 0.0), pnl_pct=0.0, stop=meta.get("stop", 0.0)))

        gross = sum(abs(p.get("notional", 0.0)) for p in self.positions.values())
        rs = ctx.regime_state
        return DashboardState(
            regime_label=rs.get("label", "NEUTRAL"), risk_on=rs.get("risk_on", False),
            stability_bars=rs.get("stability", 0), vol_level=rs.get("vol_level", "Mid"),
            equity=self.equity, daily_pnl=self.equity - self.day_start_equity,
            daily_pnl_pct=(self.equity - self.day_start_equity) / max(1.0, self.day_start_equity) * 100.0,
            allocation_pct=(gross / self.equity * 100.0) if self.equity else 0.0,
            leverage=(gross / self.equity) if self.equity else 0.0,
            positions=positions, daily_dd=self._daily_dd(),
            peak_dd=(self.peak_equity - self.equity) / self.peak_equity if self.peak_equity > 0 else 0.0,
            strategy_rows=rows, cash_reserve_pct=self.allocator.config.reserve * 100.0,
        )


# ---------------------------------------------------------------------------
# Simulation helpers (dry-run feed + signal source)
# ---------------------------------------------------------------------------
class SimulatedFeed:
    """Deterministic bar/regime feed for the dry-run dashboard."""

    def __init__(self, symbols: dict[str, float], seed: int = 7, start: datetime | None = None):
        self._rng = random.Random(seed)
        self._prices = dict(symbols)
        self._t = start or datetime(2025, 1, 6, tzinfo=timezone.utc)  # a Monday
        self.regime = "BULL"
        self.stability = 1

    def next_bar(self) -> BarContext:
        bars = {}
        for sym in self._prices:
            drift = self._rng.uniform(-0.02, 0.025)
            self._prices[sym] *= (1.0 + drift)
            atr = max(0.5, self._prices[sym] * 0.02)
            bars[sym] = {"price": self._prices[sym], "atr": atr,
                         "ema50": self._prices[sym] * (1.0 - self._rng.uniform(-0.01, 0.02))}
        if self._rng.random() < 0.12:
            self.regime = "BEAR" if self.regime == "BULL" else "BULL"
            self.stability = 1
        else:
            self.stability += 1
        risk_on = self.regime == "BULL"
        ctx = BarContext(
            timestamp=self._t,
            bars=bars,
            regime_state={"label": self.regime, "risk_on": risk_on,
                          "probability": 0.70, "vol_level": "Low" if risk_on else "High",
                          "stability": self.stability},
            strategy_returns=None,
        )
        self._t += timedelta(days=1)
        return ctx


def simulated_signal_source(strategy: BaseStrategy, bars: dict, regime_state: dict) -> list[TradeSignal]:
    """Fabricate a valid, stop-protected TradeSignal per bar for the dry run.

    RISK OFF regimes yield an 'uncertain' signal (leverage->cash), so the
    per-strategy RiskManager rejects it -- exactly what should happen live.
    """
    if not strategy.symbols or not bars:
        return []
    symbol = strategy.symbols[0]
    bar = bars.get(symbol)
    if bar is None:
        return []
    price, atr = float(bar["price"]), float(bar["atr"])
    risk_on = regime_state.get("risk_on", False)
    return [TradeSignal(
        symbol=symbol, direction=1, asset_class="equity", price=price, atr=atr,
        stop_loss=price - 2.0 * atr,
        regime="confirmed_low_vol" if risk_on else "uncertain",
        confirmed_breakout=risk_on, win_rate=0.55, bid_ask_spread=0.0005,
        sector=symbol, timestamp=None,
    )]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def build_live_engine(
    registry: StrategyRegistry,
    allocator: CapitalAllocator,
    use_portfolio_risk: bool = True,
    signal_source: SignalSource | None = None,
    initial_capital: float = 100000.0,
    alerts: AlertManager | None = None,
) -> MultiStratLiveEngine:
    """Assemble an engine with one RiskManager per registered strategy."""
    risk_managers = {name: RiskManager(initial_capital=initial_capital)
                     for name in registry.all()}
    portfolio_risk = PortfolioRiskManager() if use_portfolio_risk else None
    return MultiStratLiveEngine(
        registry=registry, allocator=allocator, portfolio_risk=portfolio_risk,
        risk_managers=risk_managers, signal_source=signal_source,
        alerts=alerts, initial_capital=initial_capital,
    )
