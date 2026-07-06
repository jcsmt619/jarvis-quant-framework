from pathlib import Path
from types import SimpleNamespace

import pytest

from paper_trading.alpaca_account_state import (
    build_alpaca_paper_symbol_state,
    write_alpaca_paper_symbol_state,
)
from paper_trading.alpaca_config import AlpacaPaperConfig


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


class FakePaperClient:
    def __init__(self, *, positions=None, orders=None):
        self.positions = positions or []
        self.orders = orders or []
        self.order_submit_called = False

    def get_account(self):
        return SimpleNamespace(
            status="ACTIVE",
            cash="100000",
            buying_power="400000",
            portfolio_value="100000",
        )

    def get_all_positions(self):
        return self.positions

    def get_orders(self):
        return self.orders

    def submit_order(self, *args, **kwargs):
        self.order_submit_called = True
        raise AssertionError("submit_order must not be called")


def test_symbol_state_reads_position_and_open_orders_without_submitting():
    client = FakePaperClient(
        positions=[
            SimpleNamespace(symbol="EEM", qty="12"),
            SimpleNamespace(symbol="SPY", qty="5"),
        ],
        orders=[
            SimpleNamespace(symbol="EEM", status="new", id="order_1"),
            SimpleNamespace(symbol="EEM", status="accepted", id="order_2"),
            SimpleNamespace(symbol="EEM", status="filled", id="filled_ignored"),
            SimpleNamespace(symbol="SPY", status="new", id="spy_ignored"),
        ],
    )

    state = build_alpaca_paper_symbol_state(
        config=valid_config(),
        symbol="eem",
        paper_client_factory=lambda: client,
    )

    assert state.symbol == "EEM"
    assert state.account_status == "ACTIVE"
    assert state.cash == "100000"
    assert state.buying_power == "400000"
    assert state.portfolio_value == "100000"
    assert state.position_quantity == 12.0
    assert state.position_open is True
    assert state.open_symbol_orders_count == 2
    assert state.open_symbol_order_ids == ["order_1", "order_2"]
    assert state.read_only is True
    assert state.order_submission_enabled is False
    assert state.broker_order_call_performed is False
    assert state.live_trading_enabled is False
    assert client.order_submit_called is False


def test_symbol_state_handles_no_position_and_no_orders():
    client = FakePaperClient()

    state = build_alpaca_paper_symbol_state(
        config=valid_config(),
        symbol="EEM",
        paper_client_factory=lambda: client,
    )

    assert state.position_quantity == 0.0
    assert state.position_open is False
    assert state.open_symbol_orders_count == 0
    assert state.open_symbol_order_ids == []


def test_symbol_state_rejects_empty_symbol():
    with pytest.raises(ValueError, match="symbol is required"):
        build_alpaca_paper_symbol_state(
            config=valid_config(),
            symbol="",
            paper_client_factory=lambda: FakePaperClient(),
        )


def test_symbol_state_rejects_missing_client_factory():
    with pytest.raises(ValueError, match="paper_client_factory is required"):
        build_alpaca_paper_symbol_state(
            config=valid_config(),
            symbol="EEM",
            paper_client_factory=None,
        )


def test_symbol_state_rejects_live_config():
    live_config = AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )

    with pytest.raises(Exception):
        build_alpaca_paper_symbol_state(
            config=live_config,
            symbol="EEM",
            paper_client_factory=lambda: FakePaperClient(),
        )


def test_write_symbol_state_json_excludes_secrets(tmp_path):
    client = FakePaperClient(
        positions=[SimpleNamespace(symbol="EEM", qty="3")],
        orders=[SimpleNamespace(symbol="EEM", status="new", id="order_123")],
    )

    state = build_alpaca_paper_symbol_state(
        config=valid_config(),
        symbol="EEM",
        paper_client_factory=lambda: client,
    )

    path = write_alpaca_paper_symbol_state(state, output_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert '"symbol": "EEM"' in text
    assert '"read_only": true' in text
    assert '"order_submission_enabled": false' in text
    assert '"broker_order_call_performed": false' in text
    assert '"live_trading_enabled": false' in text
    assert "paper_key" not in text
    assert "paper_secret" not in text
