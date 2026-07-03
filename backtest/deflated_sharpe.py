"""
backtest/deflated_sharpe.py
===========================
Probabilistic and Deflated Sharpe Ratios (Bailey & Lopez de Prado) --
build-library prompt #10, the number this repo has been invoking qualitatively
("seed lottery", "1-of-N-searched") all along.

  PSR: P(true Sharpe > benchmark), given track length and the returns'
       skew/kurtosis (fat tails make a naive Sharpe overstate quality).
  DSR: PSR evaluated against the expected MAXIMUM Sharpe of N independent
       trials -- the haircut for how much you searched. The benchmark rises
       with the trial count; a raw Sharpe that clears zero can still fail to
       clear "the best of 300 coin flips".

All Sharpe inputs here are PER-PERIOD (e.g. daily, unannualized); annualized
numbers are reported separately for readability only.

Run:  python backtest/deflated_sharpe.py --demo        # course worked example
      python backtest/deflated_sharpe.py               # deflate the SOXL blend
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRADING_DAYS = 252
EULER_GAMMA = 0.5772156649015329


# ---------------------------------------------------------------------------
def sharpe_stats(returns: np.ndarray) -> dict:
    """Per-period Sharpe + the distribution moments PSR/DSR need."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    sd = r.std(ddof=1)
    sr = float(r.mean() / sd) if sd > 1e-12 else 0.0
    return {"sr": sr, "T": len(r),
            "skew": float(stats.skew(r)),
            "kurt": float(stats.kurtosis(r, fisher=False)),   # normal = 3
            "sr_annual": sr * np.sqrt(TRADING_DAYS)}


def probabilistic_sharpe(sr: float, T: int, skew: float, kurt: float,
                         sr_benchmark: float = 0.0) -> float:
    """PSR = P(true SR > sr_benchmark | observed sr, T, skew, kurt)."""
    if T < 2:
        return 0.5
    denom = np.sqrt(max(1e-12, 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2))
    z = (sr - sr_benchmark) * np.sqrt(T - 1) / denom
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_trial_sr: float) -> float:
    """E[max SR] of n_trials independent zero-true-SR strategies whose
    estimated SRs have variance var_trial_sr (the search's luck ceiling)."""
    if n_trials <= 1:
        return 0.0
    sd = np.sqrt(max(var_trial_sr, 1e-12))
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(sd * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(returns: np.ndarray, n_trials: int,
                    trial_sharpes: list[float] | None = None) -> dict:
    """Full report: raw, probabilistic, and deflated Sharpe with a blunt verdict."""
    s = sharpe_stats(returns)
    sr, T, skew, kurt = s["sr"], s["T"], s["skew"], s["kurt"]

    # Variance of trial Sharpes: from the actual trials if given, else the
    # asymptotic estimator for a single-strategy SR at this track length.
    if trial_sharpes and len(trial_sharpes) > 1:
        var_sr = float(np.var(np.asarray(trial_sharpes, dtype=float), ddof=1))
    else:
        var_sr = (1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2) / max(T - 1, 1)

    sr0 = expected_max_sharpe(n_trials, var_sr)
    psr = probabilistic_sharpe(sr, T, skew, kurt, 0.0)
    dsr = probabilistic_sharpe(sr, T, skew, kurt, sr0)

    if dsr >= 0.95:
        verdict = "edge SURVIVES deflation (DSR >= 95%)"
    elif dsr >= 0.80:
        verdict = "WEAK evidence -- suggestive, not proven; do not fund on this alone"
    else:
        verdict = "edge DEFLATES TO NOTHING -- treat as a product of the search"

    return {**s, "n_trials": n_trials, "var_trial_sr": var_sr,
            "expected_max_sr": sr0,
            "expected_max_sr_annual": sr0 * np.sqrt(TRADING_DAYS),
            "psr": psr, "dsr": dsr, "verdict": verdict}


def report(res: dict, label: str) -> None:
    print(f"\nDEFLATED SHARPE — {label}")
    print(f"  track: {res['T']} periods | skew {res['skew']:+.2f} | "
          f"kurtosis {res['kurt']:.1f} (normal=3)")
    print(f"  raw Sharpe        : {res['sr_annual']:.2f} annualized "
          f"({res['sr']:.4f}/period)")
    print(f"  PSR  P(SR>0)      : {res['psr']:.1%}")
    print(f"  search ceiling    : best of {res['n_trials']} lucky trials ~ "
          f"{res['expected_max_sr_annual']:.2f} annualized Sharpe")
    print(f"  DSR  P(SR>ceiling): {res['dsr']:.1%}")
    print(f"  VERDICT: {res['verdict']}")


# ---------------------------------------------------------------------------
def demo() -> None:
    """The course's worked example: 'a Sharpe of 2.4 found after 300 trials'.
    Synthesize a 3-year daily track with SR 2.4 annualized, mild fat tails."""
    rng = np.random.default_rng(42)
    T = 756
    sr_daily = 2.4 / np.sqrt(TRADING_DAYS)
    r = rng.standard_t(df=6, size=T)
    r = (r - r.mean()) / r.std(ddof=1) * 0.01
    r = r + sr_daily * 0.01                                  # impose the SR
    res = deflated_sharpe(r, n_trials=300)
    report(res, "course worked example (SR 2.4, 300 trials, 3y daily)")


def deflate_blend() -> None:
    import pandas as pd
    csv = ROOT / "logs" / "regime_blend" / "soxl_blend_equity.csv"
    if not csv.exists():
        print(f"No blend equity at {csv}; run strategies/regime_blend.py first.")
        return
    eq = pd.read_csv(csv, index_col=0, parse_dates=True)["equity"]
    rets = eq.pct_change().dropna().to_numpy()
    # HONEST trial count for the SOXL research line this session: 11 stop-grid
    # multipliers + 2 runner arms + 4 hybrid arms + 2 tail arms + 6 blend
    # configs + 6 seed-battery runs + 3 ensemble arms + ~6 informal variants.
    n_trials = 40
    res = deflated_sharpe(rets, n_trials=n_trials)
    report(res, f"SOXL Sortino blend (honest trial count N={n_trials})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="course worked example")
    args = ap.parse_args()
    if args.demo:
        demo()
    else:
        deflate_blend()
