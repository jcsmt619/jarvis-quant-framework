"""Instrument math is the foundation everything sizes against, so it gets
checked directly: tick-to-dollar conversion, signed P&L, and front-month roll.
"""

from datetime import date

import pytest

from core.instruments import (get_instrument, front_month, contract_code,
                              max_contracts_for_margin, QUARTERLY_MONTH_CODES)


def test_nq_point_and_tick_value():
    nq = get_instrument("NQ")
    assert nq.tick_size == 0.25
    assert nq.tick_value == 5.0
    assert nq.point_value == 20.0  # 5.0 / 0.25


def test_mnq_is_one_tenth_of_nq():
    nq, mnq = get_instrument("NQ"), get_instrument("MNQ")
    assert mnq.tick_value == pytest.approx(nq.tick_value / 10)
    assert mnq.is_micro


def test_long_pnl_positive_when_price_rises():
    nq = get_instrument("NQ")
    # +10 points = 40 ticks * $5 * 2 contracts = $400
    assert nq.pnl(18000, 18010, contracts=2, direction="long") == pytest.approx(400.0)


def test_short_pnl_positive_when_price_falls():
    nq = get_instrument("NQ")
    assert nq.pnl(18000, 17990, contracts=1, direction="short") == pytest.approx(200.0)


def test_stop_distance_ticks():
    mnq = get_instrument("MNQ")
    assert mnq.stop_distance_ticks(18000, 17996) == pytest.approx(16.0)  # 4 points / 0.25


def test_round_to_tick():
    mnq = get_instrument("MNQ")
    assert mnq.round_to_tick(18000.13) == pytest.approx(18000.25)


def test_front_month_returns_quarterly_code():
    code, month, year = front_month(date(2026, 1, 15))
    assert code in QUARTERLY_MONTH_CODES.values()
    assert month in (3, 6, 9, 12)


def test_contract_code_format():
    code = contract_code("NQ", date(2026, 1, 15))
    assert code.startswith("NQ")
    assert code[-1].isdigit()


def test_max_contracts_for_margin():
    mnq = get_instrument("MNQ")  # day_margin 180
    assert max_contracts_for_margin(mnq, 1000) == 5  # floor(1000/180)


def test_unknown_symbol_raises():
    with pytest.raises(KeyError):
        get_instrument("ZZZZ")
