from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Full-history daily symbols validated by the walk-forward engine (Phase 3).
WALK_FORWARD_SYMBOLS = ["SPY", "BTC-USD", "TLT", "SOXL", "TQQQ"]


def main() -> None:
    print("=" * 80)
    print("JARVIS QUANTITATIVE RESEARCH FRAMEWORK")
    print("=" * 80)

    # --- PHASE 1: data -----------------------------------------------------
    print("\n[PHASE 1] Fetching institutional data...")
    try:
        from data_fetcher import main as fetch_data
        fetch_data()
        print("\u2713 Data fetch complete")
    except Exception as e:
        print(f"\u2717 Data fetch failed: {e}")
        sys.exit(1)

    # --- PHASE 2: domain-routed tri-agent optimization ---------------------
    print("\n[PHASE 2] Activating domain-routed tri-agent adversarial optimization...")
    try:
        from tri_agent_optimizer import TriAgentOptimizer
        TriAgentOptimizer().run()
        print("\u2713 Tri-agent optimization complete")
    except Exception as e:
        print(f"\u2717 Tri-agent optimization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- PHASE 3: honest walk-forward validation (STEP 4) ------------------
    print("\n[PHASE 3] Running 15-year walk-forward validation (parallel across symbols)...")
    try:
        from backtest.validation import run_walk_forward_validation
        run_walk_forward_validation(WALK_FORWARD_SYMBOLS, parallel=True)
        print("\u2713 Walk-forward validation complete")
    except Exception as e:
        print(f"\u2717 Walk-forward validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
