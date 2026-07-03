"""
tests/test_structural_arb.py
============================
Offline mechanics: the ex-ante list is well-formed, the runner honors the
engine contract on a synthetic dual-class pair, borrow sensitivity moves
the right direction, and FUNDABLEs get a real DSR stamp.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.structural_arb import (
    STRUCTURAL_PAIRS,
    run_pipeline,
    run_structural,
)


@pytest.fixture(scope="module")
def dual_class() -> pd.DataFrame:
    """Synthetic dual-class: same random walk, class B trades at a slowly
    oscillating discount plus idiosyncratic noise -- wide enough to clear
    the degenerate-spread guard and mean-reverting by construction."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2021-07-01", "2026-06-30")
    n = len(idx)
    walk = np.cumsum(rng.normal(0.0002, 0.012, n))
    premium = 0.06 * np.sin(np.linspace(0, 14 * np.pi, n))
    a = 100 * np.exp(walk)
    b = 100 * np.exp(walk) * (0.92 + premium) + rng.normal(0, 0.4, n)
    return pd.DataFrame({"AA": a, "AB": b}, index=idx)


def test_pair_list_is_well_formed():
    seen = set()
    for a, b, note in STRUCTURAL_PAIRS:
        assert a != b
        key = frozenset((a, b))
        assert key not in seen           # no duplicate pairs
        seen.add(key)
        assert note                      # every pair declares its linkage


def test_runner_contract_and_trades(dual_class):
    r = run_structural(dual_class["AA"], dual_class["AB"], borrow_annual=0.03)
    for key in ("verdict", "net_return", "max_dd", "sharpe", "n_trades",
                "risk_of_ruin", "fail_reason", "equity"):
        assert key in r
    assert r["n_trades"] > 0             # oscillating premium must trade


def test_borrow_sensitivity_direction(dual_class):
    """Higher borrow can never make the same trade sequence MORE profitable."""
    gc = run_structural(dual_class["AA"], dual_class["AB"], borrow_annual=0.005)
    hi = run_structural(dual_class["AA"], dual_class["AB"], borrow_annual=0.03)
    assert hi["net_return"] <= gc["net_return"] + 1e-9


def test_pipeline_offline_dsr_stamp(dual_class):
    out = run_pipeline(prices=dual_class,
                       pairs=[("AA", "AB", "synthetic twin"),
                              ("AA", "ZZ", "missing leg")])
    assert out["n_trials"] == 2          # honest N includes the unpriceable pair
    assert out["skipped"] == ["AA/ZZ"]
    (row,) = out["results"]
    if row["verdict"] == "FUNDABLE":
        assert {"psr", "dsr", "dsr_verdict"} <= set(row)
        assert 0.0 <= row["dsr"] <= 1.0
    else:
        assert row["fail_reason"]        # DEAD must say why
