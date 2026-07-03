"""
utils/friction.py
=================
Institutional friction engine (Meridian L4 transaction-cost blueprint):
commissions, bid-ask spread, square-root market impact, and short borrow.

Corrections vs the draft it was adapted from:
  * Added the BID-ASK SPREAD component -- the sqrt-impact term vanishes as
    order size -> 0, but every order pays the half-spread. Without it, small
    orders are modeled as free, which flatters high-turnover strategies.
  * Borrow rate is PER-LEG: hard-to-borrow (SOXL-class) defaults to 8%/yr;
    general-collateral mega-caps ~0.5%/yr. Using 8% for GC names would
    overstate a market-neutral book's costs ~15x.
  * The impact law is sqrt (concave), per Almgren et al -- the draft's
    "quadratic scaling" comment was wrong.

Costs err PESSIMISTIC by design (per the course: "erring pessimistic rather
than optimistic").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TRADING_DAYS = 252


@dataclass
class FrictionConfig:
    commission_per_share: float = 0.005     # prime-brokerage per-share
    min_commission: float = 1.00            # minimum ticket per leg
    spread_frac_of_range: float = 0.05      # spread ~ 5% of avg daily H-L range (L4 spec)
    impact_coef: float = 0.10               # sqrt-law coefficient (L4 spec)
    gc_borrow_annual: float = 0.005         # general collateral (mega-caps)
    htb_borrow_annual: float = 0.08         # hard-to-borrow (volatile LETF legs)


class InstitutionalFrictionEngine:
    def __init__(self, config: FrictionConfig | None = None):
        self.cfg = config or FrictionConfig()

    # ------------------------------------------------------------------
    def half_spread(self, price: float, daily_range: float) -> float:
        """Half the effective bid-ask spread, estimated from the avg daily
        high-low range (crossing the spread costs half of it per leg)."""
        if price <= 0 or daily_range <= 0:
            return 0.0
        return 0.5 * self.cfg.spread_frac_of_range * daily_range

    def market_impact(self, price: float, atr: float, order_shares: float,
                      adv_shares: float) -> float:
        """Per-share market impact: sqrt participation law, volatility-scaled.
        impact = coef * (ATR/price) * sqrt(size/ADV) * price
        """
        if adv_shares <= 0 or order_shares <= 0 or price <= 0 or atr <= 0:
            return 0.0
        participation = order_shares / adv_shares
        return price * self.cfg.impact_coef * (atr / price) * np.sqrt(participation)

    def execution_cost(self, price: float, order_shares: float, atr: float,
                       adv_shares: float, daily_range: float | None = None) -> float:
        """Total dollars of friction for ONE leg (entry or exit)."""
        if order_shares <= 0:
            return 0.0
        commission = max(self.cfg.commission_per_share * order_shares,
                         self.cfg.min_commission)
        spread = self.half_spread(price, daily_range if daily_range is not None else atr)
        impact = self.market_impact(price, atr, order_shares, adv_shares)
        return commission + (spread + impact) * order_shares

    # ------------------------------------------------------------------
    def short_borrow_cost(self, short_value: float, days_held: float,
                          hard_to_borrow: bool = False) -> float:
        """Compounded borrow cost for holding a short leg `days_held` days."""
        if short_value <= 0 or days_held <= 0:
            return 0.0
        annual = self.cfg.htb_borrow_annual if hard_to_borrow else self.cfg.gc_borrow_annual
        daily = annual / 365.25
        return short_value * ((1.0 + daily) ** days_held - 1.0)

    def daily_borrow_drag(self, short_gross_fraction: float,
                          hard_to_borrow: bool = False) -> float:
        """Per-trading-day return drag from carrying a short book of
        `short_gross_fraction` x equity. The full annual borrow accrues over
        the calendar year but is booked across 252 trading days."""
        if short_gross_fraction <= 0:
            return 0.0
        annual = self.cfg.htb_borrow_annual if hard_to_borrow else self.cfg.gc_borrow_annual
        return short_gross_fraction * annual / TRADING_DAYS
