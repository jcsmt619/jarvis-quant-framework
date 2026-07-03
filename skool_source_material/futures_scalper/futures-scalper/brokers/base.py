"""Broker abstraction so the system is not tied to any one execution venue.

Every broker (the built-in simulator, IBKR, TradeStation, or a prop-firm gateway
like Topstep/ProjectX) implements the same small interface. The rest of the
system only ever talks to :class:`BrokerAdapter`, so switching venues is a config
change, not a code change. The simulator is the default so the whole pipeline
runs and is testable without any live account or network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    client_id: Optional[str] = None
    reduce_only: bool = False


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0


@dataclass
class OrderResult:
    accepted: bool
    order_id: str = ""
    status: str = ""
    fills: list[Fill] = field(default_factory=list)
    message: str = ""


@dataclass
class BrokerPosition:
    symbol: str
    quantity: int                # signed: positive long, negative short
    avg_price: float
    unrealized_pnl: float = 0.0


@dataclass
class AccountInfo:
    equity: float
    cash: float
    buying_power: float
    realized_pnl: float = 0.0
    open_pnl: float = 0.0


class BrokerAdapter(ABC):
    name: str = "base"
    supports_data: bool = False  # can this adapter also serve historical bars

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_account(self) -> AccountInfo: ...

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def close_position(self, symbol: str) -> OrderResult: ...

    @abstractmethod
    def close_all(self) -> list[OrderResult]: ...

    def place_bracket(self, order: OrderRequest) -> OrderResult:
        """Default bracket = entry order carrying stop_loss / take_profit fields.

        Adapters that support native OCO brackets should override this.
        """
        return self.place_order(order)

    def get_bars(self, symbol: str, timeframe: str = "5Min",
                 limit: int = 500, start: Optional[str] = None,
                 end: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError(f"{self.name} does not provide historical bars")

    def is_market_open(self) -> bool:
        return True
