"""
Hyper-Alpha Kelly Strategy (Module-Integrated)
==============================================
High-velocity Breakout Momentum engine + ATR-based trend follower, wired to the
shared KellyCriterionSizer and ATRCircuit modules for a cohesive system.

Pipeline:
1. Breakout Momentum: Donchian N-bar high breakout + Rate-of-Change velocity.
2. ATR Trend Filter: only take breakouts aligned with a rising trend EMA.
3. KellyCriterionSizer (utils.kelly_criterion): dynamic sizing from rolling
   win-rate / edge; supports FULL Kelly with up to 5x leverage cap and instant
   flatten on regime drift.
4. ATRCircuit (utils.atr_circuit): non-linear trailing stop + spike scale-outs,
   backstopped by a hard 2.5x ATR trailing stop to cut losses instantly.

Intended for high-beta intraday assets (BTCUSD, ETHUSD, SOXL, TQQQ).

RISK NOTE: Full Kelly at 5x leverage is, by design, an aggressive path with a
high theoretical probability of deep drawdowns / ruin. The backtest harness that
drives this strategy applies realistic friction and liquidation checks so the
reported results reflect blow-up risk rather than idealized fills.
"""

from __future__ import annotations

import sys
from pathlib import Path

import backtrader as bt

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.kelly_criterion import KellyCriterionSizer, TradeRecord
from utils.atr_circuit import ATRCircuit, ExitSignal
from utils.runner_exit import RunnerManager


