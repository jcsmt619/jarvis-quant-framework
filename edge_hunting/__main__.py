"""
edge_hunting/__main__.py
========================
CLI entry point for the edge-hunting pipeline.

Usage:
    python -m edge_hunting <config.yaml>           # run one experiment
    python -m edge_hunting configs/experiments/    # run all in a directory
    python -m edge_hunting --list                  # list available configs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from edge_hunting.runner import run_experiment


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="edge_hunting",
        description="Edge-hunting pipeline: run strategy experiments.",
    )
    ap.add_argument(
        "target",
        nargs="?",
        help="Path to a YAML config file or a directory of configs.",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="List available experiment configs in configs/experiments/.",
    )
    args = ap.parse_args()

    if args.list:
        cfg_dir = Path("configs/experiments")
        if not cfg_dir.exists():
            print("No configs/experiments/ directory found.")
            return 0
        yamls = sorted(cfg_dir.glob("*.yaml"))
        if not yamls:
            print("No experiment configs found in configs/experiments/.")
        else:
            print("Available experiment configs:")
            for y in yamls:
                print(f"  {y.name}")
        return 0

    if not args.target:
        ap.print_help()
        return 1

    target = Path(args.target)

    if target.is_dir():
        yamls = sorted(target.glob("*.yaml"))
        if not yamls:
            print(f"No .yaml configs found in {target}")
            return 1
        failures = []
        for y in yamls:
            print(f"\n{'='*60}")
            print(f"Running: {y.name}")
            print(f"{'='*60}")
            try:
                report = run_experiment(y)
                print(f"  Verdict: {report.gate_verdict.verdict}")
                if report.gate_verdict.hard_failures:
                    for f in report.gate_verdict.hard_failures:
                        print(f"    FAIL: {f}")
                if report.gate_verdict.soft_warnings:
                    for w in report.gate_verdict.soft_warnings:
                        print(f"    WARN: {w}")
            except Exception as exc:
                print(f"  ERROR: {exc}")
                failures.append(str(y))
        if failures:
            print(f"\n{len(failures)} experiment(s) failed: {failures}")
            return 1
        return 0

    elif target.is_file():
        report = run_experiment(target)
        print(f"\nExperiment: {report.config.strategy_name}")
        print(f"  Verdict: {report.gate_verdict.verdict}")
        print(f"  Sharpe:  {report.metrics.get('sharpe', 0):.2f}")
        print(f"  Max DD:  {report.metrics.get('max_drawdown', 0):.2%}")
        print(f"  DSR:     {report.robustness.get('dsr', 0):.2f}")
        if report.gate_verdict.hard_failures:
            print("\n  Hard Gate Failures:")
            for f in report.gate_verdict.hard_failures:
                print(f"    - {f}")
        if report.gate_verdict.soft_warnings:
            print("\n  Soft Warnings:")
            for w in report.gate_verdict.soft_warnings:
                print(f"    - {w}")
        return 0 if report.gate_verdict.passed else 1

    else:
        print(f"Target not found: {target}")
        return 1


if __name__ == "__main__":
    sys.exit(main())