"""
backtest/cpcv.py
================
Combinatorial Purged Cross-Validation (CPCV) -- Lopez de Prado, ch.12.

Partition the timeline into N groups, hold out every combination of k
groups as test, purge training samples whose LABEL INTERVALS overlap any
test group, embargo a buffer of bars after each test block -- then stitch
the C(N,k) splits into phi = k*C(N,k)/N complete out-of-sample backtest
PATHS. The output is a performance DISTRIBUTION, not a point estimate.

Corrections vs the draft this was adapted from:
  * MERGED-SPAN PURGE BUG: the draft treated the k test groups as ONE
    contiguous window [min(test), max(test)]. With non-adjacent groups
    (say {0, 5} of 6) that purges every training group in between -- the
    training set collapses to almost nothing. Purging here is PER TEST
    BLOCK: a train sample dies only if its own label interval genuinely
    overlaps a test block's label window.
  * NO PATHS: the draft yielded splits and stopped. The entire point of
    CPCV is the path reconstruction (each group's test occurrences across
    splits are numbered; occurrence j of every group is stitched into
    path j) so you get phi full OOS equity curves and a Sharpe
    DISTRIBUTION. Implemented in `backtest_paths()`.
  * Embargo was converted to CALENDAR DAYS via Timedelta -- wrong for
    business-day or intraday indices. Embargo here is in BARS, applied
    positionally after each test block's label end.
  * `t1.shift(0)` no-op, prints inside the generator, emojis removed;
    the demo now PROVES the purge (asserts zero train/test label overlap)
    instead of just counting dropped rows.

Run:  python backtest/cpcv.py            (SPY demo, local CSV, no network)
"""

from __future__ import annotations

import sys
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class CPCV:
    """Combinatorial purged CV split generator + path assembler.

    Parameters
    ----------
    n_groups : total contiguous partitions of the timeline (N).
    n_test_groups : partitions held out per split (k).
    embargo_pct : fraction of the sample dropped AFTER each test block
        (converted to bars).
    """

    def __init__(self, n_groups: int = 6, n_test_groups: int = 2,
                 embargo_pct: float = 0.01):
        if not 0 < n_test_groups < n_groups:
            raise ValueError("need 0 < k < N")
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.embargo_pct = embargo_pct

    # ------------------------------------------------------------------
    @property
    def n_splits(self) -> int:
        return comb(self.n_groups, self.n_test_groups)

    @property
    def n_paths(self) -> int:
        """phi = k * C(N,k) / N complete out-of-sample paths."""
        return self.n_test_groups * self.n_splits // self.n_groups

    def group_bounds(self, n_samples: int) -> list[tuple[int, int]]:
        b = np.linspace(0, n_samples, self.n_groups + 1).astype(int)
        return [(int(b[i]), int(b[i + 1])) for i in range(self.n_groups)]

    # ------------------------------------------------------------------
    @staticmethod
    def _t1_positions(n_samples: int, t1, index: pd.Index | None) -> np.ndarray:
        """Label-end POSITION for each sample. t1=None -> point labels
        (label ends at its own bar). Datetime t1 values are converted via
        searchsorted on the supplied index."""
        if t1 is None:
            return np.arange(n_samples)
        vals = np.asarray(t1.values if isinstance(t1, pd.Series) else t1)
        if np.issubdtype(vals.dtype, np.datetime64) or isinstance(
                vals.flat[0], pd.Timestamp):
            if index is None:
                raise ValueError("datetime t1 requires the sample index")
            pos = np.asarray(pd.Index(index).searchsorted(vals))
        else:
            pos = vals.astype(int)
        return np.clip(pos, 0, n_samples - 1)

    def split(self, n_samples: int, t1=None, index: pd.Index | None = None):
        """Yield (split_id, test_group_ids, train_idx, test_idx).

        Purge rule, applied PER TEST BLOCK [a, b): a training sample i is
        removed iff its label interval [i, t1_i] overlaps the block's
        label window [a, max(t1[a:b])], or i falls inside the embargo of
        `embargo_bars` bars after that window.
        """
        t1_pos = self._t1_positions(n_samples, t1, index)
        embargo = int(n_samples * self.embargo_pct)
        bounds = self.group_bounds(n_samples)
        all_idx = np.arange(n_samples)

        for sid, test_groups in enumerate(
                combinations(range(self.n_groups), self.n_test_groups)):
            test_mask = np.zeros(n_samples, dtype=bool)
            dead_mask = np.zeros(n_samples, dtype=bool)
            for g in test_groups:
                a, b = bounds[g]
                test_mask[a:b] = True
                label_end = int(t1_pos[a:b].max())
                # Purge: train label interval [i, t1_i] overlaps [a, label_end].
                overlap = (all_idx <= label_end) & (t1_pos >= a)
                # Embargo: bars immediately after the block's label window.
                emb = (all_idx > label_end) & (all_idx <= label_end + embargo)
                dead_mask |= overlap | emb
            train_idx = all_idx[~test_mask & ~dead_mask]
            yield sid, test_groups, train_idx, all_idx[test_mask]

    # ------------------------------------------------------------------
    def backtest_paths(self) -> list[list[tuple[int, int]]]:
        """phi paths, each a list of (group_id, split_id) covering every
        group exactly once: occurrence j of group g across the splits
        where g is in test belongs to path j (Lopez de Prado's stitching)."""
        occurrences: dict[int, list[int]] = {g: [] for g in range(self.n_groups)}
        for sid, test_groups in enumerate(
                combinations(range(self.n_groups), self.n_test_groups)):
            for g in test_groups:
                occurrences[g].append(sid)
        return [[(g, occurrences[g][j]) for g in range(self.n_groups)]
                for j in range(self.n_paths)]


