import pytest

from paper_trading import alpaca_config
from paper_trading.alpaca_config import (
    AlpacaConfigError,
    AlpacaPaperConfig,
    is_live_endpoint,
    is_paper_endpoint,
    load_alpaca_paper_config,
    validate_alpaca_paper_config,
)


def valid_env(**overrides):
    env = {
        "ALPACA_API_KEY": "paper_key",
        "ALPACA_SECRET_KEY": "paper_secret",
        "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        "ALPACA_PAPER_ONLY": "true",
        "ALPACA_CONFIRM_LIVE": "false",
    }
    env.update(overrides)
    return env


def test_valid_paper_config_passes():
    config = load_alpaca_paper_config(valid_env())

    assert config.base_url == "https://paper-api.alpaca.markets"
    assert config.paper_only is True
    assert config.confirm_live is False


def test_missing_api_key_fails():
    env = valid_env()
    env.pop("ALPACA_API_KEY")

    with pytest.raises(AlpacaConfigError):
        load_alpaca_paper_config(env)


def test_missing_secret_key_fails():
    env = valid_env()
    env.pop("ALPACA_SECRET_KEY")

    with pytest.raises(AlpacaConfigError):
        load_alpaca_paper_config(env)


def test_missing_base_url_fails():
    env = valid_env()
    env.pop("ALPACA_BASE_URL")

    with pytest.raises(AlpacaConfigError):
        load_alpaca_paper_config(env)


def test_live_endpoint_fails():
    env = valid_env(ALPACA_BASE_URL="https://api.alpaca.markets")

    with pytest.raises(AlpacaConfigError, match="Live Alpaca endpoint"):
        load_alpaca_paper_config(env)


def test_non_paper_endpoint_fails():
    env = valid_env(ALPACA_BASE_URL="https://example.com")

    with pytest.raises(AlpacaConfigError, match="paper endpoint"):
        load_alpaca_paper_config(env)


def test_paper_only_false_fails():
    env = valid_env(ALPACA_PAPER_ONLY="false")

    with pytest.raises(AlpacaConfigError, match="ALPACA_PAPER_ONLY"):
        load_alpaca_paper_config(env)


def test_confirm_live_true_fails():
    env = valid_env(ALPACA_CONFIRM_LIVE="true")

    with pytest.raises(AlpacaConfigError, match="ALPACA_CONFIRM_LIVE"):
        load_alpaca_paper_config(env)


def test_bool_values_must_be_explicit_true_or_false():
    env = valid_env(ALPACA_PAPER_ONLY="yes")

    with pytest.raises(AlpacaConfigError, match="true.*false"):
        load_alpaca_paper_config(env)


def test_paper_endpoint_detection():
    assert is_paper_endpoint("https://paper-api.alpaca.markets")
    assert is_paper_endpoint("https://paper-api.alpaca.markets/")
    assert not is_paper_endpoint("https://api.alpaca.markets")


def test_live_endpoint_detection():
    assert is_live_endpoint("https://api.alpaca.markets")
    assert not is_live_endpoint("https://paper-api.alpaca.markets")


def test_config_repr_does_not_expose_keys():
    config = AlpacaPaperConfig(
        api_key="super_secret_key",
        secret_key="super_secret_value",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )

    rendered = repr(config)

    assert "super_secret_key" not in rendered
    assert "super_secret_value" not in rendered


def test_redacted_summary_does_not_expose_keys():
    config = load_alpaca_paper_config(valid_env())

    summary = config.redacted_summary()

    assert summary["api_key_present"] is True
    assert summary["secret_key_present"] is True
    assert "paper_key" not in str(summary)
    assert "paper_secret" not in str(summary)


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

    module_names = set(dir(alpaca_config))

    assert forbidden_names.isdisjoint(module_names)


def test_validate_config_rejects_constructed_unsafe_config():
    config = AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )

    with pytest.raises(AlpacaConfigError):
        validate_alpaca_paper_config(config)
