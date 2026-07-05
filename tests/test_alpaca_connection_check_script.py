from pathlib import Path

import pytest

from paper_trading.alpaca_health import AlpacaPaperHealthResult
from scripts import check_alpaca_paper_connection as script


def test_load_env_file_does_not_overwrite_existing_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=file_key",
                "ALPACA_SECRET_KEY=file_secret",
                "ALPACA_BASE_URL=https://paper-api.alpaca.markets",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ALPACA_API_KEY", "existing_key")

    script.load_env_file(env_file)

    assert script.os.environ["ALPACA_API_KEY"] == "existing_key"
    assert script.os.environ["ALPACA_SECRET_KEY"] == "file_secret"


def test_run_check_config_failure_returns_one(tmp_path, capsys, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=paper_key",
                "ALPACA_SECRET_KEY=paper_secret",
                "ALPACA_BASE_URL=https://api.alpaca.markets",
                "ALPACA_PAPER_ONLY=true",
                "ALPACA_CONFIRM_LIVE=false",
            ]
        ),
        encoding="utf-8",
    )

    for key in [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ALPACA_BASE_URL",
        "ALPACA_PAPER_ONLY",
        "ALPACA_CONFIRM_LIVE",
    ]:
        monkeypatch.delenv(key, raising=False)

    code = script.run_check(env_file=env_file)
    output = capsys.readouterr().out

    assert code == 1
    assert "ALPACA PAPER CONFIG: FAIL" in output
    assert "Live Alpaca endpoint" in output


def test_run_check_success_uses_mocked_health_check(tmp_path, capsys, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=paper_key",
                "ALPACA_SECRET_KEY=paper_secret",
                "ALPACA_BASE_URL=https://paper-api.alpaca.markets",
                "ALPACA_PAPER_ONLY=true",
                "ALPACA_CONFIRM_LIVE=false",
            ]
        ),
        encoding="utf-8",
    )

    for key in [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ALPACA_BASE_URL",
        "ALPACA_PAPER_ONLY",
        "ALPACA_CONFIRM_LIVE",
    ]:
        monkeypatch.delenv(key, raising=False)

    def fake_health_check(config):
        return AlpacaPaperHealthResult(
            ok=True,
            message="mock ok",
            account_status="ACTIVE",
            trading_blocked=False,
            account_blocked=False,
        )

    monkeypatch.setattr(script, "check_alpaca_paper_connection", fake_health_check)

    code = script.run_check(env_file=env_file)
    output = capsys.readouterr().out

    assert code == 0
    assert "ALPACA PAPER CONFIG: PASS" in output
    assert "ALPACA PAPER HEALTH: PASS" in output
    assert "ORDER SUBMISSION: DISABLED" in output
    assert "LIVE TRADING: DISABLED" in output
    assert "paper_secret" not in output
