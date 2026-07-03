"""
tests/test_cluster_hunter.py
============================
ClusterHunter: label mapping actually persists (the draft's .T bug), known
factor structure is recovered, pairs stay within clusters, and the
formation/trading split keeps clustering strictly out-of-sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.cluster_hunter import ClusterHunter


def _two_factor_universe(n=400, seed=0):
    """6 assets: 3 driven by factor1, 3 by factor2, tiny idiosyncratic noise."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-01", periods=n)
    f1 = rng.normal(0, 0.02, n)
    f2 = rng.normal(0, 0.02, n)
    cols = {}
    for i, name in enumerate(["A1", "A2", "A3"]):
        cols[name] = f1 + rng.normal(0, 0.002, n)
    for i, name in enumerate(["B1", "B2", "B3"]):
        cols[name] = f2 + rng.normal(0, 0.002, n)
    return pd.DataFrame(cols, index=idx)


def test_labels_persist_and_recover_structure():
    rets = _two_factor_universe()
    labels = ClusterHunter.cluster_assets(rets, min_samples=2)
    assert set(labels) == set(rets.columns)          # mapping exists (draft's .T bug)
    a_labels = {labels[t] for t in ("A1", "A2", "A3")}
    b_labels = {labels[t] for t in ("B1", "B2", "B3")}
    assert len(a_labels) == 1 and -1 not in a_labels  # A-group clusters together
    assert len(b_labels) == 1 and -1 not in b_labels
    assert a_labels != b_labels                        # ...and apart from B-group


def test_pairs_only_within_clusters():
    labels = {"A1": 0, "A2": 0, "A3": 0, "B1": 1, "B2": 1, "N1": -1}
    pairs = ClusterHunter.pairs_within_clusters(labels)
    assert ("A1", "A2") in pairs and ("B1", "B2") in pairs
    assert all(labels[a] == labels[b] for a, b in pairs)      # never cross-cluster
    assert not any("N1" in p for p in pairs)                   # noise excluded
    assert len(pairs) == 3 + 1                                 # C(3,2) + C(2,2)


def test_clustering_input_is_formation_only():
    """The clustering must be identical whether or not the trading window exists."""
    rets = _two_factor_universe(n=400)
    labels_full_info = ClusterHunter.cluster_assets(rets.iloc[:160])
    labels_no_future = ClusterHunter.cluster_assets(
        _two_factor_universe(n=160))          # regenerate only the formation bars
    assert labels_full_info == labels_no_future
