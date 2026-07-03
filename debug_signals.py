#!/usr/bin/env python3
"""Debug strategy signal generation"""
import sys
from pathlib import Path
import pandas as pd
import backtrader as bt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data" / "raw"

# Load SPY data
df = pd.read_csv(DATA_DIR / "spy.csv", parse_dates=["date"])
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")
df.columns = [col.lower() for col in df.columns]
df = df[["open", "high", "low", "close", "volume"]].sort_index()

print(f"Data shape: {df.shape}")
print(f"Date range: {df.index.min()} to {df.index.max()}")
print(f"First few rows:\n{df.head()}\n")

# Create a simple test strategy
class DebugStrategy(bt.Strategy):
    def __init__(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(self.data.close, period=10)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(self.data.close, period=30)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=14)
        self.order = None
        self.trades = []
        
    def next(self):
        if len(self) < 40:
            return
        
        ema_fast = self.ema_fast[0]
        ema_slow = self.ema_slow[0]
        ema_fast_prev = self.ema_fast[-1]
        ema_slow_prev = self.ema_slow[-1]
        rsi = self.rsi[0]
        close = self.data.close[0]
        date = self.data.datetime.date(0)
        
        # Check conditions
        bullish_crossover = ema_fast > ema_slow and ema_fast_prev <= ema_slow_prev
        bearish_crossover = ema_fast < ema_slow and ema_fast_prev >= ema_slow_prev
        rsi_in_range = rsi < 70 and rsi > 30
        
        if bullish_crossover:
            print(f"[{date}] Bullish crossover detected!")
            print(f"  EMA_fast: {ema_fast:.2f}, EMA_slow: {ema_slow:.2f}")
            print(f"  RSI: {rsi:.2f} (in range: {rsi < 70})")
            print(f"  Position size before: {self.position.size}")
            
            if self.position.size <= 0 and rsi < 70:
                self.order = self.buy(size=1)
                print(f"  → BUY order placed")
                self.trades.append(("BUY", date, close))
        
        elif bearish_crossover:
            print(f"[{date}] Bearish crossover detected!")
            print(f"  EMA_fast: {ema_fast:.2f}, EMA_slow: {ema_slow:.2f}")
            print(f"  RSI: {rsi:.2f} (in range: {rsi > 30})")
            print(f"  Position size before: {self.position.size}")
            
            if self.position.size > 0 and rsi > 30:
                self.order = self.sell(size=self.position.size)
                print(f"  → SELL order placed")
                self.trades.append(("SELL", date, close))
    
    def stop(self):
        print(f"\n\nTOTAL TRADES: {len(self.trades)}")
        for trade in self.trades:
            print(f"  {trade}")

# Run backtest
cerebro = bt.Cerebro()
cerebro.addstrategy(DebugStrategy)
cerebro.broker.set_cash(100000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.adddata(bt.feeds.PandasData(dataname=df, name="SPY"))

print("="*80)
print("RUNNING BACKTEST WITH DEBUG OUTPUT")
print("="*80 + "\n")

results = cerebro.run()

print("\n" + "="*80)
print("BACKTEST COMPLETE")
print("="*80)
