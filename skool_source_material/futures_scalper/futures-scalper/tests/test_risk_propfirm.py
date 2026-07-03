"""Risk is the gatekeeper, so the tests are blunt: sizing must match the
hand-calculated contract count, the daily loss limit must halt the session, and
a trailing-drawdown breach must lock the account and write the lock file.
"""

from pathlib import Path

import pandas as pd
import pytest

from core.instruments import get_instrument
from core.risk_manager import AccountState, HaltLevel, RiskManager
from core.scalp_strategies import Direction, Signal


def _signal(direction=Direction.LONG, entry=18000.0, stop=17990.0, target=18020.0):
    return Signal(symbol="MNQ", direction=direction, confidence=0.7, entry_price=entry,
                  stop_price=stop, target_price=target, stop_ticks=40, target_ticks=80,
                  regime_id=1, regime_name="NORMAL", regime_probability=0.7,
                  timestamp=pd.Timestamp.now(tz="UTC"), reasoning="test", strategy_name="t")


def _account(equity=50000.0):
    return AccountState(equity=equity, starting_equity=equity,
                        session_start_equity=equity, high_water_mark=equity)


def test_contract_sizing_matches_risk_budget():
    # MNQ: stop 10 points = 40 ticks * $0.50 = $20 risk per contract.
    # risk_per_trade 0.01 of 50k = $500 -> 25 by risk, but capped by max_contracts.
    rm = RiskManager({"risk_per_trade": 0.01, "max_contracts": 25,
                      "max_margin_utilization": 1.0, "prop_firm": {"enabled": False}})
    n, notes = rm.size_contracts(_account(), _signal(), get_instrument("MNQ"))
    assert n == 25


def test_hard_contract_cap_applies():
    rm = RiskManager({"risk_per_trade": 0.05, "max_contracts": 3,
                      "max_margin_utilization": 1.0, "prop_firm": {"enabled": False}})
    n, _ = rm.size_contracts(_account(), _signal(), get_instrument("MNQ"))
    assert n == 3


def test_margin_cap_applies():
    # Small account, MNQ day margin 180 -> margin cap dominates.
    rm = RiskManager({"risk_per_trade": 0.5, "max_contracts": 100,
                      "max_margin_utilization": 0.5, "prop_firm": {"enabled": False}})
    n, notes = rm.size_contracts(_account(equity=1000), _signal(), get_instrument("MNQ"))
    assert n == 2  # floor(500 / 180)


def test_rejects_missing_stop():
    rm = RiskManager({"prop_firm": {"enabled": False}})
    sig = _signal(stop=0.0)
    d = rm.validate_signal(_account(), sig, get_instrument("MNQ"))
    assert not d.approved


def test_rejects_wrong_side_stop():
    rm = RiskManager({"prop_firm": {"enabled": False}})
    sig = _signal(direction=Direction.LONG, entry=18000, stop=18010)  # stop above entry on a long
    d = rm.validate_signal(_account(), sig, get_instrument("MNQ"))
    assert not d.approved


def test_daily_loss_limit_halts_session():
    rm = RiskManager({"prop_firm": {"enabled": True, "daily_loss_limit": 1000,
                                    "trailing_max_drawdown": 0}})
    acct = _account(50000)
    rm.start_session(acct)
    acct.equity = 48900  # down 1100 > 1000
    rm.update_after_fill_or_mark(acct)
    assert rm.breaker.level is HaltLevel.HALTED_SESSION
    d = rm.validate_signal(acct, _signal(), get_instrument("MNQ"))
    assert not d.approved


def test_daily_loss_reduce_halves_size():
    rm = RiskManager({"risk_per_trade": 0.01, "max_contracts": 100,
                      "max_margin_utilization": 1.0,
                      "prop_firm": {"enabled": True, "daily_loss_limit": 1000,
                                    "daily_loss_reduce_at": 0.6, "trailing_max_drawdown": 0}})
    acct = _account(50000)
    rm.start_session(acct)
    acct.equity = 49300  # down 700, past 60% of 1000
    rm.update_after_fill_or_mark(acct)
    assert rm.breaker.level is HaltLevel.REDUCED
    assert rm.breaker.size_multiplier == 0.5


def test_trailing_drawdown_locks_and_writes_file(tmp_path):
    lock = tmp_path / "halt.lock"
    rm = RiskManager({"prop_firm": {"enabled": True, "daily_loss_limit": 0,
                                    "trailing_max_drawdown": 2000,
                                    "trailing_locks_at_start": True,
                                    "lock_file": str(lock)}})
    acct = _account(50000)
    acct.equity = 51000
    rm.update_after_fill_or_mark(acct)   # new high-water mark 51000
    acct.equity = 48900                  # 2100 below the mark > 2000
    rm.update_after_fill_or_mark(acct)
    assert rm.breaker.level is HaltLevel.HALTED_LOCKED
    assert lock.exists()


def test_flat_signal_always_approved():
    rm = RiskManager({"prop_firm": {"enabled": False}})
    sig = _signal(direction=Direction.FLAT)
    d = rm.validate_signal(_account(), sig, get_instrument("MNQ"))
    assert d.approved
