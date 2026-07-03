"""Broker factory. Picks an adapter from config; defaults to the simulator.

The live brokers (IBKR, TradeStation) import optional third-party libraries, so
they are only imported when actually requested. That keeps the simulator path
dependency-free for testing and for members without a funded account yet.
"""

from __future__ import annotations

from brokers.base import (AccountInfo, BrokerAdapter, BrokerPosition, Fill,  # noqa: F401
                          OrderRequest, OrderResult, OrderSide, OrderType)
from brokers.sim_broker import SimBroker


def make_broker(config: dict | None = None) -> BrokerAdapter:
    cfg = config or {}
    btype = str(cfg.get("type", "sim")).lower()
    if btype in ("sim", "simulator", "paper-sim"):
        return SimBroker(cfg.get("sim", {}))
    if btype in ("ibkr", "ib", "interactive_brokers"):
        from brokers.ibkr_broker import IBKRBroker
        return IBKRBroker(cfg.get("ibkr", {}))
    if btype in ("tradestation", "ts", "topstep", "projectx"):
        from brokers.tradestation_broker import TradeStationBroker
        return TradeStationBroker(cfg.get("tradestation", {}))
    raise ValueError(f"Unknown broker type '{btype}'. Use sim, ibkr, or tradestation.")
