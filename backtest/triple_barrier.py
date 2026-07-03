"""
backtest/triple_barrier.py
==========================
Triple-barrier labeling (Lopez de Prado, ch.3): label each event by the
FIRST barrier its price path touches -- profit-take (upper), stop-loss
(lower), both scaled by causal EWM volatility, or the vertical time limit.

Labels look at the future BY DESIGN (they are training targets). The whole
point of pairing this module with backtest/cpcv.py is that the labels'
touch times ARE the `t1` label-span series CPCV's purge requires -- use
them together, never with naive CV.

Corrections vs the draft this was adapted from:
  * VERTICAL BARRIER IN CALENDAR DAYS (`Timedelta(days=10)`) -- on
    business-day bars that's ~7 trading bars and varies across weekends
    (the same bug as the CPCV draft's embargo). Now positional BARS.
  * TAIL EVENTS: the draft dropped out-of-range verticals in a way that
    left its "NaNs at end" comment and `fillna(last_bar)` dead, and would
    label incomplete windows with whatever data existed -- so the label
    would CHANGE when new bars arrive. Events without a complete window
    are now dropped explicitly (prefix-consistency: a label, once
    assigned, never changes as data extends -- enforced by test).
  * `min_ret` was accepted, computed, and discarded. Now a real filter:
    events whose volatility target is below `min_ret` are skipped (LdP's
    usage -- don't chase barriers thinner than noise).
  * VERTICAL TOUCH BIN: the draft assigned bin=0 to every time-expiry
    even when the realized return was strongly signed. LdP bins vertical
    touches by sign(ret); the barrier type lives in `touch`.
  * Molecule/index mismatch (`sl` built on events.index, indexed by the
    subset), dead searchsorted block in the vol estimator, unseeded demo,
    emojis -- removed.

Run:  python backtest/triple_barrier.py   (SPY demo + CPCV integration)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TripleBarrier:
    """First-touch labeling with volatility-scaled horizontal barriers.

    Parameters
    ----------
    pt_mult / sl_mult : barrier widths in units of the vol target
        (<= 0 disables that barrier).
    max_hold_bars : vertical barrier, in BARS (positional, not calendar).
    vol_span : EWM span for the causal volatility target.
    min_ret : skip events whose vol target is below this (thinner than noise).
    """

    def __init__(self, pt_mult: float = 2.0, sl_mult: float = 1.0,
                 max_hold_bars: int = 10, vol_span: int = 100,
                 min_ret: float = 0.0):
        self.pt_mult = pt_mult
        self.sl_mult = sl_mult
        self.max_hold_bars = max_hold_bars
        self.vol_span = vol_span
        self.min_ret = min_ret

    # ------------------------------------------------------------------
    def daily_vol(self, close: pd.Series) -> pd.Series:
        """Causal EWM volatility of 1-bar returns -- the dynamic barrier
        width. Uses data at or before each bar only."""
        return close.pct_change().ewm(span=self.vol_span).std()

    # ------------------------------------------------------------------
    def label(self, close: pd.Series, t_events: pd.Index | None = None,
              side: pd.Series | None = None) -> pd.DataFrame:
        """Label events by first barrier touch.

        Returns a DataFrame indexed by event time with columns:
          t1     -- touch timestamp (this is CPCV's label-span input)
          touch  -- 'pt' | 'sl' | 'time'
          ret    -- realized (side-adjusted) return at the touch bar
          bin    -- +1 (pt), -1 (sl), sign(ret) for time expiry
          trgt   -- the vol target used for the barriers

        Events without a COMPLETE vertical window are dropped: their label
        is not yet knowable, and assigning one would let it change as new
        data arrives.
        """
        vol = self.daily_vol(close)
        idx = close.index
        events = idx if t_events is None else pd.Index(t_events)
        prices = close.to_numpy(dtype=float)

        rows = []
        for t0 in events:
            p0 = idx.get_loc(t0)
            p1 = p0 + self.max_hold_bars
            if p1 >= len(idx):
                continue                     # incomplete window -> unknowable
            trgt = vol.iloc[p0]
            if not np.isfinite(trgt) or trgt <= 0 or trgt < self.min_ret:
                continue
            s = float(side.loc[t0]) if side is not None else 1.0
            path_ret = (prices[p0:p1 + 1] / prices[p0] - 1.0) * s
            pt_level = self.pt_mult * trgt if self.pt_mult > 0 else np.inf
            sl_level = -self.sl_mult * trgt if self.sl_mult > 0 else -np.inf

            pt_hits = np.nonzero(path_ret > pt_level)[0]
            sl_hits = np.nonzero(path_ret < sl_level)[0]
            first_pt = pt_hits[0] if len(pt_hits) else np.inf
            first_sl = sl_hits[0] if len(sl_hits) else np.inf

            if first_sl <= first_pt and np.isfinite(first_sl):
                off, touch, b = int(first_sl), "sl", -1
            elif np.isfinite(first_pt):
                off, touch, b = int(first_pt), "pt", 1
            else:
                off, touch = self.max_hold_bars, "time"
                b = int(np.sign(path_ret[-1]))
            rows.append({"event": t0, "t1": idx[p0 + off], "touch": touch,
                         "ret": float(path_ret[off]), "bin": b,
                         "trgt": float(trgt)})

        return pd.DataFrame(rows).set_index("event") if rows else \
            pd.DataFrame(columns=["t1", "touch", "ret", "bin", "trgt"])


# ---------------------------------------------------------------------------
def demo() -> dict:
    """Label SPY events, then hand the labels' t1 straight to CPCV --
    the two halves of the LdP pipeline meeting."""
    from backtest.cpcv import CPCV

    px = pd.read_csv(ROOT / "data" / "raw" / "spy.csv", parse_dates=["date"]
                     ).set_index("date")["Close"]
    tb = TripleBarrier(pt_mult=2.0, sl_mult=1.0, max_hold_bars=10)
    labels = tb.label(px, t_events=px.index[::5])

    counts = labels["touch"].value_counts()
    bins = labels["bin"].value_counts()
    print("TRIPLE BARRIER -- SPY, pt 2.0x vol / sl 1.0x vol / 10-bar vertical")
    print(f"  events labeled: {len(labels)}")
    print(f"  touches: pt {counts.get('pt', 0)} | sl {counts.get('sl', 0)} | "
          f"time {counts.get('time', 0)}")
    print(f"  bins:    +1 {bins.get(1, 0)} | -1 {bins.get(-1, 0)} | "
          f"0 {bins.get(0, 0)}")
    print(f"  mean |ret| at touch: {labels['ret'].abs().mean():.3%} | "
          f"mean hold: "
          f"{(px.index.searchsorted(labels['t1']) - px.index.searchsorted(labels.index)).mean():.1f} bars")

    # CPCV integration: these labels' t1 IS the purge input. NOTE: the
    # index handed to CPCV must be the EVENT index (samples = events), so
    # touch times map into event-row space -- passing the full bar index
    # here would misalign the purge for sparse events.
    cv = CPCV(n_groups=6, n_test_groups=2, embargo_pct=0.01)
    n = len(labels)
    purged = []
    for _, _, train, test in cv.split(n, t1=labels["t1"], index=labels.index):
        purged.append(n - len(train) - len(test))
    print(f"\n  CPCV integration: {cv.n_splits} splits, label spans purge "
          f"{np.mean(purged):.0f} samples/split on average")
    print("  (labels look ahead BY DESIGN -- these purge counts are the "
          "leakage CPCV removes)")
    return {"labels": len(labels), "purged_mean": float(np.mean(purged))}


if __name__ == "__main__":
    demo()
