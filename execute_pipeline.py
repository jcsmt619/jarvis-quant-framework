#!/usr/bin/env python3
"""
Direct execution wrapper for the tri-agent optimization pipeline.
This bypasses shell issues by executing within Python directly.
"""
import sys
from pathlib import Path

# Set up path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Import and run the pipeline
if __name__ == "__main__":
    print("\n" + "="*80)
    print("JARVIS QUANTITATIVE RESEARCH FRAMEWORK - PHASE 1 EXECUTION")
    print("="*80 + "\n")
    
    # Step 1: Import and run data fetcher
    print("[STEP 1] Fetching institutional data from Alpaca...\n")
    from data_fetcher import main as fetch_data
    try:
        fetch_data()
        print("\n✓ Data fetch complete\n")
    except Exception as e:
        print(f"\n✗ Data fetch failed: {e}\n")
        sys.exit(1)
    
    # Step 2: Import and run tri-agent optimizer
    print("[STEP 2] Activating tri-agent adversarial optimization...\n")
    from tri_agent_optimizer import TriAgentOptimizer
    try:
        optimizer = TriAgentOptimizer(
            symbols=["SPY", "BTC-USD", "TLT"],
            dataset_type="raw"
        )
        optimizer.run()
        print("\n✓ Tri-agent optimization complete\n")
    except Exception as e:
        print(f"\n✗ Tri-agent optimization failed: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("="*80)
    print("PIPELINE EXECUTION SUCCESSFUL")
    print("="*80 + "\n")
