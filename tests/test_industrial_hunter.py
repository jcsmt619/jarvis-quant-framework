"""
tests/test_industrial_hunter.py
===============================
Double-blind protocol mechanics (offline, synthetic -- no network):
window boundaries can't leak, factor-blob guard caps the luck factory,
gauntlet adapter honors its contract, and the pipeline runs end-to-end.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.industrial_hunter import (
    GAUNTLET_A_START,
    IndustrialHunter,
    PERIOD_2_START,
    candidates_from_clusters,
    protocol_windows,
    run_gauntlet,
)


@pytest.fixture(scope="module")
def synthetic_prices() -> pd.DataFrame:
    """6 tickers, 2018-2026 business days: AA/BB cointegrated (shared random
    walk), CC/DD share a weaker factor, EE/FF independent noise."""
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2018-01-02", "2026-06-30")
    n = len(idx)
    core = np.cumsum(rng.normal(0, 0.01, n))
    factor = np.cumsum(rng.normal(0, 0.01, n))
    px = pd.DataFrame({
        "AA": 100 * np.exp(core + rng.normal(0, 0.002, n)),
        "BB": 120 * np.exp(core + rng.normal(0, 0.002, n)),
        "CC": 80 * np.exp(0.6 * factor + np.cumsum(rng.normal(0, 0.008, n))),
        "DD": 90 * np.exp(0.6 * factor + np.cumsum(rng.normal(0, 0.008, n))),
        "EE": 50 * np.exp(np.cumsum(rng.normal(0, 0.012, n))),
        "FF": 60 * np.exp(np.cumsum(rng.normal(0, 0.012, n))),
    }, index=idx)
    return px


def test_windows_do_not_leak(synthetic_prices):
    """Formation ends before Gate A trading; warmup prefix stops exactly at
    the trade boundary; Gate A trading ends before Gate B trading."""
    w = protocol_windows(synthetic_prices.index, warmup=273)
    idx = synthetic_prices.index
    formation = idx[w["formation"]]
    assert formation[-1] < pd.Timestamp(GAUNTLET_A_START)
    assert idx[w["a_trade_start"]] >= pd.Timestamp(GAUNTLET_A_START)
    assert idx[w["b_trade_start"]] >= pd.Timestamp(PERIOD_2_START)
    # Warmup prefix of Gate A reaches back exactly 273 bars, no further.
    gate_a = idx[w["gate_a"]]
    assert list(idx).index(gate_a[0]) == w["a_trade_start"] - 273
    # Gate A slice stops where Gate B trading starts (no shared trading bars).
    assert gate_a[-1] < idx[w["b_trade_start"]]


def test_blob_guard_caps_factor_clusters():
    rng = np.random.default_rng(0)
    blob = [f"T{i:02d}" for i in range(20)]          # 20 members -> 190 raw pairs
    small = ["XA", "XB", "XC"]
    labels = {t: 0 for t in blob} | {t: 1 for t in small} | {"NN": -1}
    rets = pd.DataFrame(rng.normal(0, 0.01, (100, 24)),
                        columns=blob + small + ["NN"])
    cands = candidates_from_clusters(labels, rets, max_cluster=12,
                                     blob_top=20, cap=400)
    blob_pairs = [p for p in cands if p[0] in blob and p[1] in blob]
    small_pairs = [p for p in cands if p[0] in small or p[1] in small]
    assert len(blob_pairs) == 20                     # capped, not 190
    assert len(small_pairs) == 3                     # C(3,2) all kept
    assert not any("NN" in p for p in cands)         # noise label excluded
    # Cross-cluster pairs must never appear.
    assert all((a in blob) == (b in blob) for a, b in cands)


def test_global_candidate_cap():
    rng = np.random.default_rng(1)
    members = [f"S{i:02d}" for i in range(10)]       # C(10,2) = 45 pairs
    labels = {t: 0 for t in members}
    rets = pd.DataFrame(rng.normal(0, 0.01, (100, 10)), columns=members)
    assert len(candidates_from_clusters(labels, rets, cap=7)) == 7


def test_gauntlet_adapter_contract(synthetic_prices):
    r = run_gauntlet(synthetic_prices["AA"].iloc[:800],
                     synthetic_prices["BB"].iloc[:800])
    for key in ("verdict", "cagr", "net_return", "max_dd", "sharpe",
                "n_trades", "risk_of_ruin", "fail_reason", "equity"):
        assert key in r
    assert r["verdict"] in ("FUNDABLE", "DEAD")
    assert isinstance(r["equity"], pd.Series) and len(r["equity"]) > 0


def test_pipeline_end_to_end_offline(synthetic_prices):
    """Full double-blind run on injected prices: Gate B only re-tests Gate A
    survivors, confirmed rows carry a deflated-Sharpe stamp."""
    hunter = IndustrialHunter(tickers=list(synthetic_prices.columns))
    hunter.prices = synthetic_prices                 # bypass network
    out = hunter.run()
    assert out["n_candidates"] >= 1                  # AA/BB must cluster together
    a_survivors = {r["pair"] for r in out["gate_a"] if r["verdict"] == "FUNDABLE"}
    assert {r["pair"] for r in out["gate_b"]} == a_survivors
    for row in out["confirmed"]:
        assert {"psr", "dsr", "dsr_verdict"} <= set(row)
        assert 0.0 <= row["dsr"] <= 1.0
