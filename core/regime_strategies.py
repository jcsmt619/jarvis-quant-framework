"""
core/regime_strategies.py
=========================
STEP 3 — the master volatility-based ALLOCATION blueprint. Three volatility-ranked
strategies plus a StrategyOrchestrator that maps HMM regimes to a target
allocation, leverage, and a mandatory ATR stop. This is a DRAWDOWN-CONTROL layer:
allocation scales inversely with volatility, and every strategy carries a stop so
exposure is cut when price breaks structure.

Key design point (from the spec): regimes are ranked by `expected_volatility`
(ascending) to compute `vol_rank`, completely INDEPENDENT of the return-sorted
human-readable labels. Low-vol -> aggressive long; high-vol -> defensive, never
short.

Per 01_CLAUDE.md: strategies inherit from BaseStrategy and implement
generate_signal(); no order is ever produced without a stop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass

import numpy as np

# High-beta 3x LETFs whose ATR stop distance is widened so normal 3x volatility
# swings do not shake the position out (whipsaw). This is a WIDER INITIAL stop at
# entry (recomputed each bar) -- it never moves an already-open stop further away,
# so it respects the 01_CLAUDE.md "stops can only tighten after open" rule.
HIGH_BETA_SYMBOLS = frozenset({"SOXL", "TQQQ"})
LETF_STOP_MULTIPLIER = 1.75  # within the requested 1.5x-2.0x band

# "Capped Satellite" doctrine (skool_dump.txt, Survival First): 3x LETFs are
# satellites, never core. Their target exposure is HARD-CAPPED at 10% of equity
# regardless of signal strength, so even a -75% LETF crash costs the portfolio
# ~7.5% -- inside the 25% peak-DD kill switch with a wide margin.
SATELLITE_CAP = 0.10


@dataclass
class AllocationSignal:
    allocation: float       # base target fraction of equity (pre-leverage)
    leverage: float
    stop_price: float
    orientation: str = "long"

    @property
    def target_exposure(self) -> float:
        return self.allocation * self.leverage


@dataclass
class AllocationDecision:
    target_exposure: float  # allocation * leverage, after confidence adjustment
    allocation: float
    leverage: float
    stop_price: float
    strategy: str
    vol_rank: int
    uncertain: bool
    rebalance: bool
    stop_widened: bool = False
    satellite_capped: bool = False


# ---------------------------------------------------------------------------
# Strategy classes
# ---------------------------------------------------------------------------
@dataclass
class StrategyHealth:
    is_healthy: bool
    recent_sharpe: float
    current_drawdown: float
    consecutive_losing_days: int
    reason_if_unhealthy: str | None = None


class BaseStrategy(ABC):
    name: str = "base"
    orientation: str = "long"

    # Health thresholds -- a strategy is UNHEALTHY if ANY is breached.
    MAX_DRAWDOWN = 0.15
    MIN_SHARPE = -1.0
    MAX_LOSING_DAYS = 10

    def __init__(self, name: str | None = None):
        if name:
            self.name = name
        self.is_enabled: bool = True
        self.allocated_capital: float = 0.0
        self.performance_history: deque[float] = deque(maxlen=252)  # rolling daily returns
        self.current_positions: dict = {}
        # config-driven fields (populated from settings.yaml by the registry loader)
        self.symbols: list[str] = []
        self.weight_min: float = 0.0
        self.weight_max: float = 1.0
        # internal drawdown / streak tracking
        self._equity: list[float] = [1.0]
        self._peak: float = 1.0
        self._consecutive_losing_days: int = 0

    @abstractmethod
    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        """Return the target allocation/leverage and the MANDATORY stop price.
        `stop_widen` scales the ATR stop distance (>1 = wider berth for LETFs)."""
        raise NotImplementedError

    def generate_signals(self, bars, regime_state) -> list:
        """Live multi-strategy hook: return a list of core.risk_manager.TradeSignal.
        Base implementation yields nothing; concrete live strategies override it.
        The multi-strategy engine can also be driven by an injected signal source."""
        return []

    # --- lifecycle hooks ---
    def on_enable(self) -> None:
        self.is_enabled = True

    def on_disable(self) -> None:
        self.is_enabled = False

    def reset_state(self) -> None:
        """Reset all runtime state (for a fresh backtest pass)."""
        self.is_enabled = True
        self.allocated_capital = 0.0
        self.performance_history.clear()
        self.current_positions = {}
        self._equity = [1.0]
        self._peak = 1.0
        self._consecutive_losing_days = 0

    # --- performance tracking ---
    def record_daily_return(self, daily_return: float) -> None:
        """Feed one day's return; updates history, equity peak and losing streak."""
        r = float(daily_return)
        self.performance_history.append(r)
        eq = self._equity[-1] * (1.0 + r)
        self._equity.append(eq)
        self._peak = max(self._peak, eq)
        self._consecutive_losing_days = self._consecutive_losing_days + 1 if r < 0 else 0

    def get_recent_sharpe(self, window_days: int = 60) -> float:
        data = list(self.performance_history)[-window_days:]
        if len(data) < 2:
            return 0.0
        arr = np.asarray(data, dtype=float)
        sd = arr.std(ddof=1)
        if sd < 1e-12:          # near-constant returns -> Sharpe is undefined
            return 0.0
        return float(arr.mean() / sd * np.sqrt(252.0))

    def get_current_drawdown(self) -> float:
        eq = self._equity[-1]
        return (self._peak - eq) / self._peak if self._peak > 0 else 0.0

    def health_check(self) -> StrategyHealth:
        sharpe = self.get_recent_sharpe(60)
        drawdown = self.get_current_drawdown()
        losing = self._consecutive_losing_days
        reason = None
        if drawdown > self.MAX_DRAWDOWN:
            reason = f"drawdown {drawdown:.1%} exceeds {self.MAX_DRAWDOWN:.0%}"
        elif sharpe < self.MIN_SHARPE:
            reason = f"60-day Sharpe {sharpe:.2f} below {self.MIN_SHARPE}"
        elif losing >= self.MAX_LOSING_DAYS:
            reason = f"{losing} consecutive losing days"
        return StrategyHealth(
            is_healthy=reason is None, recent_sharpe=sharpe,
            current_drawdown=drawdown, consecutive_losing_days=losing,
            reason_if_unhealthy=reason,
        )


