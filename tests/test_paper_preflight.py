import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from paper_trading import preflight
from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading.preflight import (
    build_paper_preflight_report,
    write_paper_preflight_report,
)


def valid_config(**overrides):
    values = {
        "api_key": "paper_key",
        "secret_key": "paper_secret",
        "base_url": "https://paper-api.alpaca.markets",
        "paper_only": True,
        "confirm_live": False,
    }
    values.update(overrides)
    return AlpacaPaperConfig(**values)


class FakeAccount:
    def __init__(
        self,
        status="ACTIVE",
        cash="100000",
        buying_power="400000",
        portfolio_value="100000",
        equity="100000",
        trading_blocked=False,
        account_blocked=False,
    ):
        self.status = status
        self.cash = cash
        self.buying_power = buying_power
        self.portfolio_value = portfolio_value
        self.equity = equity
        self.trading_blocked = trading_blocked
        self.account_blocked = account_blocked


class FakeClient:
    def __init__(self, account=None, positions=None, orders=None):
        self.account = account or FakeAccount()
        self.positions = [] if positions is None else positions
        self.orders = [] if orders is None else orders

    def get_account(self):
        return self.account

    def list_positions(self):
        return self.positions

    def list_orders(self, status=None):
        assert status == "open"
        return self.orders


def fake_factory(account=None, positions=None, orders=None):
    def _factory(**kwargs):
        return FakeClient(account=account, positions=positions, orders=orders)

    return _factory


def _fresh_index(length: int):
    end = datetime.now(UTC)
    start = end - timedelta(days=length - 1)
    return pd.date_range(start=start, periods=length, freq="D")


def buy_signal_prices():
    prices = [
        100,
        99,
        98,
        97,
        96,
        95,
        94,
        93,
        92,
        91,
        90,
        89,
        88,
        87,
        86,
        85,
        84,
        83,
        82,
        81,
    ]
    return pd.Series(prices, index=_fresh_index(len(prices)))


def hold_signal_prices():
    prices = [
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
        100,
        101,
    ]
    return pd.Series(prices, index=_fresh_index(len(prices)))


def test_preflight_report_ready_when_account_active_and_dry_run_passes():
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=buy_signal_prices(),
        client_factory=fake_factory(),
    )

    assert report.account_status == "ACTIVE"
    assert report.symbol == "EEM"
    assert report.strategy == "rsi_revert"
    assert report.dry_run_order_submitted is False
    assert report.order_submission_enabled is False
    assert report.live_trading_enabled is False
    assert report.blocked_reasons == []
    assert report.ready_for_paper_order_phase is True


def test_preflight_blocks_inactive_account():
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=hold_signal_prices(),
        client_factory=fake_factory(account=FakeAccount(status="INACTIVE")),
    )

    assert report.ready_for_paper_order_phase is False
    assert any("not ACTIVE" in reason for reason in report.blocked_reasons)


def test_preflight_blocks_trading_blocked_account():
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=hold_signal_prices(),
        client_factory=fake_factory(account=FakeAccount(trading_blocked=True)),
    )

    assert report.ready_for_paper_order_phase is False
    assert "paper account trading_blocked is True" in report.blocked_reasons


def test_preflight_blocks_account_blocked_account():
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=hold_signal_prices(),
        client_factory=fake_factory(account=FakeAccount(account_blocked=True)),
    )

    assert report.ready_for_paper_order_phase is False
    assert "paper account account_blocked is True" in report.blocked_reasons


def test_preflight_blocks_kill_switch():
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=buy_signal_prices(),
        kill_switch_engaged=True,
        client_factory=fake_factory(),
    )

    assert report.ready_for_paper_order_phase is False
    assert any("kill_switch" in reason or "kill switch" in reason for reason in report.blocked_reasons)


def test_preflight_rejects_live_endpoint_before_client_creation():
    called = False

    def factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient()

    with pytest.raises(AlpacaConfigError):
        build_paper_preflight_report(
            config=valid_config(base_url="https://api.alpaca.markets"),
            close_prices=hold_signal_prices(),
            client_factory=factory,
        )

    assert called is False


def test_write_preflight_report_creates_json_without_secrets(tmp_path):
    report = build_paper_preflight_report(
        config=valid_config(),
        close_prices=hold_signal_prices(),
        client_factory=fake_factory(),
    )

    path = write_paper_preflight_report(report, output_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert path.exists()
    assert data["symbol"] == "EEM"
    assert data["strategy"] == "rsi_revert"
    assert data["order_submission_enabled"] is False
    assert data["live_trading_enabled"] is False
    assert "paper_key" not in path.read_text(encoding="utf-8")
    assert "paper_secret" not in path.read_text(encoding="utf-8")


def test_no_order_submission_function_exists():
    forbidden_names = {
        "submit_order",
        "place_order",
        "create_order",
        "send_order",
        "buy",
        "sell",
        "liquidate",
        "cancel_order",
    }

    module_names = set(dir(preflight))

    assert forbidden_names.isdisjoint(module_names)
