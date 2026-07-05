"""
tests/test_paper_trading_dry_run.py
====================================
Tests for Phase 2 of the Alpaca Paper-Trading Gate (dry-run signal
logger). See docs/ALPACA_PAPER_TRADING_GATE_SPEC.md.

These tests never connect to a broker and never touch .env / API keys.
"""

import numpy as np
import pandas as pd
import pytest

from paper_trading.allowlist import NotAllowedError, is_allowed
from paper_trading.dry_run_logger import (
    APPROVED_ASSET,
    APPROVED_PARAMS,
    APPROVED_STRATEGY,
    SIGNAL_BUY,
    SIGNAL_EXIT,
    SIGNAL_HOLD,
    evaluate_dry_run,
)
from paper_trading.risk_gates import evaluate_all_gates


def _make_price_series(values, freq="D"):
    """Anchored so the last bar is 'now' -- avoids tripping the Phase-2
    stale-data risk gate placeholder, which is tested separately below."""
    end = pd.Timestamp.now(tz="UTC").floor("min")
    idx = pd.date_range(end=end, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


def _low_rsi_series(n=40):
    """Mostly-declining path with a couple of small up-ticks mixed in
    (avoids the indicator's zero-loss/zero-gain edge case, which clamps
    RSI to exactly 50 -- see edge_hunting/indicators.py::rsi) so RSI
    lands solidly under the 30 oversold threshold."""
    vals = [100.0]
    for i in range(1, n):
        step = 0.6 if i % 7 == 0 else -1.0
        vals.append(vals[-1] + step)
    return _make_price_series(vals)


def _high_rsi_series(n=40):
    """Mostly-rising path with a couple of small down-ticks mixed in,
    for the same reason as _low_rsi_series -- lands solidly over the 70
    overbought threshold."""
    vals = [50.0]
    for i in range(1, n):
        step = -0.6 if i % 7 == 0 else 1.0
        vals.append(vals[-1] + step)
    return _make_price_series(vals)


def _flat_series(n=40):
    """Alternating small moves -> RSI should land near 50 (HOLD zone)."""
    vals = [100 + (1 if i % 2 == 0 else -1) for i in range(n)]
    return _make_price_series(vals)



# ---------------------------------------------------------------------------
# 1. Allowlist behavior
# ---------------------------------------------------------------------------

def test_approved_eem_rsi_config_is_allowed():
    assert is_allowed(APPROVED_STRATEGY, APPROVED_ASSET, dict(APPROVED_PARAMS)) is True


def test_unapproved_symbol_is_blocked():
    assert is_allowed(APPROVED_STRATEGY, "SPY", dict(APPROVED_PARAMS)) is False


def test_unapproved_rsi_parameters_are_blocked():
    bad_params = dict(APPROVED_PARAMS)
    bad_params["window"] = 21
    assert is_allowed(APPROVED_STRATEGY, APPROVED_ASSET, bad_params) is False

    bad_params2 = dict(APPROVED_PARAMS)
    bad_params2["oversold"] = 25
    assert is_allowed(APPROVED_STRATEGY, APPROVED_ASSET, bad_params2) is False

    bad_params3 = dict(APPROVED_PARAMS)
    bad_params3["overbought"] = 80
    assert is_allowed(APPROVED_STRATEGY, APPROVED_ASSET, bad_params3) is False


def test_unapproved_strategy_family_is_blocked():
    assert is_allowed("bollinger_revert", APPROVED_ASSET, dict(APPROVED_PARAMS)) is False


def test_evaluate_dry_run_raises_for_unapproved_symbol():
    with pytest.raises(NotAllowedError):
        evaluate_dry_run(
            symbol="SPY",
            strategy=APPROVED_STRATEGY,
            params=dict(APPROVED_PARAMS),
            close_prices=_low_rsi_series(),
        )


def test_evaluate_dry_run_raises_for_unapproved_params():
    bad_params = dict(APPROVED_PARAMS)
    bad_params["window"] = 9
    with pytest.raises(NotAllowedError):
        evaluate_dry_run(
            symbol=APPROVED_ASSET,
            strategy=APPROVED_STRATEGY,
            params=bad_params,
            close_prices=_low_rsi_series(),
        )


# ---------------------------------------------------------------------------
# 2. Signal logic
# ---------------------------------------------------------------------------

def test_buy_signal_when_rsi_below_30():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_low_rsi_series(),
        position_open=False,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    assert result.rsi_value is not None
    assert result.rsi_value < 30
    assert result.signal == SIGNAL_BUY
    assert result.order_submitted is False


def test_exit_signal_when_rsi_above_70_and_position_open():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_high_rsi_series(),
        position_open=True,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    assert result.rsi_value is not None
    assert result.rsi_value > 70
    assert result.signal == SIGNAL_EXIT
    assert result.order_submitted is False


def test_hold_when_rsi_above_70_but_no_position_open():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_high_rsi_series(),
        position_open=False,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    assert result.signal == SIGNAL_HOLD
    assert result.order_submitted is False


def test_hold_when_rsi_between_thresholds():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_flat_series(),
        position_open=False,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    assert result.signal == SIGNAL_HOLD
    assert result.order_submitted is False


# ---------------------------------------------------------------------------
# 3. Dry-run mode never submits orders (across every signal type)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "series,position_open",
    [
        (_low_rsi_series(), False),
        (_high_rsi_series(), True),
        (_flat_series(), False),
    ],
)
def test_dry_run_never_submits_orders(series, position_open):
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=series,
        position_open=position_open,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    assert result.order_submitted is False
    assert "no order was submitted" in result.note.lower()


