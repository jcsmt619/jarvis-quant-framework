from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import backtrader as bt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_ROOT = ROOT / "data"
RAW_DIR = DATA_ROOT / "raw"
INTRADAY_DIR = DATA_ROOT / "intraday"
# Backtest-scoped lock so a simulated hard-halt never blocks a real kill switch.
BACKTEST_LOCK = ROOT / "logs" / "backtest_trading_halted.lock"

from core.risk_manager import RiskLimits, RiskManager

INTRADAY_STEMS = {"SOXL": "soxl_60m", "TQQQ": "tqqq_60m", "ETH-USD": "eth_usd_60m", "BTC-USD": "btc_usd_60m"}

# ---------------------------------------------------------------------------
# Asset-class routing. Each engine runs ONLY on the assets it was designed for,
# and each asset can carry its own params + timeframe.
#   - Mean Reversion (RSI-2)   : SPY daily, long-only dip buying.
#   - Bond Regime (TLT invert) : TLT daily with allow_short=True -> below the
#     200-SMA it shorts the bounce instead of buying dips (or sits in cash).
#   - Crypto Momentum          : BTC-USD daily breakout.
#   - Intraday LETF Momentum   : SOXL, TQQQ on 60m bars with faster breakout
#     params tuned for 3x high-beta intraday trend acceleration.
# ---------------------------------------------------------------------------
ENGINES: dict[str, dict] = {
    "mean_reversion": {
        "label": "Mean Reversion (RSI-2)",
        "strategy": "strategies.skool_variant_1.SkoolVariant1",
        "assets": [
            {"symbol": "SPY", "timeframe": "daily", "params": {"allow_short": False}},
        ],
    },
    "bond_regime": {
        "label": "Bond Regime (TLT invert)",
        "strategy": "strategies.skool_variant_1.SkoolVariant1",
        "assets": [
            {"symbol": "TLT", "timeframe": "daily", "params": {"allow_short": True}},
        ],
    },
    "crypto_momentum": {
        "label": "Crypto Momentum (HyperAlpha)",
        "strategy": "strategies.hyper_alpha_kelly.HyperAlphaKelly",
        "assets": [
            {"symbol": "BTC-USD", "timeframe": "daily", "params": {}},
        ],
    },
    "intraday_momentum": {
        "label": "Intraday LETF Momentum",
        "strategy": "strategies.hyper_alpha_kelly.HyperAlphaKelly",
        "assets": [
            {"symbol": "SOXL", "timeframe": "intraday",
             "params": {"breakout_period": 10, "momentum_period": 4, "trend_ema": 24, "atr_period": 14}},
            {"symbol": "TQQQ", "timeframe": "intraday",
             "params": {"breakout_period": 10, "momentum_period": 4, "trend_ema": 24, "atr_period": 14}},
        ],
    },
    # STEP 5: aggressive full-Kelly / up-to-4x breakout engine guarded by the
    # RiskManager circuit breakers. Concentrated on BTC-USD + 3x LETFs only.
    "kelly_hypervelocity": {
        "label": "Kelly Hyper-Velocity (4x LETF)",
        "simulator": "kelly_hypervelocity",
        "assets": [
            {"symbol": "BTC-USD", "timeframe": "daily",
             "params": {"breakout_period": 20, "momentum_period": 10, "trend_ema": 50}},
            {"symbol": "SOXL", "timeframe": "intraday",
             "params": {"breakout_period": 10, "momentum_period": 4, "trend_ema": 24}},
            {"symbol": "TQQQ", "timeframe": "intraday",
             "params": {"breakout_period": 10, "momentum_period": 4, "trend_ema": 24}},
        ],
    },
    # STEP 3: volatility-ranked regime ALLOCATION blueprint (drawdown control).
    # Walk-forward HMM -> StrategyOrchestrator -> allocation + mandatory ATR stop.
    "regime_allocation": {
        "label": "Regime Allocation (STEP 3)",
        "simulator": "regime_allocation",
        "assets": [
            {"symbol": "SPY", "timeframe": "daily"},
            {"symbol": "BTC-USD", "timeframe": "daily"},
            {"symbol": "TLT", "timeframe": "daily"},
            {"symbol": "SOXL", "timeframe": "daily"},
            {"symbol": "TQQQ", "timeframe": "daily"},
        ],
    },
}


