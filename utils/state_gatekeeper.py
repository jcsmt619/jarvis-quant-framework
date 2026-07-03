"""
utils/state_gatekeeper.py
=========================
The flight recorder: crash-safe state persistence + broker reconciliation.
These are the two go-live blockers from the production review -- a bot that
cannot prove its local book matches the broker's book has no business
sending orders.

Corrections vs the draft this was adapted from:
  * CORRUPTION MUST HALT, NOT RESET: the draft backed up a corrupt state
    file and continued on a blank "genesis" slate -- a live bot that wakes
    up believing it is FLAT while real positions exist will build a second
    book on top of them. Corruption now backs up the file, marks
    `requires_reconciliation`, and DISARMS trading until an operator runs
    reconcile/adopt + an explicit resume.
  * SHORT-POSITION LEDGER: a fresh short kept entry_price=0.0 (P&L garbage
    forever) and COVERING a short ran the buy-side weighted-average on a
    negative quantity (cover half of -10 @ 100 at 110 -> "entry" 90).
    Correct ledger: same-direction adds average in; reductions never touch
    the entry; crossing zero resets the entry to the crossing fill.
  * RECONCILE NOW ACTS: a RED verdict previously returned a dict while
    trading continued. Mismatch now writes the halt into the state itself
    (disarm + requires_reconciliation) atomically.
  * Added the supervised recovery path: adopt_broker_state() (broker is
    the source of truth) then resume_trading() -- two explicit steps, so a
    resync can never happen by accident.
  * Fills update CASH; zero-qty broker rows no longer fire false ORPHANs;
    float quantities compared with tolerance; datetime.utcnow() (removed
    in 3.12+ deprecation path) -> timezone-aware; emojis removed.

The atomic-write pattern (tmp + fsync + os.replace) from the draft was
correct and is kept.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

QTY_TOL = 1e-9          # fractional-share comparison tolerance


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateGatekeeper:
    """Crash-safe local book + the broker reality check."""

    def __init__(self, state_file: str | Path = ROOT / "state_snapshot.json"):
        self.state_file = Path(state_file)
        self.state = self._load_or_halt()

    # ------------------------------------------------------------------
    def _genesis(self, requires_reconciliation: bool = False) -> dict:
        return {
            "meta": {"version": "1.1", "created": _now()},
            "cash": 0.0,
            "positions": {},   # ticker -> {qty, entry_price, timestamp}
            "strategy": {
                "armed": not requires_reconciliation,
                "requires_reconciliation": requires_reconciliation,
                "halt_reason": ("state corruption -- reconcile with broker "
                                "before trading" if requires_reconciliation
                                else ""),
            },
        }

    def _load_or_halt(self) -> dict:
        if not self.state_file.exists():
            return self._genesis()
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            backup = self.state_file.with_suffix(
                f".CORRUPT.{int(time.time())}.json")
            shutil.copy(self.state_file, backup)
            print(f"CRITICAL: state file corrupt -> backed up to {backup.name}; "
                  f"trading DISARMED until reconciliation")
            state = self._genesis(requires_reconciliation=True)
            self._write(state)
            return state

    # ------------------------------------------------------------------
    def _write(self, state: dict) -> None:
        """Atomic write: tmp + fsync + os.replace (crash mid-write leaves
        the previous good state intact)."""
        state["meta"]["last_updated"] = _now()
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.state_file)

    def save_state(self) -> None:
        self._write(self.state)

    # ------------------------------------------------------------------
    @property
    def armed(self) -> bool:
        return bool(self.state["strategy"]["armed"])

    def get_position(self, ticker: str) -> float:
        """Signed local quantity, 0.0 if flat."""
        pos = self.state["positions"].get(ticker)
        return float(pos["qty"]) if pos else 0.0

    def _disarm(self, reason: str) -> None:
        self.state["strategy"]["armed"] = False
        self.state["strategy"]["requires_reconciliation"] = True
        self.state["strategy"]["halt_reason"] = reason
        self.save_state()

    # ------------------------------------------------------------------
    def update_position(self, ticker: str, qty: float, price: float,
                        side: str) -> None:
        """Book a fill. Signed ledger: same-direction adds average the
        entry; reductions keep it; crossing zero resets it to the fill."""
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")
        signed = qty if side == "BUY" else -qty
        pos = self.state["positions"].get(
            ticker, {"qty": 0.0, "entry_price": 0.0})
        old_qty, entry = float(pos["qty"]), float(pos["entry_price"])
        new_qty = old_qty + signed

        if old_qty == 0.0 or old_qty * signed > 0:
            # opening or adding in the same direction -> weighted average
            entry = ((abs(old_qty) * entry + abs(signed) * price)
                     / abs(new_qty)) if new_qty != 0 else 0.0
        elif old_qty * new_qty < 0:
            entry = price               # crossed through zero: fresh basis
        # pure reduction: entry unchanged

        self.state["cash"] -= signed * price
        if abs(new_qty) < QTY_TOL:
            self.state["positions"].pop(ticker, None)
        else:
            self.state["positions"][ticker] = {
                "qty": new_qty, "entry_price": entry, "timestamp": _now()}
        self.save_state()

    # ------------------------------------------------------------------
    def reconcile_with_broker(self, broker_positions: dict[str, float]) -> dict:
        """The reality check. Any mismatch DISARMS trading in the state
        itself -- the report is not advisory."""
        broker = {t: float(q) for t, q in broker_positions.items()
                  if abs(float(q)) > QTY_TOL}      # zero rows are not orphans
        local = {t: float(v["qty"]) for t, v in self.state["positions"].items()}

        mismatches = []
        for t, q in broker.items():
            if t not in local:
                mismatches.append(f"ORPHAN: broker holds {q} {t}, local NONE")
            elif abs(local[t] - q) > QTY_TOL:
                mismatches.append(
                    f"QTY MISMATCH: broker {q} {t} != local {local[t]}")
        for t, q in local.items():
            if t not in broker:
                mismatches.append(f"PHANTOM: local holds {q} {t}, broker NONE")

        if mismatches:
            self._disarm("reconciliation failed: " + "; ".join(mismatches))
            return {"status": "RED", "action": "HALT_TRADING",
                    "reason": mismatches}

        self.state["strategy"]["requires_reconciliation"] = False
        self.save_state()
        return {"status": "GREEN", "reason": "state synchronized"}

    # ------------------------------------------------------------------
    def adopt_broker_state(self, broker_positions: dict[str, float],
                           prices: dict[str, float] | None = None) -> None:
        """Supervised recovery step 1: the BROKER is the source of truth.
        Overwrites the local book (entry basis from `prices` if supplied,
        else 0.0 flagged as unknown). Trading stays DISARMED until the
        operator explicitly calls resume_trading()."""
        prices = prices or {}
        self.state["positions"] = {
            t: {"qty": float(q),
                "entry_price": float(prices.get(t, 0.0)),
                "timestamp": _now()}
            for t, q in broker_positions.items() if abs(float(q)) > QTY_TOL}
        self.state["strategy"]["requires_reconciliation"] = False
        self.state["strategy"]["halt_reason"] = (
            "adopted broker state -- awaiting explicit resume_trading()")
        self.save_state()

    def resume_trading(self) -> None:
        """Supervised recovery step 2: explicit re-arm. Refuses while a
        reconciliation is still owed."""
        if self.state["strategy"]["requires_reconciliation"]:
            raise RuntimeError("cannot re-arm: reconciliation still required")
        self.state["strategy"]["armed"] = True
        self.state["strategy"]["halt_reason"] = ""
        self.save_state()


# ---------------------------------------------------------------------------
def demo() -> None:
    path = ROOT / "logs" / "demo_state.json"
    path.unlink(missing_ok=True)

    gate = StateGatekeeper(path)
    gate.update_position("SPY", 10, 400.50, "BUY")
    print(f"booked: {gate.state['positions']['SPY']} | cash {gate.state['cash']}")

    reloaded = StateGatekeeper(path)               # simulated crash + reload
    print(f"reloaded after crash: {reloaded.state['positions']['SPY']}")

    print(f"reconcile (match): "
          f"{reloaded.reconcile_with_broker({'SPY': 10})['status']}")

    verdict = reloaded.reconcile_with_broker({"SPY": 15})
    print(f"reconcile (mismatch): {verdict['status']} -> armed = "
          f"{reloaded.armed}")
    for m in verdict["reason"]:
        print(f"    {m}")

    reloaded.adopt_broker_state({"SPY": 15}, prices={"SPY": 402.0})
    print(f"adopted broker truth: {reloaded.state['positions']['SPY']} "
          f"| armed = {reloaded.armed}")
    reloaded.resume_trading()
    print(f"explicit resume: armed = {reloaded.armed}")
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    demo()