# ---------------------------------------------------------------------------
# 4. Risk gates
# ---------------------------------------------------------------------------

def test_kill_switch_blocks_action():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_low_rsi_series(),  # would otherwise be BUY
        position_open=False,
        is_market_open=True,
        kill_switch_engaged=True,
    )
    assert result.risk_gate_passed is False
    assert result.signal == SIGNAL_HOLD  # forced to HOLD despite raw BUY signal
    assert result.order_submitted is False
    assert "kill switch" in "; ".join(
        detail for ok, detail in result.risk_gate_checks.values() if not ok
    ).lower()


def test_market_closed_blocks_action():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_low_rsi_series(),
        position_open=False,
        is_market_open=False,
        kill_switch_engaged=False,
    )
    assert result.risk_gate_passed is False
    assert result.signal == SIGNAL_HOLD
    assert result.order_submitted is False


def test_max_position_size_gate_direct():
    status = evaluate_all_gates(
        target_notional=10_000.0,
        is_market_open=True,
        bar_count=20,
        latest_bar_timestamp=pd.Timestamp.now(tz="UTC"),
    )
    assert status.passed is False
    assert status.checks["max_position_size"][0] is False


def test_stale_data_gate_blocks_when_timestamp_missing():
    status = evaluate_all_gates(
        target_notional=100.0,
        is_market_open=True,
        bar_count=20,
        latest_bar_timestamp=None,
    )
    assert status.checks["stale_data"][0] is False
    assert status.passed is False


def test_insufficient_bars_gate_blocks():
    status = evaluate_all_gates(
        target_notional=100.0,
        is_market_open=True,
        bar_count=3,
        latest_bar_timestamp=pd.Timestamp.now(tz="UTC"),
    )
    assert status.checks["sufficient_bars"][0] is False
    assert status.passed is False


# ---------------------------------------------------------------------------
# 5. Logging output contains required fields, still no order
# ---------------------------------------------------------------------------

def test_result_contains_all_required_fields():
    result = evaluate_dry_run(
        symbol=APPROVED_ASSET,
        strategy=APPROVED_STRATEGY,
        params=dict(APPROVED_PARAMS),
        close_prices=_low_rsi_series(),
        position_open=False,
        is_market_open=True,
        kill_switch_engaged=False,
    )
    record = result.to_dict()
    for field in (
        "timestamp",
        "symbol",
        "latest_price",
        "rsi_value",
        "position_state_assumption",
        "signal",
        "reason",
        "risk_gate_passed",
        "risk_gate_checks",
        "final_decision",
        "order_submitted",
        "note",
    ):
        assert field in record
    assert record["order_submitted"] is False