class LowVolBullStrategy(BaseStrategy):
    """Lowest 1/3 volatility: aggressive long, 95% @ 1.25x."""
    name = "LowVolBull"

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        stop = max(price - 3.0 * stop_widen * atr, ema50 - 0.5 * stop_widen * atr)
        return AllocationSignal(allocation=0.95, leverage=1.25, stop_price=stop)


class MidVolCautiousStrategy(BaseStrategy):
    """Middle 1/3 volatility: long, trend-gated size, 1.0x."""
    name = "MidVolCautious"

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        stop = ema50 - 0.5 * stop_widen * atr
        allocation = 0.95 if price > ema50 else 0.60
        return AllocationSignal(allocation=allocation, leverage=1.0, stop_price=stop)


class HighVolDefensiveStrategy(BaseStrategy):
    """Top 1/3 volatility: defensive long ONLY (never short), 60% @ 1.0x."""
    name = "HighVolDefensive"

    def generate_signal(self, price: float, ema50: float, atr: float, stop_widen: float = 1.0) -> AllocationSignal:
        stop = ema50 - 1.0 * stop_widen * atr
        return AllocationSignal(allocation=0.60, leverage=1.0, stop_price=stop)


# Backward-compatible aliases (name -> class).
STRATEGY_ALIASES: dict[str, type[BaseStrategy]] = {
    "BearTrendStrategy": HighVolDefensiveStrategy,
    "CrashDefensiveStrategy": HighVolDefensiveStrategy,
    "MeanReversionStrategy": MidVolCautiousStrategy,
    "BullTrendStrategy": LowVolBullStrategy,
    "EuphoriaCautiousStrategy": LowVolBullStrategy,
}