class PandasData(bt.feeds.PandasData):
    params = (
        ("datetime", "date"),
        ("open", "Open"),
        ("high", "High"),
        ("low", "Low"),
        ("close", "Close"),
        ("volume", "Volume"),
        ("openinterest", None),
    )


def resolve_data_file(symbol: str, dataset_type: str = "raw", timeframe: str = "daily") -> Path:
    """Locate the exact data file, preferring parquet over csv."""
    if timeframe == "intraday":
        stem = INTRADAY_STEMS.get(symbol, symbol.lower().replace("-", "_") + "_60m")
        directory = INTRADAY_DIR
    else:
        stem = symbol.lower().replace("-", "_").replace("/", "_")
        suffix = "" if dataset_type == "raw" else "_stress"
        stem = f"{stem}{suffix}"
        directory = RAW_DIR
    for ext in (".parquet", ".csv"):
        candidate = directory / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No data file for '{symbol}' ({timeframe}/{dataset_type}) under {directory}")


def load_symbol_frame(symbol: str, dataset_type: str = "raw", timeframe: str = "daily") -> pd.DataFrame:
    path = resolve_data_file(symbol, dataset_type, timeframe)
    if path.suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path, parse_dates=["date"])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[["date", "Open", "High", "Low", "Close", "Volume"]].copy()
    frame = frame.sort_values("date").dropna().reset_index(drop=True)
    return frame


def _load_strategy(dotted_path: str):
    module_name, class_name = dotted_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_name), class_name)


def backtest_symbol(
    symbol: str,
    strategy_cls,
    params: dict | None = None,
    dataset_type: str = "raw",
    timeframe: str = "daily",
    cash: float = 100000.0,
) -> tuple[float, float, float]:
    """Run a single symbol in its own cerebro (correct for single-data strategies)."""
    frame = load_symbol_frame(symbol, dataset_type, timeframe)
    intraday = timeframe == "intraday"

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(strategy_cls, **(params or {}))
    cerebro.broker.set_cash(cash)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.001 if intraday else 0.0005)
    cerebro.adddata(PandasData(dataname=frame, name=symbol))

    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        timeframe=bt.TimeFrame.Days, annualize=True, riskfreerate=0.045)

    result = cerebro.run()[0]
    total_return = float(result.analyzers.returns.get_analysis().get("rtot", 0.0) or 0.0)
    max_dd = float(result.analyzers.drawdown.get_analysis().get("max", {}).get("drawdown", 0.0) or 0.0) / 100.0
    sharpe_raw = result.analyzers.sharpe.get_analysis().get("sharperatio", 0.0)
    sharpe = float(sharpe_raw) if sharpe_raw is not None and not pd.isna(sharpe_raw) else 0.0
    return total_return, max_dd, sharpe


class MultiAssetBacktest:
    """Backward-compatible wrapper: runs each daily symbol independently and averages."""

    def __init__(self, symbols, dataset_type="raw",
                 strategy_class="strategies.baseline_ema_rsi.BaselineEMARSI", params=None):
        self.symbols = symbols
        self.dataset_type = dataset_type
        self.strategy_class = strategy_class
        self.params = params or {}

    def run(self) -> tuple[float, float, float]:
        if not self.symbols:
            raise ValueError("At least one symbol is required")
        strategy_cls = _load_strategy(self.strategy_class)
        rets, dds, sharpes = [], [], []
        for symbol in self.symbols:
            r, dd, s = backtest_symbol(symbol, strategy_cls, self.params, self.dataset_type, "daily")
            rets.append(r)
            dds.append(dd)
            sharpes.append(s)
        n = len(self.symbols)
        return sum(rets) / n, sum(dds) / n, sum(sharpes) / n


def _np_sharpe(daily_returns: np.ndarray, rf: float = 0.045) -> float:
    arr = np.asarray([r for r in np.asarray(daily_returns, dtype=float) if r == r])
    if arr.size < 2 or arr.std(ddof=1) == 0:
        return 0.0
    return float((arr.mean() - rf / 252.0) / arr.std(ddof=1) * np.sqrt(252.0))