# ---------------------------------------------------------------------------
def demo(horizon: int = 5) -> dict:
    """CPCV on a toy causal momentum model over local SPY data: fit per
    split on purged train bars, predict the held-out groups, stitch the
    phi paths, report the Sharpe DISTRIBUTION -- the deliverable the
    point-estimate backtest can't give you."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    px = pd.read_csv(ROOT / "data" / "raw" / "spy.csv", parse_dates=["date"]
                     ).set_index("date")["Close"]
    rets = px.pct_change()
    X = pd.DataFrame({
        "mom5": px.pct_change(5),
        "mom20": px.pct_change(20),
        "vol20": rets.rolling(20).std(),
    }).shift(1)                                   # features known at t-1
    fwd = px.pct_change(horizon).shift(-horizon)  # label: forward h-day return
    data = pd.concat([X, fwd.rename("fwd")], axis=1).dropna()
    n = len(data)
    t1 = pd.Series(np.minimum(np.arange(n) + horizon, n - 1))  # label spans h bars

    cv = CPCV(n_groups=6, n_test_groups=2, embargo_pct=0.01)
    preds = {}                                    # (group, split) -> pd.Series
    bounds = cv.group_bounds(n)
    group_of = np.searchsorted([b for _, b in bounds], np.arange(n), side="right")

    feats = ["mom5", "mom20", "vol20"]
    for sid, test_groups, tr, te in cv.split(n, t1=t1):
        model = make_pipeline(StandardScaler(),
                              LogisticRegression(max_iter=1000))
        model.fit(data.iloc[tr][feats], (data.iloc[tr]["fwd"] > 0).astype(int))
        # Long/short vs the TRAIN-median probability (causal threshold);
        # a raw 0.5 cut degenerates to always-long on an up-drifting index.
        thr = float(np.median(model.predict_proba(data.iloc[tr][feats])[:, 1]))
        proba = model.predict_proba(data.iloc[te][feats])[:, 1]
        sig = np.where(proba > thr, 1.0, -1.0)
        pnl = pd.Series(sig * data.iloc[te]["fwd"].to_numpy() / horizon,
                        index=te)
        for g in test_groups:
            preds[(g, sid)] = pnl[group_of[te] == g]

    path_sharpes = []
    for path in cv.backtest_paths():
        pnl = pd.concat([preds[(g, sid)] for g, sid in path]).sort_index()
        sd = pnl.std()
        path_sharpes.append(float(pnl.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0)

    s = np.array(path_sharpes)
    out = {"n_splits": cv.n_splits, "n_paths": cv.n_paths,
           "sharpes": [round(x, 3) for x in path_sharpes],
           "mean": float(s.mean()), "std": float(s.std()),
           "min": float(s.min()), "max": float(s.max()),
           "pct_positive": float((s > 0).mean())}

    print("CPCV DEMO -- toy momentum on SPY (local CSV, causal features)")
    print(f"  N=6, k=2 -> {out['n_splits']} splits -> {out['n_paths']} "
          f"full OOS paths (label span {horizon} bars, purged + embargoed)")
    print(f"  path Sharpes: {out['sharpes']}")
    print(f"  distribution: mean {out['mean']:+.2f} | std {out['std']:.2f} | "
          f"range [{out['min']:+.2f}, {out['max']:+.2f}] | "
          f"{out['pct_positive']:.0%} of paths positive")
    print("  READ: a single-backtest Sharpe is ONE draw from this "
          "distribution. If the")
    print("  range straddles zero, the point estimate was never evidence.")
    return out


if __name__ == "__main__":
    demo()
