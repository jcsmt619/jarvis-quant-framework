"""Built-in simulation broker (the default).

It fills market orders at the current price plus a tick of slippage, tracks
positions and contract P&L through the instrument spec, and on each new bar
checks whether a bracket stop or target was touched. It is good enough to run
the live loop in paper mode with no external account, and it is what the test
suite executes against so the whole pipeline is verifiable offline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from brokers.base import (AccountInfo, BrokerAdapter, BrokerPosition, Fill,
                          OrderRequest, OrderResult, OrderSide, OrderType)
from core.instruments import InstrumentSpec, get_instrument


@dataclass
class _Pos:
    symbol: str
    qty: int                 # signed
    avg_price: float
    stop: Optional[float] = None
    target: Optional[float] = None


class SimBroker(BrokerAdapter):
    name = "sim"
    supports_data = False

    def __init__(self, config: dict | None = None,
                 instruments: Optional[dict[str, InstrumentSpec]] = None) -> None:
        cfg = config or {}
        self.initial_equity = float(cfg.get("initial_equity", 50000.0))
        self.slippage_ticks = float(cfg.get("slippage_ticks", 1.0))
        self.commission_per_contract = float(cfg.get("commission_per_contract", 2.50))
        self._instruments = instruments or {}
        self._connected = False
        self._positions: dict[str, _Pos] = {}
        self._last_price: dict[str, float] = {}
        self._realized = 0.0
        self._commission_paid = 0.0
        self.fills: list[Fill] = []
        self.closed_trades: list[dict] = []

    # -- lifecycle ---------------------------------------------------------
    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # -- instrument resolution --------------------------------------------
    def _spec(self, symbol: str) -> InstrumentSpec:
        if symbol in self._instruments:
            return self._instruments[symbol]
        return get_instrument(symbol)

    # -- price feed --------------------------------------------------------
    def set_price(self, symbol: str, price: float) -> None:
        self._last_price[symbol] = price

    def on_bar(self, symbol: str, bar: pd.Series) -> Optional[dict]:
        """Advance the simulator one bar. Returns a trade dict if a bracket exits."""
        self._last_price[symbol] = float(bar["close"])
        pos = self._positions.get(symbol)
        if pos is None or pos.qty == 0:
            return None
        spec = self._spec(symbol)
        hi, lo = float(bar["high"]), float(bar["low"])

        exit_price = None
        reason = ""
        if pos.qty > 0:  # long
            if pos.stop is not None and lo <= pos.stop:
                exit_price, reason = pos.stop, "stop"
            elif pos.target is not None and hi >= pos.target:
                exit_price, reason = pos.target, "target"
        else:            # short
            if pos.stop is not None and hi >= pos.stop:
                exit_price, reason = pos.stop, "stop"
            elif pos.target is not None and lo <= pos.target:
                exit_price, reason = pos.target, "target"

        if exit_price is not None:
            return self._close(symbol, exit_price, bar.name, reason)
        return None

    # -- orders ------------------------------------------------------------
    def place_order(self, order: OrderRequest) -> OrderResult:
        if not self._connected:
            return OrderResult(accepted=False, message="not connected")
        spec = self._spec(order.symbol)
        ref = self._last_price.get(order.symbol)
        if ref is None and order.limit_price is not None:
            ref = order.limit_price
        if ref is None:
            return OrderResult(accepted=False, message="no price available for fill")

        slip = self.slippage_ticks * spec.tick_size
        fill_price = ref + slip if order.side is OrderSide.BUY else ref - slip
        fill_price = spec.round_to_tick(fill_price)

        signed = order.quantity if order.side is OrderSide.BUY else -order.quantity
        trade = self._apply_fill(order.symbol, signed, fill_price, spec)

        # Attach bracket levels to the resulting position.
        pos = self._positions.get(order.symbol)
        if pos and pos.qty != 0:
            if order.stop_loss is not None:
                pos.stop = spec.round_to_tick(order.stop_loss)
            if order.take_profit is not None:
                pos.target = spec.round_to_tick(order.take_profit)

        oid = uuid.uuid4().hex[:12]
        comm = self.commission_per_contract * order.quantity
        self._commission_paid += comm
        fill = Fill(oid, order.symbol, order.side, order.quantity, fill_price,
                    datetime.now(timezone.utc), commission=comm)
        self.fills.append(fill)
        return OrderResult(accepted=True, order_id=oid, status="filled", fills=[fill])

    def _apply_fill(self, symbol: str, signed_qty: int, price: float,
                    spec: InstrumentSpec) -> Optional[dict]:
        pos = self._positions.get(symbol)
        if pos is None or pos.qty == 0:
            self._positions[symbol] = _Pos(symbol, signed_qty, price)
            return None

        same_dir = (pos.qty > 0) == (signed_qty > 0)
        if same_dir:
            total = pos.qty + signed_qty
            pos.avg_price = (pos.avg_price * abs(pos.qty) + price * abs(signed_qty)) / abs(total)
            pos.qty = total
            return None

        # Opposite direction: reduce / close / flip.
        closing = min(abs(pos.qty), abs(signed_qty))
        direction = "long" if pos.qty > 0 else "short"
        realized = spec.pnl(pos.avg_price, price, closing, direction)
        self._realized += realized
        self.closed_trades.append({
            "symbol": symbol, "direction": direction, "contracts": closing,
            "entry": pos.avg_price, "exit": price, "pnl": realized,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        remaining = abs(pos.qty) - closing
        leftover_signal = abs(signed_qty) - closing
        if remaining > 0:
            pos.qty = remaining if pos.qty > 0 else -remaining
        elif leftover_signal > 0:
            pos.qty = leftover_signal if signed_qty > 0 else -leftover_signal
            pos.avg_price = price
            pos.stop = pos.target = None
        else:
            self._positions.pop(symbol, None)
        return self.closed_trades[-1]

    def _close(self, symbol: str, price: float, ts, reason: str) -> dict:
        pos = self._positions[symbol]
        spec = self._spec(symbol)
        direction = "long" if pos.qty > 0 else "short"
        realized = spec.pnl(pos.avg_price, price, abs(pos.qty), direction)
        self._realized += realized
        trade = {
            "symbol": symbol, "direction": direction, "contracts": abs(pos.qty),
            "entry": pos.avg_price, "exit": price, "pnl": realized,
            "reason": reason, "at": str(ts),
        }
        self.closed_trades.append(trade)
        self._positions.pop(symbol, None)
        return trade

    def close_position(self, symbol: str) -> OrderResult:
        pos = self._positions.get(symbol)
        if not pos or pos.qty == 0:
            return OrderResult(accepted=True, status="flat", message="no position")
        side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
        return self.place_order(OrderRequest(symbol, side, abs(pos.qty),
                                             OrderType.MARKET, reduce_only=True))

    def close_all(self) -> list[OrderResult]:
        return [self.close_position(s) for s in list(self._positions)]

    # -- account -----------------------------------------------------------
    def get_positions(self) -> list[BrokerPosition]:
        out = []
        for pos in self._positions.values():
            if pos.qty == 0:
                continue
            spec = self._spec(pos.symbol)
            last = self._last_price.get(pos.symbol, pos.avg_price)
            direction = "long" if pos.qty > 0 else "short"
            upnl = spec.pnl(pos.avg_price, last, abs(pos.qty), direction)
            out.append(BrokerPosition(pos.symbol, pos.qty, pos.avg_price, upnl))
        return out

    def get_account(self) -> AccountInfo:
        open_pnl = sum(p.unrealized_pnl for p in self.get_positions())
        equity = self.initial_equity + self._realized - self._commission_paid + open_pnl
        return AccountInfo(
            equity=equity,
            cash=equity - open_pnl,
            buying_power=max(0.0, equity),
            realized_pnl=self._realized - self._commission_paid,
            open_pnl=open_pnl,
        )
