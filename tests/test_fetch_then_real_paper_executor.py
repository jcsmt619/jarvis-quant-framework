from pathlib import Path

import pandas as pd

from paper_trading.alpaca_account_state import AlpacaPaperSymbolState
from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.alpaca_market_data import AlpacaMarketDataResult
from paper_trading.paper_executor import PAPER_ORDER_CONFIRMATION
from scripts import run_fetch_then_real_paper_executor as script


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


def make_account_state(
    *,
    position_quantity=0.0,
    open_order_ids=None,
    account_status="ACTIVE",
):
    open_order_ids = open_order_ids or []
    return AlpacaPaperSymbolState(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        account_status=account_status,
        cash="100000",
        portfolio_value="100000",
        buying_power="400000",
        position_quantity=position_quantity,
        position_open=abs(position_quantity) > 0,
        open_symbol_orders_count=len(open_order_ids),
        open_symbol_order_ids=open_order_ids,
        read_only=True,
        order_submission_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def make_bars():
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"]),
            "Close": [66.0, 65.71],
        }
    )


def patch_fetch_and_state(monkeypatch, *, csv_path, account_state):
    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(script, "fetch_alpaca_daily_bars", lambda **kwargs: make_bars())
    monkeypatch.setattr(
        script,
        "write_market_data_csv",
        lambda **kwargs: (csv_path, make_market_data_result(str(csv_path))),
    )
    monkeypatch.setattr(
        script,
        "build_alpaca_paper_symbol_state",
        lambda **kwargs: account_state,
    )
    monkeypatch.setattr(
        script,
        "write_alpaca_paper_symbol_state",
        lambda state: Path("account_state.json"),
    )


def test_fetch_then_real_paper_report_disabled_by_default_uses_account_state(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(position_quantity=0.0)
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_executor(**kwargs):
        captured.update(kwargs)
        print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
        print("REAL PAPER EXECUTION ENABLED: false")
        print("REAL PAPER ORDER SUBMITTED: false")
        print("LIVE TRADING: DISABLED")
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_executor)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
        limit=120,
        feed="iex",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "READ-ONLY MARKET DATA FETCH: PASS" in output
    assert "READ-ONLY PAPER ACCOUNT STATE: PASS" in output
    assert "Actual EEM position quantity: 0.0" in output
    assert "Open EEM orders count: 0" in output
    assert "ONE-COMMAND REAL PAPER SAFETY SUMMARY" in output
    assert "REAL PAPER EXECUTION ENABLED: false" in output
    assert "CONFIRMATION ACCEPTED: false" in output
    assert "LIVE TRADING: DISABLED" in output
    assert captured["env_file"] is None
    assert captured["close_csv"] == csv_path
    assert captured["position_open"] is False
    assert captured["current_position_quantity"] == 0
    assert captured["external_blocked_reasons"] == []
    assert captured["enable_real_paper_execution"] is False
    assert captured["confirmation"] is None


def test_fetch_then_real_paper_report_passes_actual_position_quantity(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(position_quantity=4.0)
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_executor(**kwargs):
        captured.update(kwargs)
        print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
        print("REAL PAPER EXECUTION ENABLED: true")
        print("CONFIRMATION ACCEPTED: true")
        print("REAL PAPER ORDER SUBMITTED: false")
        print("LIVE TRADING: DISABLED")
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_executor)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
        limit=120,
        feed="iex",
        enable_real_paper_execution=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Actual EEM position quantity: 4.0" in output
    assert "REAL PAPER EXECUTION ENABLED: true" in output
    assert "CONFIRMATION ACCEPTED: true" in output
    assert captured["position_open"] is True
    assert captured["current_position_quantity"] == 4
    assert captured["enable_real_paper_execution"] is True
    assert captured["confirmation"] == PAPER_ORDER_CONFIRMATION


