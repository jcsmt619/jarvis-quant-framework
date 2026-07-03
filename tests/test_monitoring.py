"""
tests/test_monitoring.py
========================
Covers the STEP 8 monitoring stack: structured JSON logging with the mandated
fields, per-type alert rate limiting, and dashboard rendering.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from monitoring.alerts import AlertManager, AlertType
from monitoring.dashboard import DashboardState, Position, render_dashboard
from monitoring.logger import JsonFormatter, STATE_FIELDS


def test_json_formatter_has_mandated_fields():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "state", None, None)
    record.regime = "BULL"
    record.probability = 0.72
    record.equity = 105230.0
    record.positions = [{"symbol": "TQQQ", "side": "LONG"}]
    record.daily_pnl = 3400.0
    payload = json.loads(JsonFormatter().format(record))
    for field in ("timestamp", *STATE_FIELDS):
        assert field in payload
    assert payload["regime"] == "BULL"
    assert payload["positions"][0]["symbol"] == "TQQQ"


def test_alert_rate_limit_per_type():
    sent: list = []
    mgr = AlertManager(rate_limit_minutes=15, sink=sent.append)
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    assert mgr.regime_shift("BULL", "BEAR", now=t0) is True
    # Same type within 15 min -> suppressed.
    assert mgr.regime_shift("BEAR", "BULL", now=t0 + timedelta(minutes=5)) is False
    # A DIFFERENT critical type still gets through in the same window.
    assert mgr.circuit_breaker("DAILY_HALT", 0.061, 94000.0, now=t0 + timedelta(minutes=1)) is True
    # After the window elapses, the regime alert can fire again.
    assert mgr.regime_shift("BULL", "BEAR", now=t0 + timedelta(minutes=16)) is True
    assert len(sent) == 3


def test_dashboard_renders_without_error():
    state = DashboardState(
        regime_label="BULL", risk_on=True, stability_bars=14, vol_level="Low",
        equity=105230.0, daily_pnl=3400.0, daily_pnl_pct=3.2,
        allocation_pct=250.0, leverage=2.5,
        positions=[Position("TQQQ", "LONG", 60.50, 4.2, 58.00)],
        daily_dd=0.005, peak_dd=0.012,
    )
    group = render_dashboard(state)
    # Render to a string via a rich console to confirm no exceptions.
    from rich.console import Console
    console = Console(file=open("nul" if __import__("os").name == "nt" else "/dev/null", "w"), width=80)
    console.print(group)
    assert group is not None
