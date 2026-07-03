"""
paper_loop.py
=============
The PAPER trading daemon: the composition layer that the go-live review
found missing. Wires the tested components -- broker adapter, gatekeeper,
risk manager, JSON logging, rate-limited alerts -- into one loop, so the
mandatory 30-day paper clock can start.

HONEST FRAMING (CRO stamp): the signal traded here is the structural-arb
z-score reversion we PROVED loses slowly at daily bars net of friction
(9/10 DEAD). At 1-minute bars it is UNTESTED. This loop's purpose is to
validate the PLUMBING -- reconciliation, risk gating, pair atomicity,
crash recovery, logging -- over 30+ days of paper trading. It is not an
alpha claim, and a live switch on the back of this run would still
require a strategy that survives the validation stack.

Corrections vs the draft this was adapted from:
  * Imports/API: `brokers`/`state_gatekeeper`/`structural_arb` bare module
    paths, 2-tuple unpack of 3-tuple STRUCTURAL_PAIRS, nonexistent
    `get_buying_power()`, `gate.is_armed()`, `gate.state['strategy']
    ['active']`, and a `reconcile` YELLOW branch that cannot occur --
    all fixed against the real contracts.
  * RISK MANAGER BYPASSED: the draft sent orders straight to the broker.
    Go-live checklist section 4 is explicit -- every signal through
    validate_signal(), no bypass. Both legs must be APPROVED before
    either order is sent; breaker state and the kill-switch lock file are
    checked every cycle.
  * PAIR ATOMICITY: the draft could fill leg A and silently drop leg B
    (rejected/HTB), leaving a naked directional position. Leg B failure
    now triggers an immediate unwind of leg A, with an alert.
  * No band-snap exit (|z| > 3.5 -- co-integration breaking is an EXIT,
    as in the pairs engine), free-text logging replaced with the JSON
    structured logger, `schedule` dependency dropped (plain 60s cycle),
    sys.exit inside the signal handler replaced with a graceful flag so
    a Ctrl+C can never interrupt a half-sent pair, emojis removed.

Run:  python paper_loop.py            (paper only -- this file has no
                                       live path AT ALL, by design)
"""

from __future__ import annotations

import signal as os_signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.structural_arb import STRUCTURAL_PAIRS
from broker import get_broker
from core.risk_manager import (PortfolioState, RiskLimits, RiskManager,
                               TradeSignal)
from monitoring.alerts import AlertManager
from monitoring.logger import get_logger
from utils.state_gatekeeper import StateGatekeeper

TIMEFRAME = "1Min"
LOOKBACK = 30                # bars for the rolling z-score
Z_ENTRY = 2.0
Z_EXIT = 0.5
Z_STOP = 3.5                 # band snap: the relationship is breaking -> exit
NOTIONAL_PER_LEG = 2_000.0   # paper-test sizing cap
CYCLE_SECONDS = 60

logger = get_logger("paper_loop", log_file="paper_loop.jsonl")


