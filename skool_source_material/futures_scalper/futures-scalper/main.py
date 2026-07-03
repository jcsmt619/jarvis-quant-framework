"""Futures Scalper - entry point.

Modes:
    train-only   Fit the regime HMM on history and save it.
    backtest     Walk-forward backtest with contract P&L and prop-firm rules.
    validate     Backtest plus the big three: walk-forward, Monte Carlo, sensitivity.
    live         Session-aware loop. With the sim broker it replays a data source
                 so you can watch the whole pipeline with no account; with IBKR or
                 TradeStation it polls real bars and places real orders.

Defaults are conservative and the broker defaults to the simulator, so
`python main.py live --demo` runs out of the box.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

from brokers import make_broker
from brokers.base import OrderRequest, OrderSide, OrderType
from core.features import FeatureEngineer
from core.hmm_engine import HMMEngine
from core.instruments import apply_overrides, get_instrument
from core.risk_manager import AccountState, HaltLevel, RiskManager
from core.scalp_strategies import Direction, ScalpOrchestrator
from core.sessions import SessionCalendar
from data.loaders import load_bars
from monitoring.dashboard import Dashboard
from monitoring.logger import log_channel, setup_logger
from monitoring.notifier import TelegramNotifier


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _primary_symbol(config: dict) -> str:
    syms = config.get("universe", {}).get("symbols", ["MNQ"])
    return syms[0] if syms else "MNQ"


def _instrument_for(config: dict, symbol: str):
    overrides = (config.get("instruments", {}) or {}).get(symbol)
    if overrides:
        return apply_overrides(symbol, overrides)
    return get_instrument(symbol)


# --------------------------------------------------------------------------
# train-only
# --------------------------------------------------------------------------

def run_train_only(config: dict, logger) -> None:
    symbol = _primary_symbol(config)
    bars = load_bars(config.get("data", {}).get("source", {}))
    fe = FeatureEngineer(config.get("hmm", {}))
    feats = fe.compute_hmm_features(bars)
    eng = HMMEngine(config.get("hmm", {}))
    metrics = eng.fit(feats)
    model_path = Path(config.get("model", {}).get("save_dir", "models")) / f"{symbol}_hmm.pkl"
    eng.save(model_path)
    logger.info("Trained HMM: %d regimes, %d samples, BIC %s",
                metrics.n_regimes_selected, metrics.n_samples,
                {k: round(v) for k, v in metrics.bic_scores.items()})
    logger.info("Regimes: %s", [ri.regime_name for ri in eng.regime_infos])
    logger.info("Saved model to %s", model_path)


# --------------------------------------------------------------------------
# backtest / validate
# --------------------------------------------------------------------------

def run_backtest(config: dict, logger) -> None:
    from backtest.backtester import WalkForwardBacktester
    from backtest.performance import analyze, format_report

    symbol = _primary_symbol(config)
    instrument = _instrument_for(config, symbol)
    bars = load_bars(config.get("data", {}).get("source", {}))
    logger.info("Backtesting %s on %d bars", symbol, len(bars))

    bt = WalkForwardBacktester(config, instrument=instrument)
    result = bt.run(bars, symbol)
    report = analyze(result, config)
    print(format_report(report))

    out = Path("results")
    out.mkdir(exist_ok=True)
    if len(result.equity_curve):
        result.equity_curve.to_csv(out / "equity_curve.csv")
    if result.trades is not None and not result.trades.empty:
        result.trades.to_csv(out / "trade_log.csv", index=False)
    if result.regime_history is not None and not result.regime_history.empty:
        result.regime_history.to_csv(out / "regime_history.csv")
    logger.info("Wrote results/ CSVs")


def run_validate(config: dict, logger) -> None:
    from backtest.backtester import WalkForwardBacktester
    from backtest.performance import analyze, format_report
    from backtest.validation import monte_carlo, sensitivity, walk_forward_summary

    symbol = _primary_symbol(config)
    instrument = _instrument_for(config, symbol)
    bars = load_bars(config.get("data", {}).get("source", {}))

    bt = WalkForwardBacktester(config, instrument=instrument)
    result = bt.run(bars, symbol)
    report = analyze(result, config)
    print(format_report(report))

    wf = walk_forward_summary(result, config)
    print(f"\nWALK-FORWARD: {wf.windows} windows, OOS P&L ${wf.oos_total_pnl:,.0f}, "
          f"Sharpe {wf.oos_sharpe:.2f}. {wf.note}")

    tmdd = float(config.get("risk", {}).get("prop_firm", {}).get("trailing_max_drawdown", 0))
    mc = monte_carlo(result.trades, result.meta.get("initial_equity", 50000.0),
                     trailing_max_drawdown=tmdd, n_runs=2000)
    print(f"\nMONTE CARLO ({mc.n_runs} runs): median P&L ${mc.median_final_pnl:,.0f}, "
          f"5th pct ${mc.p05_final_pnl:,.0f}, 95th pct ${mc.p95_final_pnl:,.0f}")
    print(f"  worst drawdown ${mc.worst_max_drawdown:,.0f}, "
          f"prob of breaching trailing limit {mc.prob_breach_trailing*100:.1f}%")

    sens = sensitivity(bars, symbol, config)
    print(f"\nSENSITIVITY: {sens.note}")
    print(sens.table.to_string(index=False))


# --------------------------------------------------------------------------
# live (sim/demo replay or real-broker polling)
# --------------------------------------------------------------------------

def run_live(config: dict, logger, demo: bool = False, fast: bool = False) -> None:
    symbol = _primary_symbol(config)
    instrument = _instrument_for(config, symbol)
    calendar = SessionCalendar(config.get("sessions", {}))
    notifier = TelegramNotifier(config.get("monitoring", {}).get("telegram", {}))
    dashboard = Dashboard(config.get("monitoring", {}).get("dashboard_enabled", True))

    broker_cfg = config.get("broker", {})
    broker = make_broker(broker_cfg)
    broker.connect()
    is_sim = broker.name == "sim"

    # Load or train the regime model.
    fe = FeatureEngineer(config.get("hmm", {}))
    model_path = Path(config.get("model", {}).get("save_dir", "models")) / f"{symbol}_hmm.pkl"
    eng = HMMEngine(config.get("hmm", {}))
    warmup = load_bars(config.get("data", {}).get("source", {}))
    if model_path.exists():
        eng.load(model_path)
        logger.info("Loaded HMM from %s", model_path)
    else:
        eng.fit(fe.compute_hmm_features(warmup))
        eng.save(model_path)
        logger.info("Trained and saved HMM (no saved model found)")

    orch = ScalpOrchestrator(config.get("strategy", {}), eng.regime_infos)
    risk = RiskManager(config.get("risk", {}))

    if risk.check_lock_file():
        logger.error("Lock file present (%s). Delete it to resume trading. Exiting.",
                     risk.lock_file)
        sys.exit(1)

    acct_info = broker.get_account()
    acct = AccountState(equity=acct_info.equity, starting_equity=acct_info.equity,
                        session_start_equity=acct_info.equity, high_water_mark=acct_info.equity)

    min_conf = float(config.get("strategy", {}).get("min_confidence", 0.50))
    loop_sleep = 0.0 if fast else float(config.get("schedule", {}).get("loop_interval_seconds", 5))

    # Bar source: demo/sim replays a loaded series; live brokers poll get_bars.
    replay = warmup if (is_sim or demo) else None
    if is_sim and replay is not None:
        for _, b in replay.head(200).iterrows():
            broker.set_price(symbol, float(b["close"]))

    dashboard.start()
    cur_day = None
    try:
        if replay is not None:
            buffer = replay.iloc[:200].copy()
            stream = replay.iloc[200:]
            for ts, bar in stream.iterrows():
                buffer = pd.concat([buffer, bar.to_frame().T])
                if is_sim:
                    trade = broker.on_bar(symbol, bar)
                    if trade:
                        log_channel(logger, "trades", f"exit {trade['direction']} {symbol} "
                                    f"@ {trade['exit']:.2f} pnl ${trade['pnl']:.0f}", **trade)
                cur_day = _maybe_new_session(risk, acct, ts, cur_day)
                _step(config, symbol, instrument, buffer, eng, orch, risk, acct,
                      broker, notifier, dashboard, calendar, logger, min_conf, ts)
                if loop_sleep:
                    time.sleep(min(loop_sleep, 0.05))
        else:
            logger.info("Live polling mode for broker '%s'. Ctrl-C to stop.", broker.name)
            tf = config.get("universe", {}).get("signal_timeframe", "5Min")
            while True:
                if not calendar.is_open():
                    logger.info("Market closed. Next open %s", calendar.next_open())
                    time.sleep(loop_sleep or 30)
                    continue
                bars = broker.get_bars(symbol, timeframe=tf, limit=400)
                if bars is None or len(bars) < 250:
                    time.sleep(loop_sleep or 5)
                    continue
                ts = bars.index[-1]
                cur_day = _maybe_new_session(risk, acct, ts, cur_day)
                _step(config, symbol, instrument, bars, eng, orch, risk, acct,
                      broker, notifier, dashboard, calendar, logger, min_conf, ts)
                time.sleep(loop_sleep or 5)
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Positions keep their stops in place.")
    finally:
        dashboard.stop()
        broker.disconnect()


def _maybe_new_session(risk, acct, ts, cur_day):
    day = pd.Timestamp(ts).normalize()
    if cur_day is None:
        return day
    if day != cur_day:
        risk.start_session(acct)
        acct.high_water_mark = max(acct.high_water_mark, acct.equity)
    return day


def _step(config, symbol, instrument, bars, eng, orch, risk, acct,
          broker, notifier, dashboard, calendar, logger, min_conf, ts) -> None:
    fe = FeatureEngineer(config.get("hmm", {}))
    feats = fe.compute_hmm_features(bars)
    if len(feats) == 0:
        return
    strat_feats = fe.compute_strategy_features(bars)

    # Sync equity from broker, run breakers.
    acct.equity = broker.get_account().equity
    risk.update_after_fill_or_mark(acct)

    regime = eng.predict_regime_filtered(feats)
    log_channel(logger, "regime", f"regime {regime.label} ({regime.probability:.2f}) "
                f"confirmed={regime.is_confirmed}", regime=regime.label,
                prob=regime.probability)

    if risk.breaker.level is HaltLevel.HALTED_LOCKED:
        broker.close_all()
        notifier.breaker("ACCOUNT LOCKED", risk.breaker.reason)
        logger.error("Account locked: %s", risk.breaker.reason)
        _render(dashboard, symbol, broker, acct, regime, eng, risk, calendar, config)
        return

    positions = broker.get_positions()
    has_pos = any(p.symbol == symbol and p.quantity != 0 for p in positions)

    if (not risk.is_halted() and regime.is_confirmed and regime.probability >= min_conf
            and not eng.is_flickering() and not has_pos):
        sig = orch.generate_signal(symbol, strat_feats, regime, instrument)
        if sig is not None and sig.direction is not Direction.FLAT:
            decision = risk.validate_signal(acct, sig, instrument)
            if decision.approved and decision.contracts >= 1:
                side = OrderSide.BUY if sig.direction is Direction.LONG else OrderSide.SELL
                if broker.name == "sim":
                    broker.set_price(symbol, sig.entry_price)
                res = broker.place_bracket(OrderRequest(
                    symbol=symbol, side=side, quantity=decision.contracts,
                    order_type=OrderType.MARKET, limit_price=sig.entry_price,
                    stop_loss=sig.stop_price, take_profit=sig.target_price))
                if res.accepted:
                    acct.trades_today += 1
                    notifier.signal(symbol, sig.direction.value, decision.contracts,
                                    sig.entry_price, sig.stop_price, sig.target_price, regime.label)
                    log_channel(logger, "trades",
                                f"entry {sig.direction.value} {decision.contracts} {symbol} "
                                f"@ {sig.entry_price:.2f} stop {sig.stop_price:.2f}",
                                **{"reason": sig.reasoning})

    _render(dashboard, symbol, broker, acct, regime, eng, risk, calendar, config)


def _render(dashboard, symbol, broker, acct, regime, eng, risk, calendar, config) -> None:
    info = broker.get_account()
    pf = config.get("risk", {}).get("prop_firm", {})
    positions = [{"symbol": p.symbol, "side": "long" if p.quantity > 0 else "short",
                  "qty": abs(p.quantity), "avg": p.avg_price, "upnl": p.unrealized_pnl}
                 for p in broker.get_positions()]
    dashboard.render({
        "symbol": symbol, "session": calendar.session_type().value,
        "clock": str(calendar.now_et().strftime("%a %H:%M ET")),
        "regime": regime.label, "regime_prob": regime.probability,
        "stability": eng.get_regime_stability(), "flicker": eng.get_regime_flicker_rate(),
        "positions": positions, "equity": info.equity,
        "daily_loss": max(0.0, acct.session_start_equity - info.equity),
        "daily_limit": float(pf.get("daily_loss_limit", 1000)),
        "trailing_used": max(0.0, acct.high_water_mark - info.equity),
        "trailing_limit": float(pf.get("trailing_max_drawdown", 2000)),
        "realized_today": info.realized_pnl, "broker": broker.name,
    })


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Futures Scalper")
    p.add_argument("mode", choices=["live", "backtest", "validate", "train-only"])
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--demo", action="store_true", help="Replay a data source through the live loop.")
    p.add_argument("--fast", action="store_true", help="No sleep between loop iterations.")
    args = p.parse_args()

    config = load_config(args.config)
    mon = config.get("monitoring", {})
    logger = setup_logger("futures_scalper", level=mon.get("log_level", "INFO"),
                          log_dir=mon.get("log_dir", "logs"),
                          json_files=mon.get("json_log_files", True))

    if args.mode == "train-only":
        run_train_only(config, logger)
    elif args.mode == "backtest":
        run_backtest(config, logger)
    elif args.mode == "validate":
        run_validate(config, logger)
    elif args.mode == "live":
        run_live(config, logger, demo=args.demo, fast=args.fast)


if __name__ == "__main__":
    main()
