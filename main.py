"""
main.py — CLI entry point for the regime-trader framework.

Usage:
    python main.py backtest --symbols SPY --start 2020-01-01 --end 2024-12-31
    python main.py backtest --symbols SPY --compare
    python main.py backtest --symbols SPY --stress-test
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
RAW_DIR = ROOT / "data" / "raw"

from backtest import performance, stress_test
from backtest.backtester import WalkForwardBacktester


def load_price_data(symbol: str, start: str | None, end: str | None) -> pd.DataFrame:
    """Load OHLCV from local data/raw (parquet preferred), yfinance fallback."""
    stem = symbol.lower().replace("-", "_").replace("/", "_")
    frame = None
    for ext in (".parquet", ".csv"):
        path = RAW_DIR / f"{stem}{ext}"
        if path.exists():
            frame = pd.read_parquet(path) if ext == ".parquet" else pd.read_csv(path, parse_dates=["date"])
            break
    if frame is None:
        print(f"  No local data for {symbol}; attempting yfinance fallback...")
        import yfinance as yf
        raw = yf.download(symbol, start=start or "2010-01-01", end=end, auto_adjust=False, progress=False)
        if raw.empty:
            raise FileNotFoundError(f"No data available for {symbol}")
        raw = raw.reset_index()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]
        frame = raw.rename(columns={"Date": "date"})

    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    frame.columns = [c.lower() for c in frame.columns]
    frame = frame[["open", "high", "low", "close", "volume"]]
    if start:
        frame = frame[frame.index >= pd.Timestamp(start)]
    if end:
        frame = frame[frame.index <= pd.Timestamp(end)]
    return frame


def cmd_backtest_multistrat(args: argparse.Namespace) -> None:
    """
    Run every ENABLED registered strategy together through the capital allocator,
    tracking BOTH portfolio-level and per-strategy metrics. Each strategy is
    converted into a daily-return stream via the single-strategy walk-forward on
    its primary configured symbol (config/settings.yaml -> strategies.<name>.symbols).
    """
    from backtest.multistrat import MultiStrategyBacktester, write_outputs
    from core.capital_allocator import AllocatorConfig, CapitalAllocator
    from core.registered_strategies import apply_config, register_all
    from core.strategy_registry import StrategyRegistry

    registry = StrategyRegistry()
    register_all(registry)
    apply_config(registry)

    enabled = registry.active()
    if len(enabled) < 2:
        print("Multi-strat mode needs >=2 enabled strategies in config/settings.yaml.")
        return

    bt = WalkForwardBacktester(
        train_window=args.train_window, test_window=args.test_window,
        step_size=args.step_size, slippage=args.slippage, n_init=args.n_init,
    )

    print("\n" + "#" * 74)
    print(f"# MULTI-STRATEGY BACKTEST   ({args.start or 'start'} -> {args.end or 'end'})")
    print("#" * 74)

    strategy_returns: dict[str, pd.Series] = {}
    strategy_symbol: dict[str, str] = {}
    for name, strat in enabled.items():
        if not strat.symbols:
            print(f"  Skipping '{name}': no symbols configured.")
            continue
        symbol = strat.symbols[0]
        strategy_symbol[name] = symbol
        print(f"  Backtesting '{name}' on {symbol} ...")
        df = load_price_data(symbol, args.start, args.end)
        result = bt.run(df, symbol=symbol)
        strategy_returns[name] = pd.Series(result.returns, index=result.index)

    if len(strategy_returns) < 2:
        print("Not enough strategies produced return streams.")
        return

    cfg = AllocatorConfig.from_settings()
    allocator = CapitalAllocator(registry, cfg)
    engine = MultiStrategyBacktester(
        registry, allocator, corr_window=cfg.corr_window, corr_threshold=cfg.corr_merge_threshold)
    res = engine.run(strategy_returns)

    # --- report ---
    pm = res.portfolio_metrics
    print("\n" + "=" * 74)
    print("PORTFOLIO (dynamically allocated)")
    print("=" * 74)
    print(f"  Total return : {pm['total_return']:+.1%}    CAGR: {pm['cagr']:+.1%}")
    print(f"  Sharpe       : {pm['sharpe']:.2f}    Sortino: {pm['sortino']:.2f}")
    print(f"  Max drawdown : {pm['max_drawdown']:.1%}    Calmar: {pm['calmar']:.2f}")
    print(f"  Allocator turnover events: {res.turnover}")

    print("\nPER-STRATEGY")
    print(f"  {'name':<20}{'total':>10}{'sharpe':>9}{'maxDD':>9}{'contrib%':>10}{'disabled':>10}")
    for name, m in res.per_strategy_metrics.items():
        print(f"  {name:<20}{m['total_return']:>+10.1%}{m['sharpe']:>9.2f}"
              f"{m['max_drawdown']:>9.1%}{m['contribution_return_pct']:>10.1%}{m['disabled_days']:>10}")

    print("\nCORRELATION (% of OOS time any pair's rolling corr > {:.0%})".format(cfg.corr_merge_threshold))
    for pair, pct in res.pair_over_threshold_pct.items():
        print(f"  {pair:<28}{pct:>6.1%}")

    benchmarks = {}
    if args.compare:
        # buy-and-hold of the most-weighted strategy's symbol
        avg_w = {n: res.weight_history[n].mean() for n in strategy_returns}
        top = max(avg_w, key=avg_w.get)
        bh_df = load_price_data(strategy_symbol[top], args.start, args.end)
        bh_ret = bh_df["close"].pct_change().dropna()
        benchmarks = engine.run_benchmarks(strategy_returns, res.per_strategy_metrics, buy_hold_returns=bh_ret)
        print("\nBENCHMARKS")
        for label, m in benchmarks.items():
            nm = f" ({m['name']})" if "name" in m else ""
            print(f"  {label + nm:<28} total {m['total_return']:>+8.1%}   "
                  f"maxDD {m['max_drawdown']:>7.1%}   Calmar {m['calmar']:>6.2f}")

    # --- the verdict ---
    best_single = max(res.per_strategy_metrics.values(), key=lambda m: m["calmar"])
    print("\n" + "=" * 74)
    verdict = "YES" if pm["calmar"] > best_single["calmar"] else "NO"
    print(f"Does multi-strat beat the best single strategy on Calmar? {verdict}")
    print(f"  multi-strat Calmar {pm['calmar']:.2f}  vs  best single {best_single['calmar']:.2f}")
    if verdict == "NO":
        print("  -> The extra allocation machinery is NOT paying for itself here.")
    print("=" * 74)

    out_dir = ROOT / "logs" / "multistrat"
    write_outputs(res, out_dir)
    print(f"\nWrote CSVs to {out_dir}")


def cmd_backtest(args: argparse.Namespace) -> None:
    # STEP 2 mandates logging regime changes at WARNING (useful live), but that
    # floods a backtest that flips regimes hundreds of times. Quiet it here.
    import warnings
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="Model is not converging")

    if getattr(args, "multi_strat", False):
        cmd_backtest_multistrat(args)
        return

    bt = WalkForwardBacktester(
        train_window=args.train_window,
        test_window=args.test_window,
        step_size=args.step_size,
        slippage=args.slippage,
        n_init=args.n_init,
    )

    for symbol in args.symbols:
        print("\n" + "#" * 74)
        print(f"# BACKTEST: {symbol}   ({args.start or 'start'} → {args.end or 'end'})")
        print("#" * 74)
        df = load_price_data(symbol, args.start, args.end)
        print(f"Loaded {len(df)} bars for {symbol}. Running walk-forward...")

        result = bt.run(df, symbol=symbol)

        benchmarks = None
        if args.compare:
            print("Computing benchmarks (buy&hold, 200-SMA, random x100)...")
            benchmarks = {
                "Buy & Hold": bt.benchmark_buy_hold(result.close),
                "200-SMA Trend": bt.benchmark_sma200(result.close, result.sma200),
                "random": bt.benchmark_random(result.close, seeds=100),
            }

        out_dir = ROOT / "logs" / "backtest" / symbol if args.save_csv else None
        performance.report(result, benchmarks=benchmarks, out_dir=out_dir)

        if args.stress_test:
            print("\n" + "=" * 74)
            print(f"STRESS TESTS — {symbol}  (this can take a few minutes)")
            print("=" * 74)
            crash = stress_test.crash_injection(df, bt, symbol, n_sims=args.stress_sims)
            gaps = stress_test.gap_risk(df, bt, symbol, n_sims=args.stress_sims)
            mis = stress_test.regime_misclassification(df, bt, symbol, n_sims=max(10, args.stress_sims // 5))
            for res in (crash, gaps, mis):
                print(f"\n  {res}")


class MockBroker:
    """Simulated broker + tick feed for --dry-run mode. Sends NO real orders."""

    name = "MockBroker"

    def __init__(self, seed: int = 7, start_equity: float = 100000.0):
        import random

        self._rng = random.Random(seed)
        self.start_equity = start_equity
        self.equity = start_equity
        self.regime = "BULL"
        self.risk_on = True
        self.stability = 1
        self.peak_dd = 0.0
        self._prev_regime = "BULL"

    def next_tick(self):
        """Advance one simulated tick; return (DashboardState, regime_shift|None)."""
        from monitoring.dashboard import DashboardState, Position

        drift = self._rng.uniform(-0.004, 0.006)
        self.equity *= (1.0 + drift)
        self.stability += 1
        daily_pnl = self.equity - self.start_equity
        daily_dd = max(0.0, -min(0.0, drift) * 3.0)
        self.peak_dd = self.peak_dd * 0.8 + max(0.0, -min(0.0, drift))

        shift = None
        if self._rng.random() < 0.15:  # occasional regime flip
            new = "BEAR" if self.regime == "BULL" else "BULL"
            self.regime, self.risk_on, self.stability = new, new == "BULL", 1
            if new != self._prev_regime:
                shift = (self._prev_regime, new)
                self._prev_regime = new

        if self.risk_on:
            pnl_pct = round((self.equity / self.start_equity - 1.0) * 100.0, 1)
            positions = [Position("SOXL", "LONG", 45.20, pnl_pct, 38.00)]
            leverage, alloc = 2.5, 250.0
        else:  # RISK OFF -> flatten to cash
            positions, leverage, alloc = [], 0.0, 0.0

        state = DashboardState(
            regime_label=self.regime, risk_on=self.risk_on, stability_bars=self.stability,
            vol_level="Low" if self.risk_on else "High",
            equity=self.equity, daily_pnl=daily_pnl, daily_pnl_pct=daily_pnl / 1000.0,
            allocation_pct=alloc, leverage=leverage, positions=positions,
            daily_dd=daily_dd, peak_dd=self.peak_dd,
        )
        return state, shift


def cmd_live(args: argparse.Namespace) -> None:
    """Launch the rich monitoring dashboard.

    --dry-run initializes a MockBroker with a simulated tick feed so the dashboard
    animates immediately, with no broker connection and no real orders. Without
    --dry-run we refuse to start: 01_CLAUDE.md rule 4 forbids defaulting to live
    trading, and no live broker is wired in this environment.
    """
    import time

    from rich.live import Live

    from monitoring.alerts import AlertManager
    from monitoring.dashboard import render_dashboard
    from monitoring.logger import get_logger, log_state

    if not args.dry_run:
        print("Refusing to start LIVE trading: no broker is configured and live mode requires")
        print("explicit confirmation (01_CLAUDE.md rule 4 — never default to live). Launch the")
        print("simulator instead:\n    python main.py live --dry-run")
        return

    if getattr(args, "multi_strat", False):
        run_multistrat_live(args)
        return

    trade_log = get_logger("trading")
    alerts = AlertManager()
    broker = MockBroker()
    print(f"[dry-run] {broker.name} initialized with simulated tick feed. No real orders will be sent.\n")

    frames, i = args.frames, 0
    state, _ = broker.next_tick()
    with Live(render_dashboard(state), refresh_per_second=8, screen=False) as live:
        while frames == 0 or i < frames:
            i += 1
            state, shift = broker.next_tick()
            if shift is not None:
                alerts.regime_shift(*shift)
            log_state(
                trade_log, regime=state.regime_label, probability=0.70,
                equity=state.equity, positions=[p.__dict__ for p in state.positions],
                daily_pnl=state.daily_pnl,
            )
            live.update(render_dashboard(state))
            if frames == 0 or i < frames:
                time.sleep(args.refresh)

    print(f"\n[dry-run] Dashboard ended after {i} frames. Structured logs -> logs/trading.jsonl")


def run_multistrat_live(args: argparse.Namespace) -> None:
    """Multi-strategy dry-run: registry -> per-strategy risk -> portfolio risk -> executor.

    Wires the REAL risk architecture with a mock feed + mock executor. No broker,
    no real orders. Portfolio risk can be disabled ONLY for debugging (--no-portfolio-risk).
    """
    import time

    from rich.live import Live

    from core.capital_allocator import AllocatorConfig, CapitalAllocator
    from core.registered_strategies import apply_config, register_all
    from core.strategy_registry import StrategyRegistry
    from execution.multistrat_engine import (
        SimulatedFeed,
        build_live_engine,
        simulated_signal_source,
    )
    from monitoring.dashboard import render_dashboard

    # 1. Load + register enabled strategies from settings.yaml
    registry = StrategyRegistry()
    register_all(registry)
    apply_config(registry)

    # optional --strategies override (comma-separated strategy names)
    if args.strategies:
        wanted = {s.strip() for s in args.strategies.replace(",", " ").split() if s.strip()}
        unknown = wanted - set(registry.all())
        if unknown:
            print(f"  Ignoring unknown strategies: {sorted(unknown)}")
        for name, strat in registry.all().items():
            (strat.on_enable if name in wanted else strat.on_disable)()

    active = list(registry.active())
    if len(active) < 2:
        print("Multi-strat live needs >=2 enabled strategies. "
              "Enable more in config/settings.yaml or via --strategies.")
        return

    # 2. Capital allocator (approach override optional)
    cfg = AllocatorConfig.from_settings()
    if args.allocator:
        cfg.approach = args.allocator
    allocator = CapitalAllocator(registry, cfg)

    # 3. Portfolio risk layer (debug bypass is loud + refused implicitly in prod)
    use_pr = not args.no_portfolio_risk
    if not use_pr:
        print("!" * 74)
        print("! WARNING: PORTFOLIO RISK LAYER DISABLED (--no-portfolio-risk). DEBUG ONLY.")
        print("! This removes aggregate exposure / leverage / DD / correlation vetoes.")
        print("! NEVER run this configuration against real capital.")
        print("!" * 74)

    engine = build_live_engine(registry, allocator, use_portfolio_risk=use_pr,
                               signal_source=simulated_signal_source)

    symbols = {}
    for name in active:
        for sym in registry.get(name).symbols:
            symbols.setdefault(sym, 100.0)
    feed = SimulatedFeed(symbols or {"SPY": 100.0})

    print(f"[dry-run] Multi-strat engine: {len(active)} strategies "
          f"({', '.join(active)}), allocator={cfg.approach}, "
          f"portfolio_risk={'ON' if use_pr else 'OFF'}. No real orders will be sent.\n")

    engine.initialize(feed._t)

    frames, i = args.frames, 0
    ctx = feed.next_bar()
    engine.on_bar(ctx)
    with Live(render_dashboard(engine.build_dashboard_state(ctx)), refresh_per_second=8, screen=False) as live:
        while frames == 0 or i < frames:
            i += 1
            ctx = feed.next_bar()
            records = engine.on_bar(ctx)
            submitted = sum(1 for r in records if r.approved)
            engine.apply_pnl(engine.equity * feed._rng.uniform(-0.004, 0.006))
            live.update(render_dashboard(engine.build_dashboard_state(ctx)))
            if frames == 0 or i < frames:
                time.sleep(args.refresh)

    print(f"\n[dry-run] Multi-strat dashboard ended after {i} frames. "
          f"Orders submitted: {len(engine.executor.submitted)}. Logs -> logs/trading.jsonl")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="regime-trader CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="Run the allocation walk-forward backtester")
    bt.add_argument("--symbols", nargs="+", default=["SPY"])
    bt.add_argument("--start", default=None)
    bt.add_argument("--end", default=None)
    bt.add_argument("--compare", action="store_true", help="Add benchmark comparisons")
    bt.add_argument("--stress-test", dest="stress_test", action="store_true", help="Run Monte Carlo stress tests")
    bt.add_argument("--stress-sims", type=int, default=100)
    bt.add_argument("--train-window", dest="train_window", type=int, default=252)
    bt.add_argument("--test-window", dest="test_window", type=int, default=126)
    bt.add_argument("--step-size", dest="step_size", type=int, default=126)
    bt.add_argument("--slippage", type=float, default=0.0005)
    bt.add_argument("--n-init", dest="n_init", type=int, default=4)
    bt.add_argument("--save-csv", dest="save_csv", action="store_true")
    bt.add_argument("--multi-strat", dest="multi_strat", action="store_true",
                    help="Run all enabled registered strategies together through the capital allocator")
    bt.set_defaults(func=cmd_backtest)

    live = sub.add_parser("live", help="Launch the live monitoring dashboard (paper/demo feed)")
    live.add_argument("--dry-run", action="store_true",
                      help="Run in simulation mode without broker connection")
    live.add_argument("--frames", type=int, default=0, help="0 = run until Ctrl+C")
    live.add_argument("--refresh", type=float, default=1.0, help="Seconds between refreshes")
    live.add_argument("--multi-strat", dest="multi_strat", action="store_true",
                      help="Run the multi-strategy engine (registry + allocator + portfolio risk)")
    live.add_argument("--strategies", default=None,
                      help="Comma-separated strategy names to enable (overrides settings.yaml)")
    live.add_argument("--allocator", default=None,
                      help="Override allocator approach (equal_weight|inverse_vol|risk_parity|performance_weighted)")
    live.add_argument("--no-portfolio-risk", dest="no_portfolio_risk", action="store_true",
                      help="DEBUG ONLY: disable the portfolio risk layer. NEVER use in production.")
    live.set_defaults(func=cmd_live)
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
