import json

import pytest

from paper_trading import alpaca_snapshot
from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading.alpaca_snapshot import (
    collect_alpaca_paper_account_snapshot,
    write_alpaca_paper_account_snapshot,
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
    status = "ACTIVE"
    cash = "100000"
    buying_power = "400000"
    portfolio_value = "100000"
    equity = "100000"
    trading_blocked = False
    account_blocked = False


class FakeClient:
    def __init__(self):
        self.get_account_called = False
        self.list_positions_called = False
        self.list_orders_called_with = None

    def get_account(self):
        self.get_account_called = True
        return FakeAccount()

    def list_positions(self):
        self.list_positions_called = True
        return []

    def list_orders(self, status=None):
        self.list_orders_called_with = status
        return []


def test_collect_snapshot_uses_read_only_calls():
    captured_client = FakeClient()

    def fake_factory(**kwargs):
        return captured_client

    snapshot = collect_alpaca_paper_account_snapshot(
        valid_config(),
        client_factory=fake_factory,
    )

    assert captured_client.get_account_called is True
    assert captured_client.list_positions_called is True
    assert captured_client.list_orders_called_with == "open"
    assert snapshot.account_status == "ACTIVE"
    assert snapshot.cash == "100000"
    assert snapshot.buying_power == "400000"
    assert snapshot.portfolio_value == "100000"
    assert snapshot.positions_count == 0
    assert snapshot.open_orders_count == 0
    assert snapshot.order_submission_enabled is False
    assert snapshot.live_trading_enabled is False


def test_collect_snapshot_rejects_live_endpoint_before_client_creation():
    called = False

    def fake_factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient()

    with pytest.raises(AlpacaConfigError):
        collect_alpaca_paper_account_snapshot(
            valid_config(base_url="https://api.alpaca.markets"),
            client_factory=fake_factory,
        )

    assert called is False


def test_collect_snapshot_rejects_confirm_live_true_before_client_creation():
    called = False

    def fake_factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient()

    with pytest.raises(AlpacaConfigError):
        collect_alpaca_paper_account_snapshot(
            valid_config(confirm_live=True),
            client_factory=fake_factory,
        )

    assert called is False


def test_write_snapshot_creates_json_file(tmp_path):
    def fake_factory(**kwargs):
        return FakeClient()

    snapshot = collect_alpaca_paper_account_snapshot(
        valid_config(),
        client_factory=fake_factory,
    )

    path = write_alpaca_paper_account_snapshot(snapshot, output_dir=tmp_path)

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["account_status"] == "ACTIVE"
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

    module_names = set(dir(alpaca_snapshot))

    assert forbidden_names.isdisjoint(module_names)