class PaperTradingLoop:
    def __init__(self):
        self.running = True
        self.gate = StateGatekeeper(ROOT / "state_snapshot.json")
        self.broker = get_broker("alpaca", paper=True)   # no live path here
        acct = self.broker.get_account()
        self.risk = RiskManager(RiskLimits.from_settings(),
                                initial_capital=acct.equity)
        self.alerts = AlertManager(rate_limit_minutes=15)
        os_signal.signal(os_signal.SIGINT, self._request_stop)
        os_signal.signal(os_signal.SIGTERM, self._request_stop)
        logger.info("paper loop initialized",
                    extra={"extra_fields": {"equity": acct.equity,
                                            "pairs": len(STRUCTURAL_PAIRS)}})

    # ------------------------------------------------------------------
    def _request_stop(self, signum=None, frame=None):
        """Graceful: finish the current cycle -- never interrupt a
        half-sent pair -- then save and exit from run()."""
        logger.warning("shutdown signal received; stopping after this cycle")
        self.running = False

    # ------------------------------------------------------------------
    def startup_reconciliation(self) -> None:
        verdict = self.broker.reconcile(self.gate)
        if verdict["status"] == "RED":
            for m in verdict["reason"]:
                logger.critical(m)
            self.alerts.data_feed_failure(
                "startup reconciliation FAILED -- human intervention required")
            logger.critical("halting: run adopt_broker_state + resume_trading "
                            "after manual review")
            sys.exit(1)
        logger.info("startup reconciliation GREEN -- system armed")

    # ------------------------------------------------------------------
    def pair_zscore(self, a: str, b: str):
        """Causal rolling z of log(A)-log(B) on 1-min closes."""
        bars = self.broker.get_bars([a, b], TIMEFRAME, limit=LOOKBACK + 5)
        if a not in bars or b not in bars:
            return None, None
        ca, cb = bars[a]["close"], bars[b]["close"]
        idx = ca.index.intersection(cb.index)
        if len(idx) < LOOKBACK:
            return None, None
        spread = np.log(ca.loc[idx]) - np.log(cb.loc[idx])
        mu = spread.rolling(LOOKBACK).mean()
        sd = spread.rolling(LOOKBACK).std()
        z = float(((spread - mu) / sd.where(sd > 0)).iloc[-1])
        if not np.isfinite(z):
            return None, None
        return z, (float(ca.loc[idx].iloc[-1]), float(cb.loc[idx].iloc[-1]))

    # ------------------------------------------------------------------
    def _leg_signal(self, symbol: str, direction: int, price: float,
                    closes) -> TradeSignal:
        """Risk-manager signal for one leg. Stop is MANDATORY: 2x a
        1-min ATR proxy from recent closes."""
        atr = float(np.abs(np.diff(closes[-LOOKBACK:])).mean())
        stop = price - direction * 2.0 * atr
        return TradeSignal(symbol=symbol, direction=direction,
                           asset_class="equity", price=price, atr=atr,
                           stop_loss=stop, regime="paper_structural",
                           timestamp=datetime.now(timezone.utc))

    def _portfolio_state(self) -> PortfolioState:
        acct = self.broker.get_account()
        return PortfolioState(
            equity=acct.equity, cash=acct.cash,
            buying_power=acct.buying_power,
            positions={t: {"notional": v["qty"] * v["entry_price"],
                           "direction": 1 if v["qty"] > 0 else -1}
                       for t, v in self.gate.state["positions"].items()},
            peak_equity=self.risk.peak_equity)

    # ------------------------------------------------------------------
    def enter_pair(self, a: str, b: str, z: float, prices, closes_a, closes_b):
        dir_a = 1 if z < -Z_ENTRY else -1     # spread low -> long A / short B
        sig_a = self._leg_signal(a, dir_a, prices[0], closes_a)
        sig_b = self._leg_signal(b, -dir_a, prices[1], closes_b)
        state = self._portfolio_state()

        # BOTH legs must clear the risk manager before EITHER order is sent.
        dec_a = self.risk.validate_signal(sig_a, state)
        dec_b = self.risk.validate_signal(sig_b, state)
        if not (dec_a.approved and dec_b.approved):
            logger.info("pair entry rejected by risk manager",
                        extra={"extra_fields": {
                            "pair": f"{a}/{b}",
                            "a": dec_a.rejection_reason,
                            "b": dec_b.rejection_reason}})
            return

        qty_a = max(int(NOTIONAL_PER_LEG / prices[0]), 1)
        qty_b = max(int(NOTIONAL_PER_LEG / prices[1]), 1)
        side_a = "buy" if dir_a > 0 else "sell"
        side_b = "sell" if dir_a > 0 else "buy"

        order_a = self.broker.guarded_order(self.gate, a, qty_a, side_a)
        if order_a.status == "rejected":
            logger.warning(f"leg A rejected, pair abandoned: {order_a.reason}")
            return
        order_b = self.broker.guarded_order(self.gate, b, qty_b, side_b)
        if order_b.status == "rejected":
            # PAIR ATOMICITY: never sit naked on one leg.
            logger.error(f"leg B rejected ({order_b.reason}); unwinding leg A")
            self.alerts.strategy_disabled(
                "paper_structural",
                f"pair atomicity break on {a}/{b}: unwound leg A")
            unwind_side = "sell" if side_a == "buy" else "buy"
            self.broker.guarded_order(self.gate, a, qty_a, unwind_side)
            return
        logger.info("pair entered", extra={"extra_fields": {
            "pair": f"{a}/{b}", "z": round(z, 2), "dir_a": dir_a,
            "qty_a": qty_a, "qty_b": qty_b}})

    def exit_pair(self, a: str, b: str, z: float, why: str):
        for sym in (a, b):
            qty = self.gate.get_position(sym)
            if qty != 0:
                self.broker.guarded_order(self.gate, sym, abs(qty),
                                          "sell" if qty > 0 else "buy")
        logger.info("pair exited", extra={"extra_fields": {
            "pair": f"{a}/{b}", "z": round(z, 2), "why": why}})

    # ------------------------------------------------------------------
    def cycle(self) -> None:
        if not self.broker.is_market_open():
            return
        if self.risk.kill_switch_engaged():
            self.alerts.circuit_breaker("kill_switch_lock", 0.0,
                                        self.broker.get_account().equity)
            return
        if not self.gate.armed:
            logger.warning("gatekeeper disarmed: "
                           + self.gate.state["strategy"]["halt_reason"])
            return
        acct = self.broker.get_account()
        action = self.risk.update(datetime.now(timezone.utc), acct.equity,
                                  regime="paper_structural",
                                  open_positions=len(
                                      self.gate.state["positions"]))
        if self.risk.size_multiplier(action) == 0.0:
            peak = self.risk.peak_equity
            dd = (peak - acct.equity) / peak if peak > 0 else 0.0
            self.alerts.circuit_breaker(str(action), dd, acct.equity)
            return

        for a, b, _note in STRUCTURAL_PAIRS:
            z, prices = self.pair_zscore(a, b)
            if z is None:
                continue
            flat = (self.gate.get_position(a) == 0
                    and self.gate.get_position(b) == 0)
            if flat and abs(z) > Z_ENTRY and abs(z) <= Z_STOP:
                bars = self.broker.get_bars([a, b], TIMEFRAME,
                                            limit=LOOKBACK + 5)
                self.enter_pair(a, b, z, prices,
                                bars[a]["close"].to_numpy(),
                                bars[b]["close"].to_numpy())
            elif not flat and abs(z) < Z_EXIT:
                self.exit_pair(a, b, z, "reverted")
            elif not flat and abs(z) > Z_STOP:
                self.exit_pair(a, b, z, "band snap -- relationship breaking")

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.startup_reconciliation()
        logger.info("paper loop LIVE (paper endpoint only); Ctrl+C to stop")
        while self.running:
            started = time.monotonic()
            try:
                self.cycle()
            except Exception:  # noqa: BLE001 - halt, never trade blind
                logger.exception("unhandled exception in cycle -- HALTING")
                self.gate._disarm("unhandled exception in paper loop cycle")
                self.alerts.circuit_breaker("unhandled_exception", 0.0, 0.0)
                break
            time.sleep(max(1.0, CYCLE_SECONDS - (time.monotonic() - started)))
        self.gate.save_state()
        logger.info("state saved; paper loop stopped cleanly")


if __name__ == "__main__":
    PaperTradingLoop().run()
