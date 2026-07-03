from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import backtrader as bt
import pandas as pd

from backtest_harness import MultiAssetBacktest


class ParamGridSearcher:
    def __init__(self):
        self.param_sets = []
        self._build_grid()

    def _build_grid(self):
        fast_slow_pairs = [(5, 20), (8, 24), (10, 30), (12, 40), (15, 45)]
        rsi_levels = [(20, 80), (25, 75), (30, 70)]
        macd_pairs = [(8, 17, 9), (10, 20, 9), (12, 26, 9)]
        for fast, slow in fast_slow_pairs:
            for rsi_low, rsi_high in rsi_levels:
                for macd_fast, macd_slow, macd_signal in macd_pairs:
                    self.param_sets.append({
                        "fast": fast,
                        "slow": slow,
                        "rsi_period": 14,
                        "rsi_overbought": rsi_high,
                        "rsi_oversold": rsi_low,
                        "macd_fast": macd_fast,
                        "macd_slow": macd_slow,
                        "macd_signal": macd_signal,
                    })

    def run(self):
        results = []
        for params in self.param_sets:
            strategy = self._make_strategy(params)
            try:
                total_return, max_drawdown, sharpe_ratio = MultiAssetBacktest(["SPY", "BTC-USD", "TLT"], "raw").run()
            except Exception:
                continue
            profit_factor = self._estimate_profit_factor(total_return, max_drawdown, sharpe_ratio)
            results.append((profit_factor, sharpe_ratio, total_return, max_drawdown, params))
        results.sort(reverse=True)
        return results[:10]

    def _estimate_profit_factor(self, total_return, max_drawdown, sharpe_ratio):
        if max_drawdown == 0:
            return total_return * 1000
        return (total_return + 1) / max(abs(max_drawdown), 1e-6) * max(sharpe_ratio, 1e-6)

    def _make_strategy(self, params):
        return params


if __name__ == "__main__":
    searcher = ParamGridSearcher()
    results = searcher.run()
    print("Top parameter variations")
    for rank, (profit_factor, sharpe_ratio, total_return, max_drawdown, params) in enumerate(results, start=1):
        print(rank, params, "profit_factor_estimate", round(profit_factor, 4), "sharpe", round(sharpe_ratio, 4), "return", round(total_return, 4), "dd", round(max_drawdown, 4))
