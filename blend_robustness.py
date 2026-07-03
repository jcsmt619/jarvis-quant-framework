"""
blend_robustness.py
===================
Robustness battery v3 for the SOXL Sortino blend, now testing the
SEED-ENSEMBLE brain (rank-aligned filtered-probability averaging, fixed k=3).

The test that matters: run the SAME strategy with three DISJOINT ensemble seed
sets. If the ensemble mechanism works, results must converge across sets --
the strategy should no longer care which random numbers built its brain.

Verdict rules (stated before running, same thresholds as v1/v2):
  * Calmar spread across arms > 30% of the mean -> FRAGILE.
  * Max DD spread across arms > 10 points        -> FRAGILE.

Run:  python blend_robustness.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Three DISJOINT ensemble seed sets (5 seeds each).
SEED_SETS = {
    "setA": [42, 7, 123, 99, 888],
    "setB": [1, 2, 3, 4, 5],
    "setC": [10, 20, 30, 40, 50],
}
OUT = ROOT / "logs" / "regime_blend" / "robustness_battery.json"


def _run(name_and_seeds) -> dict:
    name, seeds = name_and_seeds
    from strategies.regime_blend import run_pair
    r = run_pair("SOXL", ensemble_seeds=seeds)
    r["arm"] = name
    return r


def main() -> None:
    from strategies.regime_blend import W_HIGH, W_LOW, W_MID, WINDOWS

    print(f"ENSEMBLE ROBUSTNESS BATTERY: SOXL blend {W_LOW:.0%}/{W_MID:.0%}/{W_HIGH:.0%}, "
          f"3 disjoint 5-seed ensembles\n")
    with ProcessPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(_run, SEED_SETS.items()))

    print(f"  {'arm':<6}{'total ret':>11}{'CAGR':>8}{'maxDD':>8}{'sharpe':>8}{'calmar':>8}{'kill25%':>9}")
    for r in results:
        m = r["blend"]
        print(f"  {r['arm']:<6}{m['total_return']:>+11.1%}{m['cagr']:>+8.1%}{m['max_dd']:>8.1%}"
              f"{m['sharpe']:>8.2f}{m['calmar']:>8.2f}{'PASS' if m['kill_switch_ok'] else 'FAIL':>9}")

    print("\n  Sub-period survival (blend return per arm):")
    print(f"  {'window':<14}" + "".join(f"{n:>10}   " for n in SEED_SETS))
    for name in WINDOWS:
        cells = []
        for r in results:
            v = r["windows"][name]["blend"]
            cells.append(f"{v:>+10.1%}   " if v is not None else f"{'n/a':>10}   ")
        print(f"  {name:<14}" + "".join(cells))

    # --- verdict per pre-stated rules ---
    calmars = np.array([r["blend"]["calmar"] for r in results])
    dds = np.array([r["blend"]["max_dd"] for r in results])
    rets = np.array([r["blend"]["total_return"] for r in results])
    calmar_spread = float(calmars.max() - calmars.min())
    fragile = (calmar_spread > 0.30 * calmars.mean()) or (float(dds.max() - dds.min()) > 0.10)

    print("\n  VERDICT")
    print(f"    calmar: mean {calmars.mean():.2f}  spread {calmar_spread:.2f} "
          f"({calmar_spread / calmars.mean():.0%} of mean)")
    print(f"    maxDD : {dds.min():.1%} .. {dds.max():.1%}  (spread {dds.max() - dds.min():.1%})")
    print(f"    return: {rets.min():+.1%} .. {rets.max():+.1%}")
    print(f"    -> {'FRAGILE: ensemble did NOT stabilize the brain' if fragile else 'CONVERGENT: ensemble brain is seed-set robust (backtest-only evidence)'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nResults -> {OUT}")


if __name__ == "__main__":
    main()
