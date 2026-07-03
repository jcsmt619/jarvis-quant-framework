"""The simulator is what the backtest and the paper loop both execute against,
so its P&L has to be exactly right: a closed trade, a bracket stop, and a bracket
target each produce the dollar result the instrument math says they should.
"""

import pandas as pd
import pytest

from brokers.sim_broker import SimBroker
from brokers.base import OrderRequest, OrderSide, OrderType
from core.instruments import get_instrument


def _broker():
    b = SimBroker({"initial_equity": 50000, "slippage_ticks": 0, "commission_per_contract": 0},
                  instruments={"MNQ": get_instrument("MNQ")})
    b.connect()
    return b


def _bar(o, h, l, c, ts="2024-01-02 10:00"):
    s = pd.Series({"open": o, "high": h, "low": l, "close": c})
    s.name = pd.Timestamp(ts)
    return s


def test_long_then_close_realizes_pnl():
    b = _broker()
    b.set_price("MNQ", 18000)
    b.place_order(OrderRequest("MNQ", OrderSide.BUY, 2, OrderType.MARKET))
    b.set_price("MNQ", 18010)  # +10 points
    b.close_position("MNQ")
    acct = b.get_account()
    # 10 points * $2/pt * 2 contracts = $40 (MNQ is $0.50/tick, $2/point)
    assert acct.realized_pnl == pytest.approx(40.0)
    assert acct.equity == pytest.approx(50040.0)


def test_bracket_stop_exit():
    b = _broker()
    b.set_price("MNQ", 18000)
    b.place_order(OrderRequest("MNQ", OrderSide.BUY, 1, OrderType.MARKET,
                               stop_loss=17990, take_profit=18020))
    # Bar trades down through the stop.
    trade = b.on_bar("MNQ", _bar(18000, 18005, 17988, 17992))
    assert trade is not None and trade["reason"] == "stop"
    # -10 points = -40 ticks * $0.50 = -$20
    assert trade["pnl"] == pytest.approx(-20.0)


def test_bracket_target_exit():
    b = _broker()
    b.set_price("MNQ", 18000)
    b.place_order(OrderRequest("MNQ", OrderSide.SELL, 1, OrderType.MARKET,
                               stop_loss=18010, take_profit=17985))
    trade = b.on_bar("MNQ", _bar(18000, 18002, 17980, 17988))
    assert trade is not None and trade["reason"] == "target"
    # short from 18000 to 17985 = +15 points = +60 ticks * $0.50 = $30
    assert trade["pnl"] == pytest.approx(30.0)


def test_position_appears_then_clears():
    b = _broker()
    b.set_price("MNQ", 18000)
    b.place_order(OrderRequest("MNQ", OrderSide.BUY, 3, OrderType.MARKET))
    assert b.get_positions()[0].quantity == 3
    b.close_position("MNQ")
    assert b.get_positions() == []


def test_unrealized_pnl_marks_to_last_price():
    b = _broker()
    b.set_price("MNQ", 18000)
    b.place_order(OrderRequest("MNQ", OrderSide.BUY, 1, OrderType.MARKET))
    b.on_bar("MNQ", _bar(18000, 18012, 17998, 18008))
    pos = b.get_positions()[0]
    # +8 points = 32 ticks * $0.50 = $16
    assert pos.unrealized_pnl == pytest.approx(16.0)
