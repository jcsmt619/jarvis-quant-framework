"""
analysis/linear_baseline.py
===========================
The white-box yardstick (build-library prompt #4): a regularized logistic
baseline every complex model must beat. If the GBM can't out-predict a
scaled, C-tuned logistic regression, the GBM's "edge" is overfit noise.

Corrections vs the draft this was adapted from:
  * FALSE TEMPORAL CLAIM: the docstring said "auto-tunes C via TimeSeries
    CV" but `LogisticRegressionCV(cv=5)` uses STRATIFIED K-FOLD -- shuffled
    folds on a time series, so the C-search trains on the future of its own
    validation folds. Now genuinely TimeSeriesSplit.
  * NO PURGE AT THE SPLIT BOUNDARY: with triple-barrier labels spanning h
    bars, train labels adjacent to the cutoff overlap the test window (the
    leak CPCV exists to kill). `audit(..., t1=...)` purges any train sample
    whose label interval reaches the test window, plus an optional embargo.
  * NO BASELINE FOR THE BASELINE: accuracy without the majority-class base
    rate is meaningless (58% accuracy on a 58% base rate = zero skill).
    Reported as `majority_baseline` and `skill`.
  * Multiclass AUC crashed when the test window missed a class -> guarded.
  * Bare `except: pass`, unseeded leaky demo, emojis removed.

Run:  python analysis/linear_baseline.py   (SPY + triple-barrier demo)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class LinearBaseline:
    """Regularized logistic audit model with honest temporal hygiene."""

    def __init__(self, cv_splits: int = 5, penalty: str = "l2",
                 embargo_bars: int = 0):
        self.cv_splits = cv_splits
        self.penalty = penalty
        self.embargo_bars = embargo_bars
        self.model = None

    # ------------------------------------------------------------------
    def pipeline(self):
        from sklearn.linear_model import LogisticRegressionCV
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        clf = LogisticRegressionCV(
            cv=TimeSeriesSplit(n_splits=self.cv_splits),   # temporal, really
            l1_ratios=(0.0 if self.penalty == "l2" else 1.0,),  # sklearn>=1.8 API
            solver="lbfgs" if self.penalty == "l2" else "saga",
            class_weight="balanced",
            scoring="neg_log_loss",
            max_iter=1000,
        )
        return Pipeline([("scaler", StandardScaler()), ("clf", clf)])

    # ------------------------------------------------------------------
    def audit(self, X: pd.DataFrame, y: pd.Series,
              t1: pd.Series | None = None, split_pct: float = 0.80) -> dict:
        """Chronological train/test audit with label-span purging.

        t1 : optional label-end times aligned to X.index (triple-barrier
        output). Train samples whose label interval reaches the test window
        are purged; `embargo_bars` more are dropped before the boundary.
        """
        cutoff = int(len(X) * split_pct)
        test_start = X.index[cutoff]

        train_mask = np.zeros(len(X), dtype=bool)
        train_mask[:cutoff] = True
        if self.embargo_bars:
            train_mask[max(0, cutoff - self.embargo_bars):cutoff] = False
        if t1 is not None:
            overlap = pd.Series(t1).reindex(X.index) >= test_start
            train_mask &= ~overlap.fillna(True).to_numpy()

        X_tr, y_tr = X.iloc[train_mask.nonzero()[0]], y.iloc[train_mask.nonzero()[0]]
        X_te, y_te = X.iloc[cutoff:], y.iloc[cutoff:]

        self.model = self.pipeline()
        self.model.fit(X_tr, y_tr)
        clf = self.model.named_steps["clf"]

        preds = self.model.predict(X_te)
        probs = self.model.predict_proba(X_te)

        from sklearn.metrics import accuracy_score, roc_auc_score
        acc = float(accuracy_score(y_te, preds))
        majority = float(y_te.value_counts(normalize=True).max())
        try:
            if len(clf.classes_) > 2:
                auc = float(roc_auc_score(y_te, probs, multi_class="ovr",
                                          labels=clf.classes_))
            else:
                auc = float(roc_auc_score(y_te, probs[:, 1]))
        except ValueError:                       # test window missing a class
            auc = float("nan")

        return {
            "accuracy": acc,
            "majority_baseline": majority,
            "skill": acc - majority,
            "auc": auc,
            "best_C": float(np.ravel(clf.C_)[0]),
            "classes": list(clf.classes_),
            "n_train": int(len(X_tr)),
            "n_test": int(len(X_te)),
            "n_purged": int(cutoff - len(X_tr)),
            "drivers": self.drivers(X.columns),
        }

    # ------------------------------------------------------------------
    def drivers(self, feature_names) -> pd.DataFrame:
        """Standardized coefficients for the most bullish class -- the
        interpretability that justifies the linear model's existence."""
        clf = self.model.named_steps["clf"]
        coefs = clf.coef_
        if coefs.ndim > 1 and len(clf.classes_) > 2:
            target = np.argmax(clf.classes_)     # most bullish class
            coefs = coefs[target]
        else:
            coefs = np.ravel(coefs)
        return (pd.DataFrame({"feature": list(feature_names),
                              "coef": coefs})
                .assign(abs_coef=lambda d: d["coef"].abs())
                .sort_values("abs_coef", ascending=False)
                .drop(columns="abs_coef")
                .reset_index(drop=True))


# ---------------------------------------------------------------------------
def demo() -> dict:
    """The full pipeline meeting itself: causal SPY features -> triple-
    barrier labels -> purged chronological audit vs the majority base rate."""
    from backtest.triple_barrier import TripleBarrier

    px = pd.read_csv(ROOT / "data" / "raw" / "spy.csv", parse_dates=["date"]
                     ).set_index("date")["Close"]
    rets = px.pct_change()
    feats = pd.DataFrame({
        "mom5": px.pct_change(5),
        "mom20": px.pct_change(20),
        "mom60": px.pct_change(60),
        "vol20": rets.rolling(20).std(),
        "vol_ratio": rets.rolling(5).std() / rets.rolling(60).std(),
    }).shift(1)                                  # known at t-1

    tb = TripleBarrier(pt_mult=2.0, sl_mult=1.0, max_hold_bars=10)
    labels = tb.label(px, t_events=px.index[::5])
    labels = labels[labels["bin"] != 0]          # drop degenerate flat bins
    data = feats.loc[labels.index].dropna()
    labels = labels.loc[data.index]

    lb = LinearBaseline(embargo_bars=2)
    res = lb.audit(data, (labels["bin"] > 0).astype(int), t1=labels["t1"])

    print("LINEAR BASELINE AUDIT -- SPY triple-barrier bins, purged split")
    print(f"  train {res['n_train']} (purged {res['n_purged']}) | "
          f"test {res['n_test']} | best C {res['best_C']:.4f}")
    print(f"  accuracy          : {res['accuracy']:.2%}")
    print(f"  majority baseline : {res['majority_baseline']:.2%}")
    print(f"  SKILL             : {res['skill']:+.2%}")
    print(f"  ROC AUC (ovr)     : {res['auc']:.3f}  (random = 0.500)")
    print("  drivers (standardized coefs, most-bullish class):")
    for _, r in res["drivers"].iterrows():
        print(f"    {r['feature']:<12}{r['coef']:>+8.3f}")
    print("\n  READ: this is the yardstick. Any model that can't beat this "
          "skill number")
    print("  net of its extra complexity has no business in the book.")
    return res


if __name__ == "__main__":
    demo()
