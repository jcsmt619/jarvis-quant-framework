import backtrader as bt
import pandas as pd
from pathlib import Path

csv = Path(r'data/raw/spy.csv')
df = pd.read_csv(csv, parse_dates=['date'])
df = df[['date','Open','High','Low','Close','Volume']].dropna().sort_values('date').reset_index(drop=True)
print(df.head())

class PandasData(bt.feeds.PandasData):
    params = (
        ('datetime', 'date'),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', None),
    )

class S(bt.Strategy):
    params = dict(fast=10, slow=30, rsi_period=14, rsi_overbought=70, rsi_oversold=30)
    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
    def next(self):
        if len(self) < 40:
            return
        print(self.data.datetime.date(0), 'close', self.data.close[0], 'ema_fast', self.ema_fast[0], 'ema_slow', self.ema_slow[0], 'rsi', self.rsi[0], 'pos', self.position.size)
        if self.ema_fast[0] > self.ema_slow[0] and self.rsi[0] < self.p.rsi_overbought:
            if self.position.size <= 0:
                self.buy(size=1)
                print('BUY')
        elif self.ema_fast[0] < self.ema_slow[0] and self.rsi[0] > self.p.rsi_oversold:
            if self.position.size > 0:
                self.sell(size=self.position.size)
                print('SELL')

cerebro = bt.Cerebro()
cerebro.addstrategy(S)
cerebro.broker.set_cash(100000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.adddata(PandasData(dataname=df))
res = cerebro.run()
print('complete')