def get_strategy(name: str) -> type[BaseStrategy]:
    """Resolve a strategy class by canonical name or legacy alias."""
    canonical = {c.name: c for c in (LowVolBullStrategy, MidVolCautiousStrategy, HighVolDefensiveStrategy)}
    if name in canonical:
        return canonical[name]
    if name in STRATEGY_ALIASES:
        return STRATEGY_ALIASES[name]
    raise KeyError(f"Unknown strategy '{name}'")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class StrategyOrchestrator:
    def __init__(
        self,
        regime_infos: dict,
        min_confidence: float = 0.55,
        rebalance_threshold: float = 0.10,
        uncertainty_mult: float = 0.50,
        symbol: str | None = None,
        letf_stop_multiplier: float = LETF_STOP_MULTIPLIER,
        satellite_cap: float = SATELLITE_CAP,
    ):
        """
        regime_infos: {regime_id: RegimeInfo} from the HMM engine. Each RegimeInfo
        must expose `.regime_id` and `.expected_volatility`.
        symbol: used to widen the ATR stop for high-beta 3x LETFs (SOXL/TQQQ)
        and to apply the hard satellite exposure cap to those same symbols.
        """
        self.regime_infos = regime_infos
        self.min_confidence = min_confidence
        self.rebalance_threshold = rebalance_threshold
        self.uncertainty_mult = uncertainty_mult
        self.symbol = (symbol or "").upper()
        self.is_satellite = self.symbol in HIGH_BETA_SYMBOLS
        self.stop_widen = letf_stop_multiplier if self.is_satellite else 1.0
        self.satellite_cap = satellite_cap

        # Rank by expected volatility ASCENDING -> vol_rank (independent of labels).
        ordered = sorted(regime_infos.values(), key=lambda ri: ri.expected_volatility)
        self.vol_rank: dict[int, int] = {ri.regime_id: rank for rank, ri in enumerate(ordered)}
        self.n_regimes = len(regime_infos)

        self._low = LowVolBullStrategy()
        self._mid = MidVolCautiousStrategy()
        self._high = HighVolDefensiveStrategy()

    def vol_rank_fraction(self, regime_id: int) -> float:
        rank = self.vol_rank.get(regime_id, 0)
        return rank / (self.n_regimes - 1) if self.n_regimes > 1 else 0.0

    def strategy_for_regime(self, regime_id: int) -> BaseStrategy:
        frac = self.vol_rank_fraction(regime_id)
        if frac <= 1.0 / 3.0:
            return self._low
        if frac <= 2.0 / 3.0:
            return self._mid
        return self._high

    def get_signal(
        self,
        regime_id: int,
        price: float,
        ema50: float,
        atr: float,
        probability: float,
        is_flickering: bool,
        active_allocation: float = 0.0,
    ) -> AllocationDecision:
        strategy = self.strategy_for_regime(regime_id)
        sig = strategy.generate_signal(price, ema50, atr, stop_widen=self.stop_widen)
        allocation, leverage = sig.allocation, sig.leverage

        # Confidence / uncertainty gate: halve allocation and force 1.0x leverage.
        uncertain = probability < self.min_confidence or is_flickering
        if uncertain:
            allocation *= self.uncertainty_mult
            leverage = 1.0

        target = allocation * leverage

        # Capped Satellite rule: high-beta 3x LETFs can NEVER exceed the cap,
        # regardless of regime, confidence, or signal strength. Hard, last, absolute.
        satellite_capped = False
        if self.is_satellite and target > self.satellite_cap:
            target = self.satellite_cap
            allocation = min(allocation, self.satellite_cap)
            leverage = 1.0
            satellite_capped = True

        rebalance = abs(target - active_allocation) > self.rebalance_threshold
        return AllocationDecision(
            target_exposure=target, allocation=allocation, leverage=leverage,
            stop_price=sig.stop_price, strategy=strategy.name,
            vol_rank=self.vol_rank.get(regime_id, 0), uncertain=uncertain, rebalance=rebalance,
            stop_widened=self.stop_widen > 1.0, satellite_capped=satellite_capped,
        )
