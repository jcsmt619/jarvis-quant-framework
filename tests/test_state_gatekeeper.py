"""
tests/test_state_gatekeeper.py
==============================
The go-live contract: crash-safe persistence, corruption -> DISARM (never
a silent blank slate), a signed ledger that survives shorts and zero
crossings, reconciliation that actually halts, and the two-step supervised
recovery.
"""

from __future__ import annotations

import json

import pytest

from utils.state_gatekeeper import StateGatekeeper


@pytest.fixture()
def gate(tmp_path) -> StateGatekeeper:
    return StateGatekeeper(tmp_path / "state.json")


def test_round_trip_persistence(tmp_path):
    g = StateGatekeeper(tmp_path / "s.json")
    g.update_position("SPY", 10, 400.0, "BUY")
    g2 = StateGatekeeper(tmp_path / "s.json")          # crash + reload
    assert g2.state["positions"]["SPY"]["qty"] == 10
    assert g2.state["cash"] == pytest.approx(-4000.0)


def test_corruption_disarms_never_resets_silently(tmp_path):
    p = tmp_path / "s.json"
    g = StateGatekeeper(p)
    g.update_position("SPY", 10, 400.0, "BUY")
    p.write_text("{ this is not json", encoding="utf-8")
    g2 = StateGatekeeper(p)
    assert g2.armed is False                            # DISARMED, not blank-slate
    assert g2.state["strategy"]["requires_reconciliation"] is True
    backups = list(tmp_path.glob("*.CORRUPT.*"))
    assert len(backups) == 1                            # forensics preserved
    with pytest.raises(RuntimeError):
        g2.resume_trading()                             # can't re-arm unreconciled


def test_ledger_long_short_and_zero_crossing(gate):
    # open long, add (weighted average)
    gate.update_position("X", 10, 100.0, "BUY")
    gate.update_position("X", 10, 110.0, "BUY")
    assert gate.state["positions"]["X"]["entry_price"] == pytest.approx(105.0)
    # partial reduction never touches the entry
    gate.update_position("X", 5, 120.0, "SELL")
    assert gate.state["positions"]["X"]["entry_price"] == pytest.approx(105.0)
    # cross through zero: fresh basis at the crossing fill
    gate.update_position("X", 25, 130.0, "SELL")
    pos = gate.state["positions"]["X"]
    assert pos["qty"] == pytest.approx(-10)
    assert pos["entry_price"] == pytest.approx(130.0)
    # covering the short (reduction) keeps the short entry -- the draft's
    # buy-side averaging on negative qty produced nonsense here
    gate.update_position("X", 5, 125.0, "BUY")
    assert gate.state["positions"]["X"]["entry_price"] == pytest.approx(130.0)
    # full close removes the row
    gate.update_position("X", 5, 125.0, "BUY")
    assert "X" not in gate.state["positions"]


def test_fresh_short_has_real_entry_price(gate):
    gate.update_position("Y", 10, 50.0, "SELL")
    pos = gate.state["positions"]["Y"]
    assert pos["qty"] == pytest.approx(-10)
    assert pos["entry_price"] == pytest.approx(50.0)    # draft left 0.0


def test_reconcile_mismatch_halts_in_state(gate):
    gate.update_position("SPY", 10, 400.0, "BUY")
    verdict = gate.reconcile_with_broker({"SPY": 15})
    assert verdict["status"] == "RED"
    assert gate.armed is False                          # halt WRITTEN, not advisory
    assert any("QTY MISMATCH" in m for m in verdict["reason"])


def test_reconcile_orphan_phantom_and_zero_rows(gate):
    gate.update_position("AAA", 5, 10.0, "BUY")
    verdict = gate.reconcile_with_broker({"BBB": 3, "CCC": 0.0})
    reasons = " | ".join(verdict["reason"])
    assert "ORPHAN" in reasons and "BBB" in reasons     # broker-only position
    assert "PHANTOM" in reasons and "AAA" in reasons    # local-only position
    assert "CCC" not in reasons                         # zero rows ignored


def test_supervised_recovery_two_steps(gate):
    gate.update_position("SPY", 10, 400.0, "BUY")
    gate.reconcile_with_broker({"SPY": 15})             # RED -> disarmed
    gate.adopt_broker_state({"SPY": 15}, prices={"SPY": 402.0})
    assert gate.state["positions"]["SPY"]["qty"] == 15
    assert gate.armed is False                          # adoption does NOT re-arm
    assert gate.reconcile_with_broker({"SPY": 15})["status"] == "GREEN"
    gate.resume_trading()                               # explicit second step
    assert gate.armed is True


def test_atomic_tmp_leftover_ignored(tmp_path):
    p = tmp_path / "s.json"
    g = StateGatekeeper(p)
    g.update_position("SPY", 10, 400.0, "BUY")
    (tmp_path / "s.tmp").write_text("garbage from a crash mid-write",
                                    encoding="utf-8")
    g2 = StateGatekeeper(p)                             # tmp must not be read
    assert g2.state["positions"]["SPY"]["qty"] == 10
