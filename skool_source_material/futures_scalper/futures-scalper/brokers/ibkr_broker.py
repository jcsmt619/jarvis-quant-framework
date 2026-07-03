"""Interactive Brokers adapter via ib_insync.

ib_insync is an optional dependency. The import is guarded so the package and
its tests run without it installed; you only need it when you actually point the
system at IBKR. Connect to the paper gateway on port 7497 or live on 7496.

This adapter qualifies a continuous-style front-month future, places native
bracket orders, and reports account equity and positions through the shared
interface. Treat it as a working starting point and verify fills on your own
paper account before going live.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from brokers.base import (AccountInfo, BrokerAdapter, BrokerPosition, Fill,
                          OrderRequest, OrderResult, OrderSide, OrderType)
from core.instruments import get_instrument

try:
    from ib_insync import IB, Future, MarketOrder, LimitOrder, util  # type: ignore
    _IB_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when lib is missing
    _IB_AVAILABLE = False


class IBKRBroker(BrokerAdapter):
    name = "ibkr"
    supports_data = True

    def __init__(self, config: dict | None = None) -> None:
        if not _IB_AVAILABLE:
            raise ImportError(
                "ib_insync is not installed. Run `pip install ib_insync` and start "
                "Trader Workstation or the IB Gateway before using the IBKR broker.")
        cfg = config or {}
        self.host = cfg.get("host", "127.0.0.1")
        self.port = int(cfg.get("port", 7497))  # 7497 paper, 7496 live
        self.client_id = int(cfg.get("client_id", 11))
        self.exchange = cfg.get("exchange", "CME")
        self._ib = IB()

    def connect(self) -> None:
        self._ib.connect(self.host, self.port, clientId=self.client_id)

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._ib.isConnected()

    def _contract(self, symbol: str):
        spec = get_instrument(symbol)
        fut = Future(symbol=spec.symbol, exchange=spec.exchange or self.exchange,
                     currency=spec.currency)
        self._ib.qualifyContracts(fut)
        return fut

    def get_account(self) -> AccountInfo:
        vals = {v.tag: v.value for v in self._ib.accountValues() if v.currency in ("USD", "")}
        equity = float(vals.get("NetLiquidation", 0.0) or 0.0)
        cash = float(vals.get("TotalCashValue", equity) or equity)
        bp = float(vals.get("BuyingPower", equity) or equity)
        return AccountInfo(equity=equity, cash=cash, buying_power=bp)

    def get_positions(self) -> list[BrokerPosition]:
        out = []
        for p in self._ib.positions():
            out.append(BrokerPosition(p.contract.symbol, int(p.position),
                                      float(p.avgCost)))
        return out

    def place_order(self, order: OrderRequest) -> OrderResult:
        contract = self._contract(order.symbol)
        action = "BUY" if order.side is OrderSide.BUY else "SELL"
        if order.order_type is OrderType.LIMIT and order.limit_price:
            ib_order = LimitOrder(action, order.quantity, order.limit_price)
        else:
            ib_order = MarketOrder(action, order.quantity)
        trade = self._ib.placeOrder(contract, ib_order)
        self._ib.sleep(0.5)
        fills = [Fill(str(f.execution.execId), order.symbol, order.side,
                      int(f.execution.shares), float(f.execution.price),
                      datetime.now(timezone.utc)) for f in trade.fills]
        return OrderResult(accepted=True, order_id=str(trade.order.orderId),
                           status=str(trade.orderStatus.status), fills=fills)

    def place_bracket(self, order: OrderRequest) -> OrderResult:
        contract = self._contract(order.symbol)
        action = "BUY" if order.side is OrderSide.BUY else "SELL"
        bracket = self._ib.bracketOrder(
            action, order.quantity,
            limitPrice=order.limit_price or 0,
            takeProfitPrice=order.take_profit or 0,
            stopLossPrice=order.stop_loss or 0)
        last = None
        for o in bracket:
            last = self._ib.placeOrder(contract, o)
        self._ib.sleep(0.5)
        return OrderResult(accepted=True, order_id=str(last.order.orderId) if last else "",
                           status="submitted")

    def close_position(self, symbol: str) -> OrderResult:
        for p in self._ib.positions():
            if p.contract.symbol == symbol and p.position != 0:
                side = OrderSide.SELL if p.position > 0 else OrderSide.BUY
                return self.place_order(OrderRequest(symbol, side, abs(int(p.position)),
                                                     OrderType.MARKET, reduce_only=True))
        return OrderResult(accepted=True, status="flat")

    def close_all(self) -> list[OrderResult]:
        results = []
        for p in self._ib.positions():
            if p.position != 0:
                results.append(self.close_position(p.contract.symbol))
        return results

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 500,
                 start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        contract = self._contract(symbol)
        bar_size = {"1Min": "1 min", "5Min": "5 mins", "15Min": "15 mins",
                    "1H": "1 hour", "1Day": "1 day"}.get(timeframe, "5 mins")
        dur = f"{max(1, limit // 78)} D"
        bars = self._ib.reqHistoricalData(
            contract, endDateTime="", durationStr=dur, barSizeSetting=bar_size,
            whatToShow="TRADES", useRTH=False)
        df = util.df(bars)
        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = df.rename(columns={"date": "timestamp"}).set_index("timestamp")
        return df[["open", "high", "low", "close", "volume"]].tail(limit)

    def is_market_open(self) -> bool:
        return True
