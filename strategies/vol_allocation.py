"""
strategies/vol_allocation.py
============================
Volatility-based allocation policy (STEP 3 mechanics) that the walk-forward
backtester consumes. It converts the HMM's volatility RANK of the current
regime into a target portfolio allocation:

    calm  -> fully invested (optionally levered up to low_vol_leverage)
    mid   -> partial, split by the 200-SMA trend gate
    high  -> defensive

Design philosophy (from the course): the HMM classifies VOLATILITY, not price
direction. Allocation scales inversely with volatility. Defaults match the
STEP 1 settings.yaml block.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationSettings:
    low_vol_allocation: float = 0.95
    mid_vol_allocation_trend: float = 0.95
    mid_vol_allocation_no_trend: float = 0.60
    high_vol_allocation: float = 0.60
    low_vol_leverage: float = 1.25
    max_leverage: float = 1.25
    uncertainty_size_mult: float = 0.50   # applied when regime is low-confidence / flickering
    transition_size_mult: float = 0.75    # applied while a regime switch is unconfirmed
    min_confidence: float = 0.55


def target_allocation(
    vol_rank_frac: float,
    above_200sma: bool,
    settings: AllocationSettings | None = None,
) -> float:
    """
    Map a regime's volatility rank fraction (0 = calmest, 1 = most turbulent)
    to a base target allocation, before confidence/transition adjustments.
    """
    s = settings or AllocationSettings()
    if vol_rank_frac <= 1.0 / 3.0:
        alloc = s.low_vol_allocation * s.low_vol_leverage
    elif vol_rank_frac <= 2.0 / 3.0:
        alloc = s.mid_vol_allocation_trend if above_200sma else s.mid_vol_allocation_no_trend
    else:
        alloc = s.high_vol_allocation
    return min(alloc, s.max_leverage)


def adjust_for_confidence(
    base_alloc: float,
    probability: float,
    is_confirmed: bool,
    is_flickering: bool,
    settings: AllocationSettings | None = None,
) -> float:
    """Reduce size when the regime signal is uncertain or mid-transition."""
    s = settings or AllocationSettings()
    alloc = base_alloc
    if probability < s.min_confidence or is_flickering:
        alloc *= s.uncertainty_size_mult
    if not is_confirmed:
        alloc *= s.transition_size_mult
    return max(0.0, min(alloc, s.max_leverage))
