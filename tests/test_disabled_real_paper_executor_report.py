from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from paper_trading.paper_executor import RealPaperExecutionResult
from scripts import run_disabled_real_paper_executor_report as script


def test_load_close_prices_uses_date_index(tmp_path):
    csv_path = tmp_path / "eem.csv"
    pd.DataFrame(
        {
            "Date": ["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"],
            "Close": [66.0, 65.71],
        }
    ).to_csv(csv_path, index=False)

    close = script._load_close_prices(
        close_csv=csv_path,
        price_column="Close",
        date_column="Date",
    )

    assert len(close) == 2
    assert float(close.iloc[-1]) == 65.71
    assert close.index[-1].year == 2026


def test_disabled_real_paper_executor_report_blocks_by_default(capsys, tmp_path, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    pd.DataFrame(
        {
            "Date": ["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"],
            "Close": [66.0, 65.71],
        }
    ).to_csv(csv_path, index=False)

    captured = {}

    preflight = SimpleNamespace(
        symbol="EEM",
        strategy="rsi_revert",
        dry_run_signal="HOLD",
        blocked_reasons=["market_hours: market is closed"],
        ready_for_paper_order_phase=False,
    )
    intent = SimpleNamespace(
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal="HOLD",
        intent_action="BLOCKED",
        estimated_quantity=0,
        estimated_notional=0.0,
        latest_price=65.71,
        blocked_reasons=["market_hours: market is closed"],
    )
    gate = SimpleNamespace(
        execution_allowed=False,
        blocked_reasons=["order submission is disabled", "market_hours: market is closed"],
    )
    result = RealPaperExecutionResult(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        intent_action="BLOCKED",
        requested_signal="HOLD",
        execution_attempted=False,
        execution_status="BLOCKED",
        submitted_side=None,
        submitted_quantity=0,
        submitted_order_type=None,
        submitted_time_in_force=None,
        paper_order_id=None,
        blocked_reasons=["real Alpaca paper execution is disabled"],
        paper_client_used=False,
        real_broker_client_used=False,
        live_trading_enabled=False,
        order_submission_to_real_broker_enabled=False,
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", lambda: object())
    monkeypatch.setattr(script, "build_paper_preflight_report", lambda **kwargs: preflight)
    monkeypatch.setattr(script, "write_paper_preflight_report", lambda report: Path("preflight.json"))
    monkeypatch.setattr(script, "build_paper_order_intent", lambda **kwargs: intent)
    monkeypatch.setattr(script, "evaluate_paper_execution_gate", lambda **kwargs: gate)

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return result

    monkeypatch.setattr(script, "execute_real_alpaca_paper_order", fake_execute)
    monkeypatch.setattr(script, "write_real_paper_execution_result", lambda result: Path("real_paper.json"))

    code = script.run_disabled_real_paper_executor_report(
        env_file=Path(".env"),
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "DISABLED REAL PAPER EXECUTOR REPORT: PASS" in output
    assert "Execution status: BLOCKED" in output
    assert "REAL PAPER EXECUTION ENABLED: false" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert "LIVE TRADING: DISABLED" in output
    assert captured["paper_client_factory"] is None
    assert captured["real_paper_execution_enabled"] is False
    assert captured["confirmation"] is None


def test_disabled_real_paper_executor_report_missing_price_column_returns_one(capsys, tmp_path, monkeypatch):
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame({"Date": ["2026-07-02"], "AdjClose": [65.71]}).to_csv(csv_path, index=False)

    monkeypatch.setattr(script, "load_alpaca_paper_config", lambda: object())

    code = script.run_disabled_real_paper_executor_report(
        env_file=None,
        close_csv=csv_path,
        price_column="Close",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "DISABLED REAL PAPER EXECUTOR REPORT: FAIL" in output
    assert "price column" in output
