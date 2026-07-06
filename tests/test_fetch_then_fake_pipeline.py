from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.alpaca_market_data import AlpacaMarketDataResult
from scripts import run_fetch_then_fake_pipeline as script


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def make_market_data_result(csv_path="reports/paper_trading/eem.csv"):
    return AlpacaMarketDataResult(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        timeframe="1Day",
        bars_count=120,
        latest_timestamp_utc="2026-07-02T04:00:00+00:00",
        latest_close=65.71,
        csv_path=csv_path,
        read_only=True,
        order_submission_enabled=False,
        live_trading_enabled=False,
        broker_order_call_performed=False,
    )


def test_fetch_then_fake_pipeline_success(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    bars = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"]),
            "Close": [66.0, 65.71],
        }
    )

    captured = {}

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(script, "fetch_alpaca_daily_bars", lambda **kwargs: bars)
    monkeypatch.setattr(
        script,
        "write_market_data_csv",
        lambda **kwargs: (csv_path, make_market_data_result(str(csv_path))),
    )

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        print("FAKE PAPER EXECUTION PIPELINE: PASS")
        print("Pipeline decision: WAIT_MARKET_CLOSED")
        print("REAL BROKER CLIENT USED: false")
        print("REAL PAPER ORDER SUBMITTED: false")
        return 0

    monkeypatch.setattr(script, "run_fake_execution_pipeline", fake_pipeline)

    code = script.run_fetch_then_fake_pipeline(
        env_file=Path(".env"),
        symbol="EEM",
        limit=120,
        feed="iex",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "READ-ONLY MARKET DATA FETCH: PASS" in output
    assert "FAKE PAPER EXECUTION PIPELINE: PASS" in output
    assert "ONE-COMMAND SAFETY SUMMARY" in output
    assert "REAL BROKER CLIENT USED: false" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert captured["close_csv"] == csv_path
    assert captured["env_file"] is None


def test_fetch_then_fake_pipeline_fetch_failure_returns_one(capsys, monkeypatch):
    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)

    def fail_fetch(**kwargs):
        raise ValueError("No market bars returned")

    monkeypatch.setattr(script, "fetch_alpaca_daily_bars", fail_fetch)

    code = script.run_fetch_then_fake_pipeline(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "READ-ONLY FETCH + FAKE PIPELINE: FAIL" in output
    assert "No market bars returned" in output


def test_fetch_then_fake_pipeline_propagates_pipeline_block(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    bars = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"]),
            "Close": [66.0, 65.71],
        }
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(script, "fetch_alpaca_daily_bars", lambda **kwargs: bars)
    monkeypatch.setattr(
        script,
        "write_market_data_csv",
        lambda **kwargs: (csv_path, make_market_data_result(str(csv_path))),
    )
    monkeypatch.setattr(script, "run_fake_execution_pipeline", lambda **kwargs: 1)

    code = script.run_fetch_then_fake_pipeline(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "READ-ONLY MARKET DATA FETCH: PASS" in output
    assert "ONE-COMMAND SAFETY SUMMARY" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
