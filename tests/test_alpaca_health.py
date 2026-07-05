import pytest

from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading import alpaca_health
from paper_trading.alpaca_health import (
    AlpacaPaperHealthResult,
    check_alpaca_paper_connection,
    create_alpaca_paper_client,
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
        trading_blocked=False,
        account_blocked=False,
    ):
        self.status = status
        self.trading_blocked = trading_blocked
        self.account_blocked = account_blocked


class FakeClient:
    def __init__(self, account=None):
        self.account = account or FakeAccount()
        self.get_account_called = False

    def get_account(self):
        self.get_account_called = True
        return self.account


def test_create_client_uses_mock_factory_only():
    captured = {}

    def fake_factory(**kwargs):
        captured.update(kwargs)
        return FakeClient()

    client = create_alpaca_paper_client(valid_config(), client_factory=fake_factory)

    assert isinstance(client, FakeClient)
    assert captured["key_id"] == "paper_key"
    assert captured["secret_key"] == "paper_secret"
    assert captured["base_url"] == "https://paper-api.alpaca.markets"


def test_connection_health_active_account_passes():
    def fake_factory(**kwargs):
        return FakeClient(FakeAccount(status="ACTIVE"))

    result = check_alpaca_paper_connection(
        valid_config(),
        client_factory=fake_factory,
    )

    assert result.ok is True
    assert result.account_status == "ACTIVE"
    assert result.trading_blocked is False
    assert result.account_blocked is False


def test_connection_health_inactive_account_fails():
    def fake_factory(**kwargs):
        return FakeClient(FakeAccount(status="INACTIVE"))

    result = check_alpaca_paper_connection(
        valid_config(),
        client_factory=fake_factory,
    )

    assert result.ok is False
    assert result.account_status == "INACTIVE"


def test_connection_health_trading_blocked_fails():
    def fake_factory(**kwargs):
        return FakeClient(FakeAccount(status="ACTIVE", trading_blocked=True))

    result = check_alpaca_paper_connection(
        valid_config(),
        client_factory=fake_factory,
    )

    assert result.ok is False
    assert result.trading_blocked is True


def test_connection_health_account_blocked_fails():
    def fake_factory(**kwargs):
        return FakeClient(FakeAccount(status="ACTIVE", account_blocked=True))

    result = check_alpaca_paper_connection(
        valid_config(),
        client_factory=fake_factory,
    )

    assert result.ok is False
    assert result.account_blocked is True


def test_live_config_is_rejected_before_client_creation():
    called = False

    def fake_factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient()

    with pytest.raises(AlpacaConfigError):
        create_alpaca_paper_client(
            valid_config(base_url="https://api.alpaca.markets"),
            client_factory=fake_factory,
        )

    assert called is False


def test_confirm_live_true_is_rejected_before_client_creation():
    called = False

    def fake_factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient()

    with pytest.raises(AlpacaConfigError):
        create_alpaca_paper_client(
            valid_config(confirm_live=True),
            client_factory=fake_factory,
        )

    assert called is False


def test_health_result_repr_does_not_expose_keys():
    result = AlpacaPaperHealthResult(
        ok=True,
        message="ok",
        account_status="ACTIVE",
        trading_blocked=False,
        account_blocked=False,
    )

    rendered = repr(result)

    assert "paper_key" not in rendered
    assert "paper_secret" not in rendered


def test_no_order_submission_function_exists():
    forbidden_names = {
        "submit_order",
        "place_order",
        "create_order",
        "send_order",
        "buy",
        "sell",
        "liquidate",
    }

    module_names = set(dir(alpaca_health))

    assert forbidden_names.isdisjoint(module_names)