def test_fetch_then_real_paper_report_blocks_when_open_symbol_orders_exist(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(open_order_ids=["order_1"])
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_executor(**kwargs):
        captured.update(kwargs)
        print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
        print("REAL PAPER ORDER SUBMITTED: false")
        print("LIVE TRADING: DISABLED")
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_executor)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Open EEM orders count: 1" in output
    assert "open EEM paper orders exist: 1" in output
    assert captured["external_blocked_reasons"] == ["open EEM paper orders exist: 1"]


def test_fetch_then_real_paper_report_blocks_when_account_not_active(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(account_status="ACCOUNT_BLOCKED")
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_executor(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_executor)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "paper account status is not ACTIVE: ACCOUNT_BLOCKED" in output
    assert captured["external_blocked_reasons"] == [
        "paper account status is not ACTIVE: ACCOUNT_BLOCKED"
    ]


def test_fetch_then_real_paper_report_fetch_failure_returns_one(capsys, monkeypatch):
    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)

    def fail_fetch(**kwargs):
        raise ValueError("No market bars returned")

    monkeypatch.setattr(script, "fetch_alpaca_daily_bars", fail_fetch)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "FETCH + ACCOUNT STATE + ARMED REAL PAPER REPORT: FAIL" in output
    assert "No market bars returned" in output


def test_fetch_then_real_paper_report_propagates_executor_failure(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state()

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)
    monkeypatch.setattr(script, "run_real_paper_executor_report", lambda **kwargs: 1)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "READ-ONLY MARKET DATA FETCH: PASS" in output
    assert "READ-ONLY PAPER ACCOUNT STATE: PASS" in output
    assert "ONE-COMMAND REAL PAPER SAFETY SUMMARY" in output


def test_account_state_open_orders_force_blocked_intent_through_real_report(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(open_order_ids=["order_1"])
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_real_report(**kwargs):
        captured.update(kwargs)
        print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
        print("Intent action: BLOCKED")
        print("Execution gate status: BLOCKED")
        print("Execution allowed: False")
        print("Execution attempted: False")
        print("PAPER CLIENT USED: false")
        print("REAL BROKER CLIENT USED: false")
        print("REAL PAPER ORDER SUBMITTED: false")
        print("LIVE TRADING: DISABLED")
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_real_report)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
        enable_real_paper_execution=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Open EEM orders count: 1" in output
    assert "open EEM paper orders exist: 1" in output
    assert "Intent action: BLOCKED" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert captured["external_blocked_reasons"] == ["open EEM paper orders exist: 1"]
    assert captured["enable_real_paper_execution"] is True
    assert captured["confirmation"] == PAPER_ORDER_CONFIRMATION


def test_account_state_not_active_forces_external_block_reason(capsys, monkeypatch):
    csv_path = Path("reports/paper_trading/mock_eem.csv")
    account_state = make_account_state(account_status="ACCOUNT_BLOCKED")
    captured = {}

    patch_fetch_and_state(monkeypatch, csv_path=csv_path, account_state=account_state)

    def fake_real_report(**kwargs):
        captured.update(kwargs)
        print("ARMED REAL PAPER EXECUTOR REPORT: PASS")
        print("Intent action: BLOCKED")
        print("Execution attempted: False")
        print("REAL PAPER ORDER SUBMITTED: false")
        print("LIVE TRADING: DISABLED")
        return 0

    monkeypatch.setattr(script, "run_real_paper_executor_report", fake_real_report)

    code = script.run_fetch_then_real_paper_executor_report(
        env_file=Path(".env"),
        symbol="EEM",
        enable_real_paper_execution=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "paper account status is not ACTIVE: ACCOUNT_BLOCKED" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert captured["external_blocked_reasons"] == [
        "paper account status is not ACTIVE: ACCOUNT_BLOCKED"
    ]
    assert captured["enable_real_paper_execution"] is True
    assert captured["confirmation"] == PAPER_ORDER_CONFIRMATION
