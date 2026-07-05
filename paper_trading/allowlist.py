"""
paper_trading/allowlist.py
==========================
Hardcoded strategy allowlist per docs/ALPACA_PAPER_TRADING_GATE_SPEC.md
Section 1 (Requirements #1, #2).

Only the strategy/asset/parameter combination explicitly classified
APPROVED_FOR_PAPER_TEST in docs/JARVIS_PAPER_TRADING_CANDIDATES.md may
be evaluated by the dry-run signal logger (and, later, by any live
paper-order-submitting phase). This is a Python constant, not a value
read from an environment variable, database, or other runtime-mutable
source, by design (spec Section 1): a config change alone must never be
able to silently add a second, unreviewed strategy.

Adding a second entry here requires a separate, explicit code change and
its own review -- it must never happen via a config flag, API call, or
runtime toggle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllowedStrategy:
    strategy: str
    asset: str
    params: dict

    def matches(self, strategy: str, asset: str, params: dict) -> bool:
        """Exact match on strategy family, asset, and every allowlisted
        parameter (extra keys in the incoming params are ignored so a
        caller passing a superset of params -- e.g. an internal id --
        does not spuriously fail the check; MISSING or MISMATCHED
        allowlisted keys DO fail it)."""
        if strategy != self.strategy or asset != self.asset:
            return False
        for key, value in self.params.items():
            if params.get(key) != value:
                return False
        return True


# The single approved candidate, per docs/JARVIS_PAPER_TRADING_CANDIDATES.md
# candidate #1: EEM rsi_revert(window=14, oversold=30, overbought=70),
# classified APPROVED_FOR_PAPER_TEST (PRIMARY).
ALLOWED_STRATEGIES: tuple[AllowedStrategy, ...] = (
    AllowedStrategy(
        strategy="rsi_revert",
        asset="EEM",
        params={"window": 14, "oversold": 30, "overbought": 70},
    ),
)


def is_allowed(strategy: str, asset: str, params: dict) -> bool:
    """True only if (strategy, asset, params) exactly matches an
    allowlisted entry. Refuses everything else, with no exceptions."""
    return any(a.matches(strategy, asset, params) for a in ALLOWED_STRATEGIES)


class NotAllowedError(RuntimeError):
    """Raised when a caller attempts to evaluate a non-allowlisted
    strategy/asset/parameter combination. This must always halt dry-run
    evaluation for that request -- it is never a soft warning."""
