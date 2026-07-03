"""TradeStation adapter, also the entry point for prop-firm gateways.

This is the venue the community approved for ten-thousand-dollar accounts. It
talks to the TradeStation REST API over OAuth. The same shape works for a
prop-firm gateway such as Topstep's ProjectX: point ``base_url`` and the auth
fields at the gateway and keep the rest. ``requests`` is imported lazily so the
package runs without it.

Endpoints and payloads follow TradeStation's documented v3 brokerage API. Set
credentials in .env, never in code, and test against a simulated account first.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from brokers.base import (AccountInfo, BrokerAdapter, BrokerPosition,
                          OrderRequest, OrderResult, OrderSide, OrderType)

try:
    import requests  # type: ignore
    _REQUESTS = True
except Exception:  # pragma: no cover
    _REQUESTS = False


class TradeStationBroker(BrokerAdapter):
    name = "tradestation"
    supports_data = True

    def __init__(self, config: dict | None = None) -> None:
        if not _REQUESTS:
            raise ImportError("The `requests` package is required for the TradeStation broker.")
        cfg = config or {}
        self.base_url = cfg.get("base_url", "https://api.tradestation.com/v3")
        self.account_id = cfg.get("account_id") or os.getenv("TS_ACCOUNT_ID", "")
        self._client_id = os.getenv("TS_CLIENT_ID", "")
        self._client_secret = os.getenv("TS_CLIENT_SECRET", "")
        self._refresh_token = os.getenv("TS_REFRESH_TOKEN", "")
        self._access_token: Optional[str] = None
        self._connected = False
        self.simulated = bool(cfg.get("simulated", True))

    def connect(self) -> None:
        self._refresh_access_token()
        self._connected = self._access_token is not None

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _refresh_access_token(self) -> None:
        resp = requests.post(
            "https://signin.tradestation.com/oauth/token",
            data={"grant_type": "refresh_token", "client_id": self._client_id,
                  "client_secret": self._client_secret, "refresh_token": self._refresh_token},
            timeout=15)
        resp.raise_for_status()
        self._access_token = resp.json().get("access_token")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def get_account(self) -> AccountInfo:
        r = requests.get(f"{self.base_url}/brokerage/accounts/{self.account_id}/balances",
                         headers=self._headers(), timeout=15)
        r.raise_for_status()
        bal = (r.json().get("Balances") or [{}])[0]
        equity = float(bal.get("Equity", 0) or 0)
        cash = float(bal.get("CashBalance", equity) or equity)
        bp = float(bal.get("BuyingPower", equity) or equity)
        return AccountInfo(equity=equity, cash=cash, buying_power=bp)

    def get_positions(self) -> list[BrokerPosition]:
        r = requests.get(f"{self.base_url}/brokerage/accounts/{self.account_id}/positions",
                         headers=self._headers(), timeout=15)
        r.raise_for_status()
        out = []
        for p in r.json().get("Positions", []):
            qty = int(float(p.get("Quantity", 0)))
            out.append(BrokerPosition(p.get("Symbol", ""), qty,
                                      float(p.get("AveragePrice", 0) or 0),
                                      float(p.get("UnrealizedProfitLoss", 0) or 0)))
        return out

    def place_order(self, order: OrderRequest) -> OrderResult:
        payload = {
            "AccountID": self.account_id,
            "Symbol": order.symbol,
            "Quantity": str(order.quantity),
            "OrderType": "Market" if order.order_type is OrderType.MARKET else "Limit",
            "TradeAction": "BUY" if order.side is OrderSide.BUY else "SELL",
            "TimeInForce": {"Duration": "DAY"},
            "Route": "Intelligent",
        }
        if order.order_type is OrderType.LIMIT and order.limit_price:
            payload["LimitPrice"] = str(order.limit_price)
        r = requests.post(f"{self.base_url}/orderexecution/orders",
                          headers=self._headers(), json=payload, timeout=15)
        ok = r.status_code in (200, 201)
        body = r.json() if ok else {}
        order_id = ((body.get("Orders") or [{}])[0]).get("OrderID", "")
        return OrderResult(accepted=ok, order_id=order_id,
                           status="submitted" if ok else "rejected",
                           message="" if ok else r.text[:200])

    def close_position(self, symbol: str) -> OrderResult:
        for p in self.get_positions():
            if p.symbol == symbol and p.quantity != 0:
                side = OrderSide.SELL if p.quantity > 0 else OrderSide.BUY
                return self.place_order(OrderRequest(symbol, side, abs(p.quantity),
                                                     OrderType.MARKET, reduce_only=True))
        return OrderResult(accepted=True, status="flat")

    def close_all(self) -> list[OrderResult]:
        return [self.close_position(p.symbol) for p in self.get_positions() if p.quantity != 0]

    def is_market_open(self) -> bool:
        return True
