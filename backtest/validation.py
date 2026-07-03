"""
backtest/validation.py
======================
Full-history walk-forward VALIDATION across multiple symbols, parallelized with
a Windows-safe process pool. This is the honest capstone: it scores the HMM
allocation strategy on out-of-sample data against buy & hold, a 200-SMA trend
follower, and a random-allocation control, per symbol.

Windows-safe: the worker lives in this importable module (never in __main__),
so it pickles cleanly under spawn. The process pool is only ever created from a
guarded entry point (run_all.main() or a `if __name__ == '__main__'` script).
"""

from __future__ import annotations

import logging
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed


def _quiet() -> None:
    logging.getLogger("hmm_engine").setLevel(logging.ERROR)
    logging.getLogger("hmmlearn").setLevel(logging.ERROR)
    logging.getLogger("backtester").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")


def _walk_forward_worker(symbol: str, n_init: int = 3, random_seeds: int = 50) -> dict:
    """Runs one symbol's full-history walk-forward + benchmarks. Executed in a child process."""
    _quiet()
    import numpy as np

    from main import load_price_data
    from backtest.backtester import WalkForwardBacktester
    from backtest.performance import _max_drawdown, _sharpe, compute_metrics

    df = load_price_data(symbol, None, None)  # full available history
    bt = WalkForwardBacktester(n_init=n_init)
    res = bt.run(df, symbol=symbol)
    m = compute_metrics(res.equity, res.returns, res.trades)

    def _stats(eq: np.ndarray) -> tuple[float, float, float]:
        total = float(eq[-1] / eq[0] - 1.0)
        dr = np.diff(eq) / eq[:-1]
        dd, _ = _max_drawdown(eq)
        return total, _sharpe(dr), dd

    bh = _stats(bt.benchmark_buy_hold(res.close))
    sma = _stats(bt.benchmark_sma200(res.close, res.sma200))
    rnd = bt.benchmark_random(res.close, seeds=random_seeds)

    beats_bh = m["total_return"] > bh[0]
    beats_random = m["total_return"] > rnd["return_mean"]
    return {
        "symbol": symbol,
        "windows": res.n_windows,
        "start": str(res.index[0].date()),
        "end": str(res.index[-1].date()),
        "strat_ret": m["total_return"], "strat_sharpe": m["sharpe"], "strat_dd": m["max_drawdown"],
        "bh_ret": bh[0], "bh_sharpe": bh[1], "bh_dd": bh[2],
        "sma_ret": sma[0], "sma_sharpe": sma[1], "sma_dd": sma[2],
        "rand_ret_mean": rnd["return_mean"], "rand_ret_std": rnd["return_std"],
        "rand_sharpe_mean": rnd["sharpe_mean"],
        "beats_bh": beats_bh, "beats_random": beats_random,
    }


def run_walk_forward_validation(symbols: list[str], parallel: bool = True, n_init: int = 3) -> list[dict]:
    """Validate every symbol (optionally in parallel) and print a consolidated matrix."""
    results: list[dict] = []
    if parallel and len(symbols) > 1:
        with ProcessPoolExecutor(max_workers=min(len(symbols), 3)) as pool:
            futures = {pool.submit(_walk_forward_worker, s, n_init): s for s in symbols}
            for fut in as_completed(futures):
                sym = futures[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:  # pragma: no cover
                    print(f"  [validation] {sym} failed: {exc}")
    else:
        for sym in symbols:
            try:
                results.append(_walk_forward_worker(sym, n_init))
            except Exception as exc:  # pragma: no cover
                print(f"  [validation] {sym} failed: {exc}")

    results.sort(key=lambda r: r["symbol"])
    _print_matrix(results)
    return results


def _print_matrix(rows: list[dict]) -> None:
    print("\n" + "=" * 96)
    print("15-YEAR WALK-FORWARD VALIDATION MATRIX  (out-of-sample; HMM allocation vs benchmarks)")
    print("=" * 96)
    hdr = "{:<9}{:>5} {:<21}{:>10}{:>8}{:>8}   {:>9}{:>7}   {:>9}{:>7}   {}"
    print(hdr.format("SYMBOL", "WIN", "OOS PERIOD", "STRAT", "Sh", "DD",
                     "Buy&Hold", "Sh", "200SMA", "Sh", "VERDICT"))
    print("-" * 96)
    for r in rows:
        verdict = "beats B&H+rand" if (r["beats_bh"] and r["beats_random"]) else (
            "beats random" if r["beats_random"] else "no edge vs random")
        period = f"{r['start']}→{r['end']}"
        print("{:<9}{:>5} {:<21}{:>9.1%}{:>8.2f}{:>8.1%}   {:>8.1%}{:>7.2f}   {:>8.1%}{:>7.2f}   {}".format(
            r["symbol"], r["windows"], period,
            r["strat_ret"], r["strat_sharpe"], r["strat_dd"],
            r["bh_ret"], r["bh_sharpe"], r["sma_ret"], r["sma_sharpe"], verdict))
    print("-" * 96)
    print("Random control (mean±std total return): " + " | ".join(
        f"{r['symbol']} {r['rand_ret_mean']:.1%}±{r['rand_ret_std']:.1%}" for r in rows))
    print("=" * 96)
