from datetime import UTC, datetime

from paper_trading.market_session import get_us_equity_market_session_status


def test_weekday_regular_hours_is_open():
    status = get_us_equity_market_session_status(
        datetime(2026, 7, 6, 14, 0, tzinfo=UTC)
    )

    assert status.is_weekday is True
    assert status.is_regular_hours is True
    assert status.is_market_open is True
    assert "regular cash-session" in status.reason


def test_weekday_before_open_is_closed():
    status = get_us_equity_market_session_status(
        datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    )

    assert status.is_weekday is True
    assert status.is_regular_hours is False
    assert status.is_market_open is False
    assert "outside regular" in status.reason


def test_weekend_is_closed():
    status = get_us_equity_market_session_status(
        datetime(2026, 7, 5, 18, 0, tzinfo=UTC)
    )

    assert status.is_weekday is False
    assert status.is_market_open is False
    assert "not a weekday" in status.reason


def test_naive_datetime_is_treated_as_utc():
    status = get_us_equity_market_session_status(
        datetime(2026, 7, 6, 14, 0)
    )

    assert status.is_market_open is True
