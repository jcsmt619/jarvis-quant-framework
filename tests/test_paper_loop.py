"""
tests/test_paper_loop.py
========================
The composition layer's invariants (offline, fake venue): pair atomicity
(a rejected second leg unwinds the first), risk-manager gating before any
order, disarmed/kill-switch/closed-market cycles send nothing, band-snap
exits, and an unhandled cycle exception disarms the loop itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from broker.base import Account, BaseBroker, Order, Position
from core.risk_manager import RiskDecision, RiskLimits, RiskManager
from paper_loop import PaperTradingLoop, Z_ENTRY
from utils.state_gatekeeper import StateGatekeeper


# ---------------------------------------------------------------------------
class LoopVenue(BaseBroker):
    """Scriptable venue: which symbols reject, what bars to serve."""

    def __init__(self, reject: set[str] | None = None, market_open=True,
                 bars: dict | None = None):
        self.reject = reject or set()
        self.market_open = market_open
        self.bars = bars or {}
        self.orders: list[tuple] = []
        self._book: dict[str, float] = {}

    def get_account(self) -> Account:
        return Account(100_000.0, 100_000.0, 200_000.0, "ACTIVE")

    def get_positions(self) -> list[Position]:
        return [Position(s, q, 100.0) for s, q in self._book.items() if q]

    def submit_order(self, symbol, qty, side, order_type="market",
                     limit_price=None) -> Order:
        self.orders.append((symbol, qty, side))
        if symbol in self.reject:
            return Order("", symbol, side, qty, order_type, "rejected",
                         reason="not shortable")
        signed = qty if side == "buy" else -qty
        self._book[symbol] = self._book.get(symbol, 0.0) + signed
        return Order("ok", symbol, side, qty, order_type, "filled",
                     filled_qty=qty)

    def cancel_order(self, order_id): ...
    def close_position(self, symbol): ...
    def close_all_positions(self): ...
    def is_market_open(self) -> bool: return self.market_open
    def get_bars(self, symbols, timeframe="1Min", limit=100) -> dict:
        return {s: self.bars[s] for s in symbols if s in self.bars}


def _approve_all(*_a, **_k) -> RiskDecision:
    return RiskDecision(approved=True)


def _mk_loop(tmp_path, venue, approve=True) -> PaperTradingLoop:
    loop = PaperTradingLoop.__new__(PaperTradingLoop)
    loop.running = True
    loop.gate = StateGatekeeper(tmp_path / "state.json")
    loop.broker = venue
    loop.risk = RiskManager(RiskLimits(), initial_capital=100_000.0,
                            lock_file=tmp_path / "halt.lock")
    if approve:
        loop.risk.validate_signal = _approve_all
    from monitoring.alerts import AlertManager
    loop.alerts = AlertManager(rate_limit_minutes=0)
    return loop


def _bars(closes) -> pd.DataFrame:
    idx = pd.date_range("2026-07-02 14:30", periods=len(closes), freq="1min")
    return pd.DataFrame({"close": closes}, index=idx)


# ---------------------------------------------------------------------------
def test_pair_atomicity_unwinds_leg_a(tmp_path):
    """THE invariant: leg B rejected -> leg A immediately unwound, book flat."""
    venue = LoopVenue(reject={"BBB"})
    loop = _mk_loop(tmp_path, venue)
    closes = np.full(35, 100.0)
    loop.enter_pair("AAA", "BBB", z=-2.5, prices=(100.0, 100.0),
                    closes_a=closes, closes_b=closes)
    sides = [(s, side) for s, _q, side in venue.orders]
    assert sides == [("AAA", "buy"), ("BBB", "sell"), ("AAA", "sell")]
    assert loop.gate.get_position("AAA") == 0        # ledger flat again
    assert loop.gate.get_position("BBB") == 0


def test_both_legs_filled_books_pair(tmp_path):
    venue = LoopVenue()
    loop = _mk_loop(tmp_path, venue)
    closes = np.full(35, 100.0)
    loop.enter_pair("AAA", "BBB", z=2.5, prices=(100.0, 100.0),
                    closes_a=closes, closes_b=closes)   # z high -> short A
    assert loop.gate.get_position("AAA") < 0
    assert loop.gate.get_position("BBB") > 0


def test_risk_rejection_sends_nothing(tmp_path):
    venue = LoopVenue()
    loop = _mk_loop(tmp_path, venue, approve=False)
    loop.risk.validate_signal = lambda *_a, **_k: RiskDecision(
        approved=False, rejection_reason="max exposure")
    closes = np.full(35, 100.0)
    loop.enter_pair("AAA", "BBB", z=2.5, prices=(100.0, 100.0),
                    closes_a=closes, closes_b=closes)
    assert venue.orders == []                        # nothing reached the venue


def test_cycle_gates(tmp_path):
    """Closed market, disarmed gatekeeper, kill-switch lock: no orders."""
    closes = list(100 + np.zeros(40))
    closes[-1] = 130                                  # huge z if it ever ran
    bars = {a: _bars(closes) for pair in [("GOOGL", "GOOG")] for a in pair}

    venue = LoopVenue(market_open=False, bars=bars)
    loop = _mk_loop(tmp_path, venue)
    loop.cycle()
    assert venue.orders == []                         # market closed

    venue.market_open = True
    loop.gate._disarm("test")
    loop.cycle()
    assert venue.orders == []                         # disarmed

    loop2 = _mk_loop(tmp_path, LoopVenue(market_open=True, bars=bars))
    (tmp_path / "halt.lock").write_text("halt", encoding="utf-8")
    loop2.cycle()
    assert loop2.broker.orders == []                  # kill switch


def test_band_snap_exit_closes_both_legs(tmp_path):
    venue = LoopVenue()
    loop = _mk_loop(tmp_path, venue)
    loop.gate.update_position("AAA", 10, 100.0, "BUY")
    loop.gate.update_position("BBB", 10, 100.0, "SELL")
    loop.exit_pair("AAA", "BBB", z=4.1, why="band snap")
    assert loop.gate.get_position("AAA") == 0
    assert loop.gate.get_position("BBB") == 0


def test_unhandled_exception_disarms_and_stops(tmp_path):
    venue = LoopVenue(market_open=True)
    loop = _mk_loop(tmp_path, venue)
    loop.startup_reconciliation = lambda: None
    loop.cycle = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    loop.run()                                        # must return, not raise
    assert loop.gate.armed is False
    assert "unhandled exception" in loop.gate.state["strategy"]["halt_reason"]


def test_real_risk_manager_approves_vanilla_leg(tmp_path):
    """Sanity: the REAL risk manager can approve a plain equity leg --
    otherwise the loop could never trade at all."""
    venue = LoopVenue()
    loop = _mk_loop(tmp_path, venue, approve=False)   # real validate_signal
    closes = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.05, 40))
    sig = loop._leg_signal("AAA", 1, float(closes[-1]), closes)
    dec = loop.risk.validate_signal(sig, loop._portfolio_state())
    assert dec.approved, f"vanilla leg rejected: {dec.rejection_reason}"