def simulate_kelly_hypervelocity(
    symbol: str,
    timeframe: str = "daily",
    breakout_period: int = 20,
    momentum_period: int = 10,
    trend_ema: int = 50,
    initial_capital: float = 100000.0,
    slippage: float | None = None,
    limits: RiskLimits | None = None,
    lock_file: Path | None = None,
    regime_gate: bool = True,
) -> dict:
    """
    RiskManager-driven full-Kelly / up-to-4x breakout simulator (STEP 5).

    Signal: causal Donchian breakout + positive ROC + price above the trend EMA
    ("breakout accelerating") unlocks leverage up to the RiskManager's hard cap;
    otherwise sizing stays at the Kelly concentration cap. Circuit breakers cut
    or flatten exposure, and a >25% peak drawdown writes the hard-halt lock.
    Leverage is honestly modelled: cash goes negative (margin) and equity can be
    wiped out (ruin), which is exactly the risk this configuration carries.
    """
    frame = load_symbol_frame(symbol, "raw", timeframe)
    frame = frame.set_index("date")
    frame.columns = [c.lower() for c in frame.columns]
    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    index = frame.index
    intraday = timeframe == "intraday"
    slip = slippage if slippage is not None else (0.001 if intraday else 0.0005)
    n = len(close)

    zero = {"total_return": 0.0, "max_dd": 0.0, "sharpe": 0.0, "ruined": False,
            "lock_triggered": False, "bars": n, "final_equity": initial_capital}
    if n < breakout_period + momentum_period + 5:
        return zero

    donch = pd.Series(high).rolling(breakout_period).max().shift(1).to_numpy()
    roc = pd.Series(close).pct_change(momentum_period).to_numpy()
    ema = pd.Series(close).ewm(span=trend_ema, adjust=False).mean().to_numpy()

    # MACRO SENSOR: query the HMM regime gate BEFORE any leverage is allocated.
    # gate == 0 -> High-Vol Chop/Bear (or ambiguous) -> force cash.
    # gate == 1 -> Calm/Trending-Bull -> unlock aggressive Kelly scaling.
    if regime_gate:
        try:
            from utils.hmm_regime import HMMRegimeSensor
            gate_series = HMMRegimeSensor().compute_gate_series(frame)
            gate_arr = gate_series.reindex(index).fillna(0.0).to_numpy()
        except Exception:
            gate_arr = np.ones(n)
    else:
        gate_arr = np.ones(n)

    rm = RiskManager(limits or RiskLimits.from_settings(), initial_capital, lock_file=lock_file or BACKTEST_LOCK)
    rm.clear_lock()

    cash = float(initial_capital)
    shares = 0
    equity_curve = np.empty(n)
    seg_entry: float | None = None
    ruined = False

    for t in range(n):
        price = close[t]
        equity = cash + shares * price
        if equity <= 0 and not ruined:
            ruined = True
        action = rm.update(index[t], equity if equity > 0 else 0.0)
        mult = rm.size_multiplier(action)

        if rm.hard_halted or ruined:
            target = 0.0
        elif np.isnan(donch[t]) or np.isnan(ema[t]) or np.isnan(roc[t]):
            target = 0.0
        else:
            accelerating = (price > donch[t]) and (roc[t] > 0) and (price > ema[t])
            # HMM macro gate has veto power: risk-off => cash regardless of signal.
            target = rm.target_leverage(accelerating) * mult * gate_arr[t]

        target_shares = int(equity * target / price) if (price > 0 and equity > 0) else 0
        delta = target_shares - shares
        if delta != 0:
            if shares > 0 and target_shares < shares and seg_entry is not None:
                rm.record_trade_pnl((shares - target_shares) * (price - seg_entry))
            sign = 1 if delta > 0 else -1
            fill = price * (1 + slip * sign)
            cash -= delta * fill
            if shares == 0 or target_shares > shares:
                seg_entry = price
            shares = target_shares
            if shares == 0:
                seg_entry = None
        equity_curve[t] = cash + shares * price

    curve = np.maximum(equity_curve, 0.0)  # floor at ruin for reporting
    total = float(curve[-1] / initial_capital - 1.0)
    peak = np.maximum.accumulate(curve)
    dd_series = np.where(peak > 0, (curve - peak) / peak, 0.0)
    max_dd = float(dd_series.min()) if dd_series.size else 0.0

    series = pd.Series(curve, index=index)
    if intraday:
        daily = series.resample("1D").last().dropna().pct_change().dropna().to_numpy()
    else:
        daily = np.diff(curve) / np.where(curve[:-1] > 0, curve[:-1], np.nan)
    sharpe = _np_sharpe(daily)

    lock_triggered = rm.lock_file.exists()
    rm.clear_lock()  # never leave a backtest lock that would block real runs
    return {"total_return": total, "max_dd": max_dd, "sharpe": sharpe,
            "ruined": bool(ruined or curve[-1] <= 1e-6), "lock_triggered": bool(lock_triggered),
            "bars": n, "final_equity": float(equity_curve[-1])}


