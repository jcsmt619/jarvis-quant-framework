from __future__ import annotations

import backtrader as bt


class ChallengerFastRSI(bt.Strategy):
    params = (
        ("fast", 5),
        ("slow", 20),
        ("rsi_period", 10),
        ("rsi_overbought", 75),
        ("rsi_oversold", 25),
        ("macd_fast", 8),
        ("macd_slow", 17),
        ("macd_signal", 9),
    )

    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(self.data.close, period_me1=self.p.macd_fast, period_me2=self.p.macd_slow, period_signal=self.p.macd_signal)
        self.order = None

    def next(self):
        if self.order or len(self) < 40:
            return
        bullish = self.ema_fast[0] > self.ema_slow[0] and self.ema_fast[-1] <= self.ema_slow[-1]
        bearish = self.ema_fast[0] < self.ema_slow[0] and self.ema_fast[-1] >= self.ema_slow[-1]
        if self.position.size <= 0 and bullish and self.rsi[0] < self.p.rsi_overbought and self.rsi[0] > self.p.rsi_oversold and self.macd.macd[0] > self.macd.signal[0]:
            self.order = self.buy(size=1)
        elif self.position.size > 0 and bearish and self.rsi[0] > self.p.rsi_oversold and self.rsi[0] < self.p.rsi_overbought and self.macd.macd[0] < self.macd.signal[0]:
            self.order = self.sell(size=self.position.size)


class ChallengerMomentum(bt.Strategy):
    params = (
        ("fast", 8),
        ("slow", 24),
        ("rsi_period", 14),
        ("rsi_overbought", 70),
        ("rsi_oversold", 30),
        ("macd_fast", 10),
        ("macd_slow", 20),
        ("macd_signal", 9),
    )

    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(self.data.close, period_me1=self.p.macd_fast, period_me2=self.p.macd_slow, period_signal=self.p.macd_signal)
        self.order = None

    def next(self):
        if self.order or len(self) < 40:
            return
        bullish = self.ema_fast[0] > self.ema_slow[0] and self.ema_fast[-1] <= self.ema_slow[-1]
        bearish = self.ema_fast[0] < self.ema_slow[0] and self.ema_fast[-1] >= self.ema_slow[-1]
        if self.position.size <= 0 and bullish and self.rsi[0] < 65 and self.macd.macd[0] > self.macd.signal[0]:
            self.order = self.buy(size=1)
        elif self.position.size > 0 and bearish and self.rsi[0] > 35 and self.macd.macd[0] < self.macd.signal[0]:
            self.order = self.sell(size=self.position.size)


class ChallengerVolatility(bt.Strategy):
    params = (
        ("fast", 12),
        ("slow", 40),
        ("rsi_period", 14),
        ("rsi_overbought", 65),
        ("rsi_oversold", 35),
        ("macd_fast", 12),
        ("macd_slow", 26),
        ("macd_signal", 9),
    )

    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.volty = bt.indicators.ROC(self.data.close, period=10)
        self.macd = bt.indicators.MACD(self.data.close, period_me1=self.p.macd_fast, period_me2=self.p.macd_slow, period_signal=self.p.macd_signal)
        self.order = None

    def next(self):
        if self.order or len(self) < 40:
            return
        bullish = self.ema_fast[0] > self.ema_slow[0] and self.ema_fast[-1] <= self.ema_slow[-1]
        bearish = self.ema_fast[0] < self.ema_slow[0] and self.ema_fast[-1] >= self.ema_slow[-1]
        if self.position.size <= 0 and bullish and self.rsi[0] < self.p.rsi_overbought and self.rsi[0] > self.p.rsi_oversold and self.volty[0] > 0 and self.macd.macd[0] > self.macd.signal[0]:
            self.order = self.buy(size=1)
        elif self.position.size > 0 and bearish and self.rsi[0] > self.p.rsi_oversold and self.rsi[0] < self.p.rsi_overbought and self.volty[0] < 0 and self.macd.macd[0] < self.macd.signal[0]:
            self.order = self.sell(size=self.position.size)
