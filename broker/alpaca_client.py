"""
broker/alpaca_client.py
=======================
Alpaca adapter (equities, paper-first).

Docs:  https://docs.alpaca.markets/  (v2 REST via alpaca-trade-api)
Auth:  ALPACA_API_KEY / ALPACA_SECRET_KEY from the environment (.env).
Quirks: API returns all numerics as STRINGS (cast everything); short
        positions come back with negative qty already signed.
Sync/Async: sync SDK; keep the adapter sync (skill rule: never mix).

Corrections vs the draft this was adapted from:
  * GTC MARKET ORDERS: a market order with time_in_force='gtc' that fails
    to execute today lingers and fills on TOMORROW'S opening gap. Market
    orders are DAY; limits accept an explicit tif.
  * LIVE WAS ONE KEYSTROKE AWAY: `paper=False` flipped the real-money
    endpoint. Repo non-negotiable is never-default-live: live now requires
    BOTH paper=False AND ALPACA_CONFIRM_LIVE=YES in the environment.
  * GATEKEEPER ACTUALLY WIRED: the draft fetched positions "for
    reconciliation" but never reconciled, and orders flew regardless of
    state. `guarded_order()` refuses while the gatekeeper is disarmed and
    books fills through update_position; `reconcile()` runs at startup.
  * ORDER FAILURE RETURNED None: silent swallow -- callers couldn't tell
    rejected from crashed. Failures return Order(status='rejected',
    reason=...) so the caller must look at what happened.
  * Kept from the draft (correct instincts): NO retry on order submission
    (a timed-out-but-actually-accepted submit that is retried DOUBLE
    FILLS; retries belong on idempotent reads only) and bounded retries
    on position fetches.
  * Emojis (cp1252 console) removed; connection banner avoids printing
    account numbers.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from broker.base import Account, BaseBroker, Order, Position

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
READ_RETRIES = 3
READ_RETRY_WAIT_S = 1.0


class AlpacaBroker(BaseBroker):
    def __init__(self, paper: bool = True):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        api_key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret:
            raise ValueError(
                "missing ALPACA_API_KEY / ALPACA_SECRET_KEY in environment")

        if not paper and os.getenv("ALPACA_CONFIRM_LIVE") != "YES":
            raise PermissionError(
                "LIVE endpoint requested but ALPACA_CONFIRM_LIVE != 'YES'. "
                "Never-default-live: set the env var explicitly to trade "
                "real money.")
        self.paper = paper

        import alpaca_trade_api as tradeapi
        self.api = tradeapi.REST(api_key, secret,
                                 PAPER_URL if paper else LIVE_URL,
                                 api_version="v2")
        acct = self.get_account()          # fail fast on bad credentials
        print(f"BROKER CONNECTED ({'PAPER' if paper else 'LIVE'}): "
              f"{acct.status} | buying power ${acct.buying_power:,.2f}")

    # ------------------------------------------------------------------
    def _read_with_retry(self, fn, what: str):
        """Bounded retries for IDEMPOTENT reads only -- never writes."""
        last = None
        for attempt in range(READ_RETRIES):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 - vendor boundary
                last = e
                print(f"API error reading {what} "
                      f"(attempt {attempt + 1}/{READ_RETRIES}): {e}")
                time.sleep(READ_RETRY_WAIT_S)
        raise RuntimeError(f"could not read {what} after "
                           f"{READ_RETRIES} attempts: {last}")

    # ------------------------------------------------------------------
    def get_account(self) -> Account:
        raw = self._read_with_retry(self.api.get_account, "account")
        return Account(equity=float(raw.equity), cash=float(raw.cash),
                       buying_power=float(raw.buying_power),
                       status=str(raw.status))

    def get_positions(self) -> list[Position]:
        raw = self._read_with_retry(self.api.list_positions, "positions")
        return [Position(symbol=p.symbol, qty=float(p.qty),
                         avg_entry_price=float(p.avg_entry_price),
                         market_value=float(p.market_value))
                for p in raw]

    def is_market_open(self) -> bool:
        return bool(self._read_with_retry(self.api.get_clock, "clock").is_open)

    def get_bars(self, symbols: list[str], timeframe: str = "1Min",
                 limit: int = 100) -> dict:
        """Recent bars per symbol (IEX feed on free tier -- fine for paper).
        Failed symbols are logged and omitted, never fabricated."""
        out = {}
        for sym in symbols:
            try:
                df = self._read_with_retry(
                    lambda s=sym: self.api.get_bars(s, timeframe,
                                                    limit=limit).df,
                    f"bars {sym}")
                if df is not None and len(df) and "close" in df.columns:
                    out[sym] = df.sort_index()
            except RuntimeError as e:
                print(f"bars unavailable for {sym}: {e}")
        return out

    # ------------------------------------------------------------------
    def submit_order(self, symbol: str, qty: float, side: str,
                     order_type: str = "market",
                     limit_price: float | None = None) -> Order:
        """Single submission, NO retry (a timed-out submit may have been
        accepted; retrying double-fills). Failures come back as a rejected
        Order with the reason -- never None."""
        qty = abs(float(qty))
        if qty == 0:
            return Order(id="", symbol=symbol, side=side, qty=0.0,
                         order_type=order_type, status="rejected",
                         reason="zero quantity")
        if side not in ("buy", "sell"):
            return Order(id="", symbol=symbol, side=side, qty=qty,
                         order_type=order_type, status="rejected",
                         reason=f"invalid side {side!r}")

        args = {"symbol": symbol, "qty": qty, "side": side,
                "type": order_type,
                # Market orders are DAY: a GTC market order left overnight
                # fills on tomorrow's opening gap.
                "time_in_force": "day" if order_type == "market" else "gtc"}
        if order_type == "limit":
            if limit_price is None:
                return Order(id="", symbol=symbol, side=side, qty=qty,
                             order_type=order_type, status="rejected",
                             reason="limit order requires limit_price")
            args["limit_price"] = float(limit_price)

        try:
            raw = self.api.submit_order(**args)
            return Order(id=str(raw.id), symbol=symbol, side=side, qty=qty,
                         order_type=order_type, status=str(raw.status),
                         filled_qty=float(raw.filled_qty or 0))
        except Exception as e:  # noqa: BLE001 - vendor boundary
            return Order(id="", symbol=symbol, side=side, qty=qty,
                         order_type=order_type, status="rejected",
                         reason=str(e))

    def cancel_order(self, order_id: str) -> None:
        self.api.cancel_order(order_id)

    def close_position(self, symbol: str) -> None:
        self.api.close_position(symbol)

    def close_all_positions(self) -> None:
        print("EMERGENCY: closing all positions")
        self.api.close_all_positions()


# ---------------------------------------------------------------------------
def main() -> None:
    """Paper smoke test: connect, reconcile against the gatekeeper, report.
    Requires ALPACA_API_KEY / ALPACA_SECRET_KEY."""
    from utils.state_gatekeeper import StateGatekeeper

    broker = AlpacaBroker(paper=True)
    print(f"market open: {broker.is_market_open()}")
    print(f"positions:   {broker.position_map() or 'none'}")

    gate = StateGatekeeper(ROOT / "state_snapshot.json")
    verdict = broker.reconcile(gate)
    print(f"reconciliation: {verdict['status']}")
    for m in verdict.get("reason", []) if verdict["status"] == "RED" else []:
        print(f"    {m}")
    print(f"gatekeeper armed: {gate.armed}")


if __name__ == "__main__":
    main()
