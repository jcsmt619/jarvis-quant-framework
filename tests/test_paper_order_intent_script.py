from pathlib import Path

import pandas as pd

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.preflight import PaperPreflightReport
from scripts import run_paper_order_intent_report as script


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def make_report(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "account_status": "ACTIVE",
        "cash": "100000",
        "buying_power": "400000",
        "portfolio_value": "100000",
        "positions_count": 0,
        "open_orders_count": 0,
        "dry_run_signal": "HOLD",
        "dry_run_reason": "RSI neutral",
        "dry_run_final_decision": "HOLD: RSI neutral",
        "dry_run_order_submitted": False,
        "risk_gate_passed": True,
        "risk_gate_checks": {},
        "ready_for_paper_order_phase": True,
        "blocked_reasons": [],
        "order_submission_enabled": False,
        "live_trading_enabled": False,
    }
    values.update(overrides)
    return PaperPreflightReport(**values)


def test_latest_price_from_close_prices():
    prices = pd.Series([10.0, 11.0, 12.5])

    assert script._latest_price_from_close_prices(prices) == 12.5


def test_run_order_intent_report_hold_success(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text(
        "Date,Close\n2026-07-01,65\n2026-07-02,66\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(
        script,
        "build_paper_preflight_report",
        lambda **kwargs: make_report(dry_run_signal="HOLD"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_preflight_report",
        lambda report: Path("reports/paper_trading/mock_preflight.json"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_order_intent",
        lambda intent: Path("reports/paper_trading/mock_intent.json"),
    )

    code = script.run_order_intent_report(
        env_file=Path(".env"),
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "PAPER ORDER INTENT: HOLD" in output
    assert "BROKER CALL PERFORMED: false" in output
    assert "ORDER SUBMISSION: DISABLED" in output
    assert "LIVE TRADING: DISABLED" in output


def test_run_order_intent_report_buy_success(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text(
        "Date,Close\n2026-07-01,50\n2026-07-02,50\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(
        script,
        "build_paper_preflight_report",
        lambda **kwargs: make_report(
            dry_run_signal="BUY",
            dry_run_final_decision="BUY: RSI below 30",
        ),
    )
    monkeypatch.setattr(
        script,
        "write_paper_preflight_report",
        lambda report: Path("reports/paper_trading/mock_preflight.json"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_order_intent",
        lambda intent: Path("reports/paper_trading/mock_intent.json"),
    )

    code = script.run_order_intent_report(
        env_file=Path(".env"),
        close_csv=csv_path,
        max_position_notional=10_000,
        max_equity_fraction=0.10,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "PAPER ORDER INTENT: BUY" in output
    assert "Estimated quantity: 200" in output
    assert "ORDER SUBMISSION: DISABLED" in output


def test_run_order_intent_report_blocked_returns_one(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text(
        "Date,Close\n2026-07-01,50\n2026-07-02,50\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(
        script,
        "build_paper_preflight_report",
        lambda **kwargs: make_report(
            ready_for_paper_order_phase=False,
            blocked_reasons=["kill switch engaged"],
        ),
    )
    monkeypatch.setattr(
        script,
        "write_paper_preflight_report",
        lambda report: Path("reports/paper_trading/mock_preflight.json"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_order_intent",
        lambda intent: Path("reports/paper_trading/mock_intent.json"),
    )

    code = script.run_order_intent_report(
        env_file=Path(".env"),
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "PAPER ORDER INTENT: BLOCKED" in output
    assert "kill switch engaged" in output


def test_run_order_intent_report_bad_csv_returns_one(tmp_path, capsys):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Wrong\n2026-07-01,50\n", encoding="utf-8")

    code = script.run_order_intent_report(
        env_file=None,
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "PAPER ORDER INTENT: FAIL" in output