class HyperAlphaKelly(bt.Strategy):
    params = (
        # --- Breakout Momentum engine ---
        ("breakout_period", 20),          # N-bar high channel for breakouts
        ("momentum_period", 10),          # ROC lookback confirming velocity
        ("momentum_threshold", 0.0),      # Minimum ROC to confirm momentum
        ("breakout_buffer", 0.0),         # Loosen breakout: enter above highest*(1-buffer)
        ("require_trend_rising", True),    # If False, only require price>trend (micro-trends)
        # --- ATR trend follower / circuit ---
        ("atr_period", 14),
        ("trend_ema", 50),                # Trend filter EMA
        ("atr_trail_mult", 2.5),          # Hard trailing stop distance (2.5x ATR)
        ("spike_threshold_atr", 4.0),     # ATRCircuit spike scale-out trigger
        ("rsi_period", 14),               # For spike confirmation
        # --- Kelly Criterion sizing (module-driven) ---
        ("kelly_fraction", 1.0),          # 1.0 = FULL Kelly (aggressive)
        ("kelly_lookback", 100),          # Rolling trades window for edge stats
        ("kelly_min_trades", 20),         # Min closed trades before Kelly engages
        ("kelly_max_leverage", 5.0),      # Hard cap on Kelly leverage
        ("min_edge_ratio", 1.2),          # Min payoff ratio to scale above base
        ("regime_drift_winrate", 0.40),   # Below this recent win rate => flatten/zero
        ("warmup", 55),                   # Bars before trading
        # --- Runner Mode exit management (uncapped upside, tighten-only risk) ---
        ("runner_mode", True),            # bank 50% @ +1.5R, breakeven, 2x ATR trail
        ("runner_trigger_r", 1.5),
        ("runner_trail_mult", 2.0),
    )

    def __init__(self):
        # --- Breakout Momentum indicators ---
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.breakout_period)
        self.roc = bt.indicators.RateOfChange(self.data.close, period=self.p.momentum_period)

        # --- ATR trend follower ---
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.trend = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.trend_ema)
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)

        # --- Shared modules (cohesive integration) ---
        self.kelly = KellyCriterionSizer(
            lookback_window=self.p.kelly_lookback,
            kelly_fraction=self.p.kelly_fraction,
            min_sample_trades=self.p.kelly_min_trades,
            regime_drift_threshold=self.p.regime_drift_winrate,
            min_edge_ratio=self.p.min_edge_ratio,
        )
        self.circuit = ATRCircuit(
            atr_period=self.p.atr_period,
            spike_threshold_atr=self.p.spike_threshold_atr,
        )

        # --- Order / position state ---
        self.order = None
        self.entry_price = None
        self.trail_stop = None
        self.scaled_out = False
        self.runner = RunnerManager(
            trigger_r=self.p.runner_trigger_r,
            trail_atr_mult=self.p.runner_trail_mult,
        )

    # ------------------------------------------------------------------
    # Position sizing via KellyCriterionSizer module
    # ------------------------------------------------------------------
    def _position_size(self, price: float) -> int:
        result = self.kelly.calculate_position_size(self.broker.getvalue())
        frac = result.get("position_size_fraction", 0.0)
        # Enforce hard leverage cap (module also clamps to 5x)
        frac = max(0.0, min(frac, self.p.kelly_max_leverage))
        if frac <= 0.0 or price <= 0:
            return 0
        target_notional = self.broker.getvalue() * frac
        return max(int(target_notional / price), 0)

    # ------------------------------------------------------------------
    # Order / trade bookkeeping -> feed the Kelly ledger
    # ------------------------------------------------------------------
    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        pnl = trade.pnlcomm
        equity = self.broker.getvalue()
        record = TradeRecord(
            exit_date=self.data.datetime.datetime(0),
            entry_price=self.entry_price if self.entry_price else 0.0,
            exit_price=self.data.close[0],
            pnl=pnl,
            pnl_pct=(pnl / equity) if equity else 0.0,
            is_win=pnl > 0,
            hold_bars=trade.barlen,
        )
        self.kelly.add_trade(record)

    # ------------------------------------------------------------------
    # Core strategy loop
    # ------------------------------------------------------------------
    def next(self):
        if self.order:
            return
        if len(self) < self.p.warmup:
            return

        price = self.data.close[0]
        atr = self.atr[0]
        if atr <= 0:
            return

        # --- Manage open position via Runner Mode / ATRCircuit + hard trail ---
        if self.position.size > 0:
            # Runner Mode: bank 50% at +1.5R, stop -> breakeven, 2x ATR trail.
            # Every action only tightens risk; the hard trail below still applies
            # pre-trigger so early losses are cut exactly as before.
            if self.p.runner_mode and self.runner.active:
                act = self.runner.update(price, atr)
                if act.banked_this_bar:
                    half = max(int(self.position.size / 2), 1)
                    self.order = self.sell(size=half)
                    self.scaled_out = True
                    return
                if act.exited:
                    self.order = self.sell(size=self.position.size)
                    self.entry_price = None
                    self.trail_stop = None
                    self.scaled_out = False
                    return

            # ATRCircuit spike scale-out (lock hyper-profits on vertical moves)
            if not self.scaled_out and self.entry_price:
                spike = self.circuit.detect_spike_exit(
                    current_price=price,
                    entry_price=self.entry_price,
                    atr_value=atr,
                    rsi=self.rsi[0],
                )
                if spike["exit_signal"] == ExitSignal.SCALE_OUT_50PCT:
                    half = max(int(self.position.size / 2), 1)
                    self.order = self.sell(size=half)
                    self.scaled_out = True
                    return

            # Hard 2.5x ATR trailing stop (ratchet up only)
            new_stop = price - self.p.atr_trail_mult * atr
            if self.trail_stop is None or new_stop > self.trail_stop:
                self.trail_stop = new_stop

            if price <= self.trail_stop:
                self.order = self.sell(size=self.position.size)
                self.entry_price = None
                self.trail_stop = None
                self.scaled_out = False
                self.runner.close_trade()
            return

        # --- Entry: Breakout Momentum + ATR trend alignment ---
        breakout_up = price > self.highest[-1] * (1.0 - self.p.breakout_buffer)
        momentum_ok = self.roc[0] > self.p.momentum_threshold
        if self.p.require_trend_rising:
            trend_ok = price > self.trend[0] and self.trend[0] > self.trend[-1]
        else:
            trend_ok = price > self.trend[0]

        if breakout_up and momentum_ok and trend_ok:
            size = self._position_size(price)
            if size > 0:
                self.order = self.buy(size=size)
                self.entry_price = price
                self.trail_stop = price - self.p.atr_trail_mult * atr
                self.scaled_out = False
                if self.p.runner_mode:
                    self.runner.open_trade(price, self.trail_stop)

    def stop(self):
        n = len(self.kelly.closed_trades)
        wins = sum(1 for t in self.kelly.closed_trades if t.is_win)
        self.final_stats = {
            "trades": n,
            "win_rate": (wins / n) if n else 0.0,
            "regime_state": self.kelly.regime_state,
        }

