"""
Skool Variant 1 - MR-01 RSI-2 Mean Reversion
============================================
Faithful implementation of the flagship entry (MR-01) from the AI Pathways
"Strategy Library" (Family 01 - Mean Reversion). This is Larry Connors' classic
RSI-2: buy short-term oversold *inside* a long-term uptrend, exit on the snap
back. Every rule and default below is lifted directly from the library entry.

------------------------------------------------------------------------------
EXTRACTED COURSE MECHANICS (verbatim from the PDF)
------------------------------------------------------------------------------
HOW IT WORKS
  - Only consider LONGS when close > 200-day SMA (long-term trend is up).
  - Enter LONG when the 2-period RSI drops below the oversold threshold.
  - Exit when close rises back above the 5-day SMA, OR RSI(2) > 50,
    OR a max-hold time stop, whichever comes first.
  - Long-only. Never short. Never average down.

CONFIGURATION (defaults from the library table)
  rsi_period 2     - the short RSI (2 is the classic).
  rsi_entry  10    - lower = fewer, deeper signals.
  trend_ma   200   - long-term SMA trend filter; only go long above it.
  exit_ma    5     - exit when close closes back above this 5-day SMA.
  rsi_exit   50    - alternative exit when RSI(2) rises above the midline.
  max_hold   10    - time stop so a failed signal is not bag-held.

RISK & SIZING (from the library "Risk & Sizing" box)
  - Size by percent of equity; 2% risk per trade is the stated sane default.
  - Mean reversion has a high win rate but occasional large losers, so a HARD
    stop matters more than usual: place it 2x ATR below entry.
  - Never average down beyond a pre-set limit (here: no adds at all).

------------------------------------------------------------------------------
FIT / CAVEATS (documented, per the library's own guidance)
------------------------------------------------------------------------------
  - Designed for equity index ETFs and liquid large caps (SPY, QQQ). The
    library explicitly warns it fails on trending commodities/FX and single
    small-caps. In the 3-symbol harness it is on-domain for SPY, marginal for
    TLT (a bond ETF that does mean-revert), and OUT of domain for BTC-USD
    (trending crypto) - expect it to underperform there. This is expected,
    not a bug.
  - The 200-day filter is load-bearing and must not be dropped.
  - This is a starting template to configure and backtest on your own data,
    NOT a plug-and-play system. Set sizing/stop/regime to your own plan.
"""

from __future__ import annotations

import backtrader as bt


class SkoolVariant1(bt.Strategy):
    params = (
        ("rsi_period", 2),          # 2-period RSI (Connors classic)
        ("rsi_entry", 10.0),        # oversold entry threshold
        ("rsi_exit", 50.0),         # RSI midline exit
        ("trend_ma", 200),          # long-term SMA trend gate (long only above)
        ("exit_ma", 5),             # short SMA exit
        ("max_hold", 10),           # time stop in trading days
        ("atr_period", 14),         # ATR lookback for the hard stop
        ("atr_stop_mult", 2.0),     # hard stop distance = 2x ATR below entry
        ("risk_per_trade", 0.02),   # 2% of equity risked per trade
        # --- Regime inversion (Task: TLT bond dynamics) ---
        # When False (default): long-only dip-buying above the 200-SMA; below it,
        # the strategy simply sits in cash (no valid long setup).
        # When True: below the 200-SMA the engine INVERTS -- it shorts the
        # overbought bounce (mirror of the long rule) instead of holding cash.
        ("allow_short", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        self.sma_trend = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.trend_ma)
        self.sma_exit = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.exit_ma)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

        self.order = None
        self.stop_price = None
        self.entry_bar = None

    # ------------------------------------------------------------------
    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        self.order = None

    # ------------------------------------------------------------------
    def _risk_sized_qty(self, price: float, stop_dist: float) -> int:
        # Percent-of-equity risk sizing: risk_amount / per-share risk.
        if stop_dist <= 0 or price <= 0:
            return 0
        equity = self.broker.getvalue()
        risk_amount = equity * self.p.risk_per_trade
        qty = int(risk_amount / stop_dist)
        # Never lever up: cap notional at available equity (cash broker).
        max_qty = int(equity / price)
        return max(0, min(qty, max_qty))

    # ------------------------------------------------------------------
    def next(self):
        if self.order:
            return

        # Warmup: need the full 200-day trend window.
        if len(self) <= self.p.trend_ma:
            return

        price = self.data.close[0]

        # --- Manage an open LONG position ---
        if self.position.size > 0:
            bars_held = len(self) - self.entry_bar if self.entry_bar is not None else 0
            hard_stop_hit = self.stop_price is not None and price <= self.stop_price
            revert_done = price > self.sma_exit[0] or self.rsi[0] > self.p.rsi_exit
            time_stop = bars_held >= self.p.max_hold

            if hard_stop_hit or revert_done or time_stop:
                self.order = self.close()
                self.stop_price = None
                self.entry_bar = None
            return

        # --- Manage an open SHORT position (invert leg) ---
        if self.position.size < 0:
            bars_held = len(self) - self.entry_bar if self.entry_bar is not None else 0
            hard_stop_hit = self.stop_price is not None and price >= self.stop_price
            # Mirror of the long exit: cover once price rolls back down / momentum cools.
            revert_done = price < self.sma_exit[0] or self.rsi[0] < (100.0 - self.p.rsi_exit)
            time_stop = bars_held >= self.p.max_hold

            if hard_stop_hit or revert_done or time_stop:
                self.order = self.close()
                self.stop_price = None
                self.entry_bar = None
            return

        # --- Entry ---
        above_trend = price > self.sma_trend[0]

        if above_trend:
            # Long-only dip-buy inside the uptrend (RSI-2 oversold).
            if self.rsi[0] < self.p.rsi_entry:
                stop_dist = self.p.atr_stop_mult * self.atr[0]
                qty = self._risk_sized_qty(price, stop_dist)
                if qty > 0:
                    self.order = self.buy(size=qty)
                    self.stop_price = price - stop_dist
                    self.entry_bar = len(self)
        elif self.p.allow_short:
            # Below the 200-SMA and inversion enabled: short the overbought bounce
            # (mirror rule). If allow_short is False we fall through to cash.
            if self.rsi[0] > (100.0 - self.p.rsi_entry):
                stop_dist = self.p.atr_stop_mult * self.atr[0]
                qty = self._risk_sized_qty(price, stop_dist)
                if qty > 0:
                    self.order = self.sell(size=qty)
                    self.stop_price = price + stop_dist
                    self.entry_bar = len(self)

    # ------------------------------------------------------------------
    def stop(self):
        self.final_stats = {
            "rsi_period": self.p.rsi_period,
            "rsi_entry": self.p.rsi_entry,
            "trend_ma": self.p.trend_ma,
        }
