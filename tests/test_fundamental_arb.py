"""
tests/test_fundamental_arb.py
=============================
Point-in-time protocol mechanics (offline, no network): vintage column
selection can't reach past the cutoff, ratio math is right, the cleaner
keeps bank-like firms, and twin generation respects cluster walls + caps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.fundamental_arb import (
    build_features,
    clean_matrix,
    pick_vintage,
    twin_candidates,
)


def _stmt(rows: dict, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.to_datetime(cols)).T


def test_pick_vintage_respects_cutoff():
    cols = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31", "2021-12-31"]
    stmt = _stmt({"Total Revenue": [5, 4, 3, 2, 1]}, cols)
    fy, prior = pick_vintage(stmt, cutoff="2023-03-31")
    assert fy == pd.Timestamp("2022-12-31")      # NOT 2023/2024/2025
    assert prior == pd.Timestamp("2021-12-31")
    # Only post-cutoff data available -> unusable, not silently leaked.
    young = _stmt({"Total Revenue": [5, 4]}, ["2025-12-31", "2024-12-31"])
    assert pick_vintage(young, cutoff="2023-03-31") is None


def test_build_features_ratio_math():
    cols = ["2022-12-31", "2021-12-31"]
    inc = _stmt({"Net Income": [10.0, 8.0], "Total Revenue": [100.0, 80.0],
                 "EBITDA": [25.0, 20.0]}, cols)
    bs = _stmt({"Stockholders Equity": [50.0, 45.0], "Total Debt": [30.0, 30.0],
                "Current Assets": [40.0, 35.0], "Current Liabilities": [20.0, 18.0],
                "Cash And Cash Equivalents": [5.0, 4.0],
                "Ordinary Shares Number": [10.0, 10.0]}, cols)
    f = build_features(inc, bs, price_formation=20.0)   # mktcap = 200
    assert f["pe"] == pytest.approx(20.0)               # 200 / 10
    assert f["pb"] == pytest.approx(4.0)                # 200 / 50
    assert f["ev_ebitda"] == pytest.approx((200 + 30 - 5) / 25)
    assert f["debt_to_equity"] == pytest.approx(0.6)
    assert f["current_ratio"] == pytest.approx(2.0)
    assert f["profit_margin"] == pytest.approx(0.10)
    assert f["roe"] == pytest.approx(0.20)
    assert f["revenue_growth"] == pytest.approx(0.25)
    # Unpriceable firm (no formation price) must drop, not fabricate.
    assert build_features(inc, bs, price_formation=np.nan) is None


def test_clean_matrix_keeps_banks_drops_outliers():
    """A metric missing for most firms (banks: no current ratio) is dropped
    as a COLUMN so the firms survive; extreme PE is winsorized."""
    rng = np.random.default_rng(0)
    m = pd.DataFrame({
        "pe": np.append(rng.normal(15, 3, 199), 10_000.0),   # one absurd PE
        "roe": rng.normal(0.15, 0.05, 200),
        "current_ratio": [np.nan] * 120 + list(rng.normal(2, 0.3, 80)),
    }, index=[f"F{i}" for i in range(200)])
    out = clean_matrix(m, max_col_missing=0.40)
    assert "current_ratio" not in out.columns       # 60% missing -> dropped
    assert len(out) == 200                          # the 120 "banks" survive
    assert out["pe"].max() < 100                    # winsorized


def test_twin_candidates_walls_and_caps():
    rng = np.random.default_rng(1)
    # Two tight twin groups far apart + scattered noise.
    twins_a = pd.DataFrame(rng.normal(0, 0.01, (3, 4)) + 5.0,
                           index=["A1", "A2", "A3"])
    twins_b = pd.DataFrame(rng.normal(0, 0.01, (3, 4)) - 5.0,
                           index=["B1", "B2", "B3"])
    noise = pd.DataFrame(rng.normal(0, 30.0, (6, 4)),
                         index=[f"N{i}" for i in range(6)])
    matrix = pd.concat([twins_a, twins_b, noise])
    matrix.columns = ["pe", "pb", "roe", "debt_to_equity"]
    cands, clusters = twin_candidates(matrix, cap=300)
    assert len(cands) >= 2
    # Invariant: every pair lives inside ONE OPTICS cluster (no cross-cluster
    # pairs, no noise members).
    member_sets = [set(v) for v in clusters.values()]
    assert all(any({a, b} <= s for s in member_sets) for a, b in cands)
    assert not any(t.startswith("N") and all(t not in s for s in member_sets)
                   for pair in cands for t in pair)
    # Closest-twins-first: the first candidate is a genuine twin pair, not noise.
    assert cands[0][0][0] == cands[0][1][0] and cands[0][0][0] in "AB"
    # Global cap binds.
    capped, _ = twin_candidates(matrix, cap=1)
    assert len(capped) == 1
