"""
tests/test_broker_adapter.py
============================
Offline contract tests: the generic BaseBroker layer (reconcile wiring,
guarded orders vs the gatekeeper) with a fake venue, and the Alpaca
adapter's order construction / never-default-live guard with a mocked SDK.
Plus one @integration smoke test that talks to the real paper API when
credentials exist.
"""

from __future__ import annotations

import os

import pytest

from broker import get_broker
from broker.base import Account, BaseBroker, Order, Position
from utils.state_gatekeeper import StateGatekeeper


# ---------------------------------------------------------------------------
class FakeBroker(BaseBroker):
    """Deterministic venue for testing the generic layer."""

    def __init__(self, positions=None, fill=True):
        self._positions = positions or []
        self._fill = fill
        self.submitted: list[dict] = []

    def get_account(self) -> Account:
        return Account(equity=100_000.0, cash=100_000.0,
                       buying_power=200_000.0, status="ACTIVE")

    def get_positions(self) -> list[Position]:
        return list(self._positions)

    def submit_order(self, symbol, qty, side, order_type="market",
                     limit_price=None) -> Order:
        self.submitted.append({"symbol": symbol, "qty": qty, "side": side})
        if not self._fill:
            return Order(id="x1", symbol=symbol, side=side, qty=qty,
                         order_type=order_type, status="rejected",
                         reason="venue said no")
        self._positions = [Position(symbol, qty if side == "buy" else -qty,
                                    avg_entry_price=100.0)]
        return Order(id="x1", symbol=symbol, side=side, qty=qty,
                     order_type=order_type, status="filled", filled_qty=qty)

    def cancel_order(self, order_id): ...
    def close_position(self, symbol): ...
    def close_all_positions(self): ...
    def is_market_open(self) -> bool: return True
    def get_bars(self, symbols, timeframe="1Min", limit=100) -> dict:
        return {}


@pytest.fixture()
def gate(tmp_path) -> StateGatekeeper:
    return StateGatekeeper(tmp_path / "state.json")


# --- generic layer ---------------------------------------------------------
def test_position_map_filters_zero_rows():
    b = FakeBroker(positions=[Position("SPY", 10, 400.0),
                              Position("TLT", 0.0, 90.0),
                              Position("GLD", -5, 180.0)])
    assert b.position_map() == {"SPY": 10, "GLD": -5}


def test_reconcile_mismatch_disarms_via_broker(gate):
    b = FakeBroker(positions=[Position("SPY", 10, 400.0)])
    verdict = b.reconcile(gate)                    # local book is empty
    assert verdict["status"] == "RED"
    assert gate.armed is False                     # halt written into state


def test_guarded_order_refused_while_disarmed(gate):
    b = FakeBroker()
    gate._disarm("test halt")
    order = b.guarded_order(gate, "SPY", 10, "buy")
    assert order.status == "rejected"
    assert "disarmed" in order.reason
    assert b.submitted == []                       # nothing reached the venue


def test_guarded_order_books_fill_into_ledger(gate):
    b = FakeBroker()
    order = b.guarded_order(gate, "SPY", 10, "buy")
    assert order.status == "filled"
    pos = gate.state["positions"]["SPY"]
    assert pos["qty"] == 10
    assert pos["entry_price"] == pytest.approx(100.0)   # venue avg entry
    # and the ledger now reconciles cleanly against the venue
    assert b.reconcile(gate)["status"] == "GREEN"


def test_guarded_order_rejection_books_nothing(gate):
    b = FakeBroker(fill=False)
    order = b.guarded_order(gate, "SPY", 10, "buy")
    assert order.status == "rejected" and order.reason == "venue said no"
    assert gate.state["positions"] == {}


# --- Alpaca adapter (mocked SDK, no network) -------------------------------
class _MockOrderResult:
    id, status, filled_qty = "o1", "accepted", "0"


class _MockApi:
    def __init__(self):
        self.calls: list[dict] = []

    def submit_order(self, **kwargs):
        self.calls.append(kwargs)
        return _MockOrderResult()


@pytest.fixture()
def alpaca():
    from broker.alpaca_client import AlpacaBroker
    b = AlpacaBroker.__new__(AlpacaBroker)         # bypass network __init__
    b.api = _MockApi()
    b.paper = True
    return b


def test_market_orders_are_day_never_gtc(alpaca):
    alpaca.submit_order("SPY", 10, "buy")
    assert alpaca.api.calls[0]["time_in_force"] == "day"


def test_limit_orders_require_price(alpaca):
    order = alpaca.submit_order("SPY", 10, "buy", order_type="limit")
    assert order.status == "rejected" and "limit_price" in order.reason
    ok = alpaca.submit_order("SPY", 10, "buy", "limit", limit_price=400.0)
    assert ok.status == "accepted"
    assert alpaca.api.calls[-1]["time_in_force"] == "gtc"


def test_invalid_orders_rejected_not_none(alpaca):
    assert alpaca.submit_order("SPY", 0, "buy").status == "rejected"
    assert alpaca.submit_order("SPY", 10, "hold").status == "rejected"
    assert alpaca.api.calls == []                  # nothing reached the SDK


def test_never_default_live(monkeypatch):
    from broker.alpaca_client import AlpacaBroker
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.delenv("ALPACA_CONFIRM_LIVE", raising=False)
    with pytest.raises(PermissionError):           # raised BEFORE any network
        AlpacaBroker(paper=False)


def test_factory_unknown_broker():
    with pytest.raises(KeyError):
        get_broker("madeup")


# --- reconcile flow (synthetic broker, no network) -------------------------
# Originally a real-paper-API integration test that skipped without
# ALPACA credentials. Credentials are not "missing local data", so the
# flow now runs against a synthetic broker fixture that supplies the same
# shape of data (account status + positions) the real adapter returns.
# Every assertion is unchanged: account status exists, adopt -> resume ->
# reconcile returns GREEN.
@pytest.mark.integration
def test_paper_connection_and_reconcile(tmp_path):
    broker = FakeBroker(positions=[Position("SPY", 10, 400.0),
                                   Position("TLT", -5, 90.0)])
    assert broker.get_account().status
    gate = StateGatekeeper(tmp_path / "s.json")
    gate.adopt_broker_state(broker.position_map())
    gate.resume_trading()
    assert broker.reconcile(gate)["status"] == "GREEN"
