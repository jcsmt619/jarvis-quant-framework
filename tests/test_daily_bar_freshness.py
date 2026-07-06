from datetime import UTC, datetime, timedelta

from paper_trading.risk_gates import check_stale_data, evaluate_all_gates


def test_closed_market_allows_daily_bar_grace_buffer():
    now = datetime(2026, 7, 6, 6, 0, tzinfo=UTC)
    latest_bar = now - timedelta(days=4.3)

    passed, reason = check_stale_data(
        latest_bar,
        now=now,
        is_market_open=False,
    )

    assert passed is True
    assert "closed-market daily-bar threshold" in reason


def test_open_market_rejects_same_stale_daily_bar():
    now = datetime(2026, 7, 6, 14, 0, tzinfo=UTC)
    latest_bar = now - timedelta(days=4.3)

    passed, reason = check_stale_data(
        latest_bar,
        now=now,
        is_market_open=True,
    )

    assert passed is False
    assert "exceeds staleness threshold" in reason


def test_closed_market_stale_data_can_pass_while_market_hours_blocks():
    now = datetime(2026, 7, 6, 6, 0, tzinfo=UTC)
    latest_bar = now - timedelta(days=4.3)

    status = evaluate_all_gates(
        target_notional=0.0,
        latest_bar_timestamp=latest_bar,
        bar_count=120,
        is_market_open=False,
        kill_switch_engaged=False,
        now=now,
    )

    assert status.checks["stale_data"][0] is True
    assert status.checks["market_hours"][0] is False
    assert status.passed is False


def test_open_market_stale_data_blocks():
    now = datetime(2026, 7, 6, 14, 0, tzinfo=UTC)
    latest_bar = now - timedelta(days=4.3)

    status = evaluate_all_gates(
        target_notional=0.0,
        latest_bar_timestamp=latest_bar,
        bar_count=120,
        is_market_open=True,
        kill_switch_engaged=False,
        now=now,
    )

    assert status.checks["stale_data"][0] is False
    assert status.passed is False
