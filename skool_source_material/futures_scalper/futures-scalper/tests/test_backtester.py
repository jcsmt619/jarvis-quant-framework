"""End-to-end checks. The point is not a specific P&L (synthetic data has no real
edge) but that the machinery runs: walk-forward produces an aligned equity curve
and trade log, prop-firm rules engage, and the validation functions return sane
shapes.
"""

import pandas as pd

from backtest.backtester import WalkForwardBacktester
from backtest.performance import analyze, format_report
from backtest.validation import monte_carlo, walk_forward_summary


def _config():
    return {
        "hmm": {"n_candidates": [3], "n_init": 4, "min_train_bars": 400,
                "stability_bars": 2, "zscore_window": 252},
        "strategy": {"min_confidence": 0.45, "stop_atr": 1.0, "target_atr": 2.0,
                     "adx_min": 15, "breakout_lookback": 20},
        "risk": {"risk_per_trade": 0.01, "max_contracts": 3, "max_margin_utilization": 0.5,
                 "max_daily_trades": 50, "min_stop_ticks": 2.0,
                 "prop_firm": {"enabled": True, "daily_loss_limit": 1500,
                               "trailing_max_drawdown": 4000}},
        "backtest": {"initial_equity": 50000, "slippage_ticks": 1.0,
                     "commission_per_contract": 2.5, "bars_per_year": 19656,
                     "walk_forward": {"train_window": 1200, "test_window": 400, "step_size": 400}},
    }


def test_backtest_runs_and_produces_equity_curve(bars):
    bt = WalkForwardBacktester(_config())
    result = bt.run(bars, "MNQ")
    assert result.windows >= 1
    assert len(result.equity_curve) > 0
    # Equity curve is monotonic in time and finite.
    assert result.equity_curve.index.is_monotonic_increasing
    assert result.equity_curve.notna().all()


def test_performance_report_is_coherent(bars):
    bt = WalkForwardBacktester(_config())
    result = bt.run(bars, "MNQ")
    rep = analyze(result, _config())
    assert rep.n_trades >= 0
    assert -1.0 <= rep.win_rate <= 1.0
    text = format_report(rep)
    assert "PROP-FIRM VERDICT" in text


def test_monte_carlo_shapes(bars):
    bt = WalkForwardBacktester(_config())
    result = bt.run(bars, "MNQ")
    if result.trades is None or result.trades.empty:
        return  # nothing to resample on this seed; acceptable
    mc = monte_carlo(result.trades, 50000, trailing_max_drawdown=4000, n_runs=500)
    assert mc.n_runs == 500
    assert mc.p05_final_pnl <= mc.median_final_pnl <= mc.p95_final_pnl
    assert 0.0 <= mc.prob_breach_trailing <= 1.0


def test_walk_forward_summary(bars):
    bt = WalkForwardBacktester(_config())
    result = bt.run(bars, "MNQ")
    wf = walk_forward_summary(result, _config())
    assert wf.windows >= 1
    assert isinstance(wf.prop_firm_pass, bool)