def simulate_regime_allocation(symbol: str, timeframe: str = "daily", n_init: int = 3) -> dict:
    """STEP 3 regime-allocation backtest via the orchestrator-driven walk-forward engine."""
    from backtest.backtester import WalkForwardBacktester
    from backtest.performance import compute_metrics

    frame = load_symbol_frame(symbol, "raw", timeframe).set_index("date")
    frame.columns = [c.lower() for c in frame.columns]
    result = WalkForwardBacktester(n_init=n_init).run(frame, symbol=symbol)
    m = compute_metrics(result.equity, result.returns, result.trades)
    return {"total_return": m["total_return"], "max_dd": m["max_drawdown"], "sharpe": m["sharpe"]}


def run_engine(engine_key: str, dataset_type: str = "raw") -> list[dict]:
    engine = ENGINES[engine_key]
    rows = []
    if engine.get("simulator") == "kelly_hypervelocity":
        for asset in engine["assets"]:
            res = simulate_kelly_hypervelocity(
                asset["symbol"], asset.get("timeframe", "daily"), **asset.get("params", {}))
            rows.append({
                "engine": engine["label"], "symbol": asset["symbol"],
                "tf": asset.get("timeframe", "daily"),
                "ret": res["total_return"], "dd": res["max_dd"], "sharpe": res["sharpe"],
            })
        return rows
    if engine.get("simulator") == "regime_allocation":
        for asset in engine["assets"]:
            res = simulate_regime_allocation(asset["symbol"], asset.get("timeframe", "daily"))
            rows.append({
                "engine": engine["label"], "symbol": asset["symbol"],
                "tf": asset.get("timeframe", "daily"),
                "ret": res["total_return"], "dd": res["max_dd"], "sharpe": res["sharpe"],
            })
        return rows
    strategy_cls = _load_strategy(engine["strategy"])
    for asset in engine["assets"]:
        r, dd, s = backtest_symbol(
            asset["symbol"], strategy_cls, asset.get("params", {}),
            dataset_type, asset.get("timeframe", "daily"),
        )
        rows.append({
            "engine": engine["label"], "symbol": asset["symbol"],
            "tf": asset.get("timeframe", "daily"), "ret": r, "dd": dd, "sharpe": s,
        })
    return rows


def _print_table(rows: list[dict]) -> None:
    print("=" * 82)
    print("{:<30}{:<9}{:<7}{:>10}{:>9}{:>10}".format("ENGINE", "SYMBOL", "TF", "TotalRet", "MaxDD", "Sharpe"))
    print("-" * 82)
    for row in rows:
        print("{:<30}{:<9}{:<7}{:>9.2%}{:>8.2%}{:>10.3f}".format(
            row["engine"][:29], row["symbol"], row["tf"][:6], row["ret"], row["dd"], row["sharpe"]))
    print("=" * 82)


def main() -> None:
    parser = argparse.ArgumentParser(description="Asset-class-routed backtest harness")
    parser.add_argument("--engine", default="all", choices=[*ENGINES.keys(), "all"])
    parser.add_argument("--dataset", default="raw", choices=["raw", "stress"])
    parser.add_argument("--symbols", nargs="+", default=None, help="Legacy: override symbols (baseline strategy).")
    args = parser.parse_args()

    try:
        if args.symbols:
            r, dd, s = MultiAssetBacktest(args.symbols, args.dataset).run()
            print(f"Dataset: {args.dataset}")
            print(f"Symbols: {', '.join(args.symbols)}")
            print(f"Total Returns: {r:.2%}")
            print(f"Max Drawdown: {dd:.2%}")
            print(f"Sharpe Ratio: {s:.3f}")
            return

        engine_keys = list(ENGINES.keys()) if args.engine == "all" else [args.engine]
        all_rows: list[dict] = []
        for key in engine_keys:
            all_rows.extend(run_engine(key, args.dataset))
        _print_table(all_rows)
    except Exception as exc:
        print(f"Backtest failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
