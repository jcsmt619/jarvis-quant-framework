"""Futures instrument specifications, P&L math, and contract rollover.

This is the layer that makes the system futures-aware. Everything downstream
(sizing, risk, fills, backtest P&L) goes through an :class:`InstrumentSpec` so
that a one-tick move is converted to dollars correctly for each product.

Margins here are representative day-trade values and vary by broker and prop
firm. They are starting points only. Override them in config to match the
margins your broker or funded account actually charges.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math


# Quarterly contract month codes used by the major index/commodity futures.
# H=Mar, M=Jun, U=Sep, Z=Dec. These four months are the standard roll cycle.
QUARTERLY_MONTH_CODES: dict[int, str] = {3: "H", 6: "M", 9: "U", 12: "Z"}
QUARTERLY_MONTHS = sorted(QUARTERLY_MONTH_CODES.keys())


@dataclass(frozen=True)
class InstrumentSpec:
    """Static contract specification for one futures product.

    Attributes
    ----------
    symbol : str
        Root symbol (e.g. "NQ", "MNQ", "ES").
    description : str
        Human-readable name.
    exchange : str
        Listing exchange (e.g. "CME").
    tick_size : float
        Minimum price increment in index/price points (e.g. 0.25 for NQ).
    tick_value : float
        Dollar value of one tick for one contract (e.g. 5.0 for NQ).
    currency : str
        Settlement currency.
    day_margin : float
        Representative intraday margin per contract (USD). Broker-dependent.
    overnight_margin : float
        Representative overnight/initial margin per contract (USD).
    is_micro : bool
        True for micro contracts (1/10th notional of the e-mini).
    """

    symbol: str
    description: str
    exchange: str
    tick_size: float
    tick_value: float
    currency: str = "USD"
    day_margin: float = 0.0
    overnight_margin: float = 0.0
    is_micro: bool = False

    @property
    def point_value(self) -> float:
        """Dollar value of a one full point move for one contract."""
        return self.tick_value / self.tick_size

    def round_to_tick(self, price: float) -> float:
        """Snap an arbitrary price to the nearest valid tick."""
        return round(price / self.tick_size) * self.tick_size

    def ticks_between(self, price_a: float, price_b: float) -> float:
        """Signed number of ticks from price_a to price_b."""
        return (price_b - price_a) / self.tick_size

    def ticks_to_dollars(self, n_ticks: float, contracts: int = 1) -> float:
        """Convert a tick distance into dollars for ``contracts`` contracts."""
        return n_ticks * self.tick_value * contracts

    def pnl(
        self,
        entry_price: float,
        exit_price: float,
        contracts: int,
        direction: str,
    ) -> float:
        """Realized dollar P&L for a closed position.

        Parameters
        ----------
        direction : str
            "long" or "short".
        """
        sign = 1.0 if direction.lower() == "long" else -1.0
        n_ticks = self.ticks_between(entry_price, exit_price)
        return sign * self.ticks_to_dollars(n_ticks, contracts)

    def stop_distance_ticks(self, entry_price: float, stop_price: float) -> float:
        """Absolute distance from entry to stop, in ticks (always positive)."""
        return abs(self.ticks_between(entry_price, stop_price))


# --------------------------------------------------------------------------
# Built-in registry of the most commonly traded retail futures.
# Day margins are representative; confirm against your own broker/prop firm.
# --------------------------------------------------------------------------

_REGISTRY: dict[str, InstrumentSpec] = {
    "NQ":  InstrumentSpec("NQ",  "E-mini Nasdaq-100",  "CME",  0.25, 5.00,  day_margin=1800, overnight_margin=21000),
    "MNQ": InstrumentSpec("MNQ", "Micro Nasdaq-100",   "CME",  0.25, 0.50,  day_margin=180,  overnight_margin=2100,  is_micro=True),
    "ES":  InstrumentSpec("ES",  "E-mini S&P 500",     "CME",  0.25, 12.50, day_margin=1300, overnight_margin=13200),
    "MES": InstrumentSpec("MES", "Micro S&P 500",      "CME",  0.25, 1.25,  day_margin=130,  overnight_margin=1320,  is_micro=True),
    "RTY": InstrumentSpec("RTY", "E-mini Russell 2000","CME",  0.10, 5.00,  day_margin=900,  overnight_margin=8500),
    "M2K": InstrumentSpec("M2K", "Micro Russell 2000", "CME",  0.10, 0.50,  day_margin=90,   overnight_margin=850,   is_micro=True),
    "YM":  InstrumentSpec("YM",  "E-mini Dow",         "CBOT", 1.00, 5.00,  day_margin=1100, overnight_margin=11000),
    "MYM": InstrumentSpec("MYM", "Micro Dow",          "CBOT", 1.00, 0.50,  day_margin=110,  overnight_margin=1100,  is_micro=True),
    "CL":  InstrumentSpec("CL",  "Crude Oil",          "NYMEX",0.01, 10.00, day_margin=2400, overnight_margin=6600),
    "MCL": InstrumentSpec("MCL", "Micro Crude Oil",    "NYMEX",0.01, 1.00,  day_margin=240,  overnight_margin=660,   is_micro=True),
    "GC":  InstrumentSpec("GC",  "Gold",               "COMEX",0.10, 10.00, day_margin=2200, overnight_margin=11000),
    "MGC": InstrumentSpec("MGC", "Micro Gold",         "COMEX",0.10, 1.00,  day_margin=220,  overnight_margin=1100,  is_micro=True),
}


def get_instrument(symbol: str) -> InstrumentSpec:
    """Look up a built-in instrument spec by root symbol (case-insensitive)."""
    root = _strip_contract_code(symbol).upper()
    if root not in _REGISTRY:
        raise KeyError(
            f"Unknown instrument '{symbol}'. Known roots: {sorted(_REGISTRY)}. "
            "Add it to core.instruments._REGISTRY or pass overrides in config."
        )
    return _REGISTRY[root]


def register_instrument(spec: InstrumentSpec) -> None:
    """Add or replace an instrument in the registry (used for config overrides)."""
    _REGISTRY[spec.symbol.upper()] = spec


def all_symbols() -> list[str]:
    return sorted(_REGISTRY)


def apply_overrides(symbol: str, overrides: dict) -> InstrumentSpec:
    """Return a spec with config overrides applied (e.g. broker-specific margin)."""
    base = get_instrument(symbol)
    fields = {
        "symbol": base.symbol, "description": base.description, "exchange": base.exchange,
        "tick_size": base.tick_size, "tick_value": base.tick_value, "currency": base.currency,
        "day_margin": base.day_margin, "overnight_margin": base.overnight_margin, "is_micro": base.is_micro,
    }
    for k, v in (overrides or {}).items():
        if k in fields:
            fields[k] = v
    spec = InstrumentSpec(**fields)
    register_instrument(spec)
    return spec


# --------------------------------------------------------------------------
# Continuous contract / rollover helpers
# --------------------------------------------------------------------------

def _strip_contract_code(symbol: str) -> str:
    """Strip a trailing month+year code if present (e.g. 'NQH6' -> 'NQ')."""
    s = symbol.strip().upper()
    # Remove a trailing single month letter + 1-2 digit year if present.
    for code in QUARTERLY_MONTH_CODES.values():
        for ylen in (2, 1):
            suffix_len = 1 + ylen
            if len(s) > suffix_len and s[-suffix_len] == code and s[-ylen:].isdigit():
                return s[:-suffix_len]
    return s


def front_month(as_of: date, roll_days_before_expiry: int = 8) -> tuple[str, int, int]:
    """Return the active quarterly front month as of a date.

    Index futures roll a little over a week before the third-Friday expiry.
    This returns ``(month_code, expiry_month, expiry_year)`` so a continuous
    series can be stitched without look-ahead.
    """
    year = as_of.year
    for month in QUARTERLY_MONTHS:
        exp = _third_friday(year, month)
        roll = _subtract_business_days(exp, roll_days_before_expiry)
        if as_of <= roll:
            return QUARTERLY_MONTH_CODES[month], month, year
    # Past December roll -> next year's March contract.
    return QUARTERLY_MONTH_CODES[3], 3, year + 1


def contract_code(symbol: str, as_of: date, roll_days_before_expiry: int = 8) -> str:
    """Full broker contract code for the front month, e.g. 'NQH6'."""
    root = _strip_contract_code(symbol)
    code, _, year = front_month(as_of, roll_days_before_expiry)
    return f"{root}{code}{year % 10}"


def _third_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    # weekday(): Monday=0 ... Friday=4
    offset = (4 - d.weekday()) % 7
    first_friday = 1 + offset
    return date(year, month, first_friday + 14)


def _subtract_business_days(d: date, n: int) -> date:
    from datetime import timedelta
    result = d
    remaining = n
    while remaining > 0:
        result -= timedelta(days=1)
        if result.weekday() < 5:
            remaining -= 1
    return result


def margin_for_contracts(spec: InstrumentSpec, contracts: int, overnight: bool = False) -> float:
    """Total margin required to hold ``contracts`` contracts."""
    per = spec.overnight_margin if overnight else spec.day_margin
    return per * max(0, contracts)


def max_contracts_for_margin(
    spec: InstrumentSpec, available_capital: float, overnight: bool = False
) -> int:
    """How many contracts the available capital can support at current margin."""
    per = spec.overnight_margin if overnight else spec.day_margin
    if per <= 0:
        return 0
    return int(math.floor(available_capital / per))
