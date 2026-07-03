from __future__ import annotations

import backtrader as bt


class BaselineEMARSI(bt.Strategy):
    params = (
        ("fast", 10),
        ("slow", 30),
        ("rsi_period", 14),
        ("rsi_overbought", 70),
        ("rsi_oversold", 30),
        ("macd_fast", 12),
        ("macd_slow", 26),
        ("macd_signal", 9),
    )

    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(self.data.close, period_me1=self.p.macd_fast, period_me2=self.p.macd_slow, period_signal=self.p.macd_signal)
        self.order = None
        self.entry_signal = False
        self.exit_signal = False

    def next(self):
        if self.order:
            return

        if len(self) < max(self.p.slow, self.p.rsi_period, self.p.macd_slow):
            return

        bullish = self.ema_fast[0] > self.ema_slow[0] and self.ema_fast[-1] <= self.ema_slow[-1]
        bearish = self.ema_fast[0] < self.ema_slow[0] and self.ema_fast[-1] >= self.ema_slow[-1]
        rsi_ok_buy = self.rsi[0] < self.p.rsi_overbought and self.rsi[0] > self.p.rsi_oversold
        rsi_ok_sell = self.rsi[0] > self.p.rsi_oversold and self.rsi[0] < self.p.rsi_overbought
        macd_ok_buy = self.macd.macd[0] > self.macd.signal[0]
        macd_ok_sell = self.macd.macd[0] < self.macd.signal[0]

        if self.position.size <= 0 and bullish and rsi_ok_buy and macd_ok_buy:
            self.order = self.buy(size=1)
            self.entry_signal = True
            self.exit_signal = False
        elif self.position.size > 0 and bearish and rsi_ok_sell and macd_ok_sell:
            self.order = self.sell(size=self.position.size)
            self.exit_signal = True
            self.entry_signal = False
