"""
broker/__init__.py
==================
Broker factory: the rest of the system asks for a broker by name and gets
a BaseBroker -- vendor SDKs never leak past this package.
"""

from __future__ import annotations

from broker.base import Account, BaseBroker, Order, Position


def get_broker(name: str = "alpaca", paper: bool = True) -> BaseBroker:
    """Registry lookup. Adapters are imported lazily so an uninstalled
    vendor SDK only breaks the venue that needs it."""
    name = name.lower()
    if name == "alpaca":
        from broker.alpaca_client import AlpacaBroker
        return AlpacaBroker(paper=paper)
    raise KeyError(f"unknown broker {name!r} -- known: ['alpaca']")


__all__ = ["Account", "BaseBroker", "Order", "Position", "get_broker"]
