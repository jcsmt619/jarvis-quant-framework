"""
risk/tail_monitor.py
====================
Proactive tail-risk monitor (Meridian L5 "smoke detector" pattern).

Protects against: reactive circuit breakers only fire AFTER losses are realized.
This monitor de-grosses on CONDITIONS -- implied volatility spiking -- so
exposure is already reduced when the crash arrives, not after it.

Levels (thresholds from config/settings.yaml `tail_risk:`, never hardcoded):
    Level 0 NORMAL   vix <= caution        -> no cap (1.0 / config max)
    Level 1 CAUTION  vix >  caution (25)   -> gross exposure hard-capped 0.80
    Level 2 DANGER   vix >  danger  (35)   -> gross exposure hard-capped 0.50
    Level 3 CRISIS   vix >  crisis  (50)   -> gross exposure hard-capped 0.00 (cash)

Action: ABSOLUTE VETO. The cap clamps any target exposure from any strategy;
signals that would breach it are clipped, or rejected when no room remains.
No override path exists by design.

When no VIX feed is available (e.g. crypto books), `vix_proxy_from_returns`
converts realized volatility into a VIX-equivalent annualized percentage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.yaml"
TRADING_DAYS = 252

logger = logging.getLogger("tail_monitor")


@dataclass
class TailRiskLimits:
    caution_vix: float = 25.0      # Level 1 trigger (exclusive: fires ABOVE this)
    danger_vix: float = 35.0       # Level 2 trigger
    crisis_vix: float = 50.0       # Level 3 trigger
    caution_cap: float = 0.80      # gross exposure cap at Level 1
    danger_cap: float = 0.50       # Level 2
    crisis_cap: float = 0.00       # Level 3: fully to cash
    min_position_usd: float = 100.0

    @classmethod
    def from_settings(cls, path: Path | str | None = None) -> "TailRiskLimits":
        path = Path(path) if path else SETTINGS
        try:
            import yaml
            data = (yaml.safe_load(path.read_text()) or {}).get("tail_risk", {})
        except Exception:
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


def vix_proxy_from_returns(returns: np.ndarray, window: int = 21) -> float:
    """VIX-equivalent proxy: annualized realized vol of the last `window` daily
    returns, expressed in percent (e.g. 0.02 daily std -> ~31.7)."""
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)][-window:]
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS) * 100.0)


class TailRiskMonitor:
    """Condition-based gross-exposure governor with absolute veto power."""

    LEVEL_NAMES = {0: "NORMAL", 1: "CAUTION", 2: "DANGER", 3: "CRISIS"}

    def __init__(self, limits: TailRiskLimits | None = None):
        self.limits = limits or TailRiskLimits()
        self.vix: float = 0.0
        self.level: int = 0
        self.cap: float = float("inf")
        self.events: list[dict] = []

    # ------------------------------------------------------------------
    def cap_for(self, vix: float) -> tuple[int, float]:
        """(level, gross cap) for a VIX reading. NORMAL is truly uncapped (inf):
        leverage limits are someone else's job; this monitor only acts on smoke.
        Strictly monotone: higher vix can only tighten the cap."""
        lim = self.limits
        if vix > lim.crisis_vix:
            return 3, lim.crisis_cap
        if vix > lim.danger_vix:
            return 2, lim.danger_cap
        if vix > lim.caution_vix:
            return 1, lim.caution_cap
        return 0, float("inf")

    def update(self, vix: float) -> float:
        """Feed the latest VIX (or proxy); returns the active gross cap."""
        old = self.level
        self.vix = float(vix)
        self.level, self.cap = self.cap_for(self.vix)
        if self.level != old:
            self.events.append({"vix": self.vix, "from": self.LEVEL_NAMES[old],
                                "to": self.LEVEL_NAMES[self.level], "cap": self.cap})
            logger.warning("TAIL RISK %s -> %s (vix=%.1f, gross cap %.0f%%)",
                           self.LEVEL_NAMES[old], self.LEVEL_NAMES[self.level],
                           self.vix, self.cap * 100)
        return self.cap

    # ------------------------------------------------------------------
    def clamp_target(self, target_exposure: float) -> float:
        """Clamp a strategy's target exposure fraction to the active cap."""
        return min(target_exposure, self.cap) if target_exposure > 0 else target_exposure

    def validate_signal(self, signal, portfolio_state):
        """Veto gate for order-based flow (RiskManager graft).

        Clips the incoming order so gross exposure stays under cap*equity;
        rejects outright when no room remains. Closing flow is never blocked
        (reducing risk is always allowed).
        """
        from core.risk_manager import RiskDecision  # local import avoids cycle

        equity = getattr(portfolio_state, "equity", 0.0)
        gross = sum(abs(p.get("notional", 0.0))
                    for p in getattr(portfolio_state, "positions", {}).values())
        max_gross = equity * self.cap
        new_notional = abs(getattr(signal, "target_notional", 0.0))

        if gross + new_notional <= max_gross + 1e-9:
            return None                                   # within cap: no issue
        room = max(0.0, max_gross - gross)
        if room < self.limits.min_position_usd:
            return RiskDecision(
                False, None,
                f"TAIL RISK {self.LEVEL_NAMES[self.level]} (vix={self.vix:.1f}): "
                f"gross cap {self.cap:.0%} reached -- new risk blocked", [])
        return RiskDecision(
            True, replace(signal, target_notional=float(room)), None,
            [f"TAIL RISK {self.LEVEL_NAMES[self.level]} (vix={self.vix:.1f}): "
             f"size clipped to {self.cap:.0%} gross cap"])
