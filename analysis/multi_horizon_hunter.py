"""
analysis/multi_horizon_hunter.py
================================
Multi-horizon causal feature hunter: which indicators carry out-of-sample
predictive power at t+1, t+3, t+5?

Corrections vs the draft this was adapted from:
  * TAIL LABELS: `np.where(NaN > 0, 1, 0)` silently turned the last h bars
    (whose futures don't exist) into target=0 -- fake labels in train AND
    test. Targets are now NaN at the tail and dropped per horizon.
  * BOUNDARY PURGE: with h>1 the last h-1 training labels overlap the test
    window (the purged-CV failure mode). An h-bar purge gap is removed from
    the end of the training partition.

Kept from the draft: chronological non-shuffled split, depth-capped forest,
permutation importance on the untouched test set, per-horizon majority-class
baseline, alpha = accuracy - baseline.

Run:  python analysis/multi_horizon_hunter.py --ticker SPY --years 8
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MultiHorizonCausalHunter:
    def __init__(self, horizons: list[int] | None = None, train_split: float = 0.80,
                 n_estimators: int = 100, max_depth: int = 5):
        self.horizons = horizons or [1, 3, 5]
        self.train_split = train_split
        self.n_estimators = n_estimators
        self.max_depth = max_depth

    # ------------------------------------------------------------------
    def generate_causal_targets(self, df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
        """Binary targets: 1 if close(t+h) > close(t). The last h rows have NO
        future -- they are NaN (never 0) and must be dropped downstream."""
        targets = {}
        for h in self.horizons:
            fut = df[price_col].shift(-h) / df[price_col] - 1.0
            t = pd.Series(np.where(fut > 0, 1.0, 0.0), index=df.index)
            t[fut.isna()] = np.nan                      # tail: no future, no label
            targets[f"target_tplus_{h}"] = t
        return pd.DataFrame(targets, index=df.index)

    # ------------------------------------------------------------------
    def evaluate_feature_space(self, X: pd.DataFrame, y_df: pd.DataFrame) -> dict:
        """Chronological split + h-bar boundary purge + permutation importance
        on the untouched test partition, per horizon."""
        results: dict = {}
        for col in y_df.columns:
            h = int(col.rsplit("_", 1)[1])
            pair = X.join(y_df[col].rename("y")).dropna()
            Xh, yh = pair.drop(columns="y"), pair["y"].astype(int)

            split = int(len(Xh) * self.train_split)
            purge = h                                    # labels spanning the boundary
            X_train, y_train = Xh.iloc[: split - purge], yh.iloc[: split - purge]
            X_test, y_test = Xh.iloc[split:], yh.iloc[split:]
            if len(X_train) < 100 or len(X_test) < 50:
                results[col] = {"error": "not enough samples after purge"}
                continue

            baseline = float(max(y_test.mean(), 1 - y_test.mean()))
            clf = RandomForestClassifier(
                n_estimators=self.n_estimators, max_depth=self.max_depth,
                min_samples_leaf=20, random_state=42, n_jobs=-1)
            clf.fit(X_train, y_train)
            acc = float(clf.score(X_test, y_test))

            perm = permutation_importance(clf, X_test, y_test, scoring="accuracy",
                                          n_repeats=10, random_state=42, n_jobs=-1)
            order = np.argsort(perm.importances_mean)[::-1]
            rankings = [{"feature": X_test.columns[i],
                         "importance_mean": float(perm.importances_mean[i]),
                         "importance_std": float(perm.importances_std[i])}
                        for i in order]

            results[col] = {
                "horizon": h, "n_train": len(X_train), "n_test": len(X_test),
                "purged": purge, "test_accuracy": acc,
                "majority_baseline": baseline,
                "alpha_generation": acc - baseline,
                "rankings": rankings,
            }
        return results


# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    import yfinance as yf

    from alpha_hunter import build_indicators

    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="SPY")
    ap.add_argument("--years", type=int, default=8)
    args = ap.parse_args()

    df = yf.download(args.ticker, period=f"{args.years}y", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    feats = build_indicators(df).replace([np.inf, -np.inf], np.nan)
    hunter = MultiHorizonCausalHunter()
    targets = hunter.generate_causal_targets(df.rename(columns={"Close": "close"}))
    res = hunter.evaluate_feature_space(feats, targets)

    print(f"MULTI-HORIZON FEATURE HUNT — {args.ticker}, {args.years}y, "
          f"{feats.shape[1]} features, purged chronological split\n")
    print(f"  {'horizon':<10}{'test acc':>10}{'baseline':>10}{'alpha':>9}{'verdict':>12}")
    for col, r in res.items():
        if "error" in r:
            print(f"  t+{col.rsplit('_', 1)[1]:<8}{r['error']}")
            continue
        verdict = "signal?" if r["alpha_generation"] > 0.02 else "noise"
        print(f"  t+{r['horizon']:<8}{r['test_accuracy']:>10.1%}{r['majority_baseline']:>10.1%}"
              f"{r['alpha_generation']:>+9.1%}{verdict:>12}")
    print()
    for col, r in res.items():
        if "error" in r:
            continue
        top = [f"{x['feature']} ({x['importance_mean']:+.4f})" for x in r["rankings"][:5]]
        print(f"  t+{r['horizon']} top features: {', '.join(top)}")
    print("\n  NOTE: one ticker x one split = one sample. 'signal?' must repeat across"
          "\n  tickers/periods and survive deflated-Sharpe before it means anything.")


if __name__ == "__main__":
    main()
