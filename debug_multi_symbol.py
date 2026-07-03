#!/usr/bin/env python3
"""Debug tri-symbol backtesting"""
import sys
from pathlib import Path
import pandas as pd
import backtrader as bt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data" / "raw"

def load_data(symbol: str) -> pd.DataFrame:
    stem = symbol.lower().replace("-", "_").replace("/", "_")
    csv_path = DATA_DIR / f"{stem}.csv"
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.columns = [col.lower() for col in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].sort_index()
    return df

# Load all data
symbols = ["SPY", "BTC-USD", "TLT"]
print("Loading data...")
for symbol in symbols:
    df = load_data(symbol)
    print(f"  {symbol}: {len(df)} bars, date range: {df.index.min()} to {df.index.max()}")

# Create strategy
class DebugStrategy(bt.Strategy):
    params = (
        ("fast", 10),
        ("slow", 30),
        ("rsi_period", 14),
        ("rsi_overbought", 70),
        ("rsi_oversold", 30),
    )

    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.fast)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.slow)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.order = None
        self.trade_count = 0
        self.data0_ref = False
        
    def next(self):
        if len(self) < 40:
            return
        
        # Print which data feed we're on (for debugging)
        if not self.data0_ref and len(self) == 40:
            print(f"First 40 bars reached")
            print(f"  self.data name: {self.data._name}")
            print(f"  self.data0 name: {self.data0._name}")
            self.data0_ref = True
        
        ema_fast = self.ema_fast[0]
        ema_slow = self.ema_slow[0]
        ema_fast_prev = self.ema_fast[-1]
        ema_slow_prev = self.ema_slow[-1]
        rsi = self.rsi[0]
        
        # Confirmed bullish crossover + RSI filter
        if (ema_fast > ema_slow and 
            ema_fast_prev <= ema_slow_prev and
            rsi < self.p.rsi_overbought):
            if self.position.size <= 0 and self.order is None:
                self.order = self.buy(size=1)
                self.trade_count += 1
                if self.trade_count <= 3:
                    print(f"[Trade {self.trade_count}] BUY signal at bar {len(self)}")
        
        # Confirmed bearish crossover + RSI filter
        elif (ema_fast < ema_slow and 
              ema_fast_prev >= ema_slow_prev and
              rsi > self.p.rsi_oversold):
            if self.position.size > 0 and self.order is None:
                self.order = self.sell(size=self.position.size)
                self.trade_count += 1
                if self.trade_count <= 6:
                    print(f"[Trade {self.trade_count}] SELL signal at bar {len(self)}")
    
    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
    
    def stop(self):
        print(f"\nTotal orders: {self.trade_count}")

# Run backtest with all three feeds
print("\n" + "="*80)
print("RUNNING BACKTEST WITH ALL THREE SYMBOLS")
print("="*80 + "\n")

cerebro = bt.Cerebro()
cerebro.addstrategy(DebugStrategy)
cerebro.broker.set_cash(100000.0)
cerebro.broker.setcommission(commission=0.001)

for symbol in symbols:
    data = load_data(symbol)
    cerebro.adddata(bt.feeds.PandasData(dataname=data, name=symbol))
    print(f"Added {symbol} data feed")

cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")

results = cerebro.run()[0]

returns_analysis = results.analyzers.returns.get_analysis()
drawdown_analysis = results.analyzers.drawdown.get_analysis()
sharpe_analysis = results.analyzers.sharpe.get_analysis()

print(f"\n" + "="*80)
print("RESULTS")
print("="*80)
print(f"Total Return: {float(returns_analysis.get('rtot', 0.0)):.4f}")
print(f"Max Drawdown: {float(drawdown_analysis.get('maxdrawdown', 0.0)):.4f}")
print(f"Sharpe Ratio: {float(sharpe_analysis.get('sharperatio', 0.0)):.4f}")
