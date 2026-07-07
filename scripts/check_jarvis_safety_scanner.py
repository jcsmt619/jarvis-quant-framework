from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.safety_scanner import SafetyScanResult, scan_git_diff, scan_paths


def _print_result(result: SafetyScanResult) -> None:
    status = "PASS" if result.passed else "BLOCKED"
    print(f"JARVIS 10D SAFETY SCANNER: {status}")
    print("RESEARCH_ONLY")
    print("MONITOR_ONLY")
    print("PAPER_ONLY")
    print("HUMAN_REVIEW_REQUIRED")
    print(f"scanned_files={result.scanned_files}")
    print(f"skipped_files={len(result.skipped_files)}")

    for finding in result.findings:
        print(
            "finding="
            f"{finding.rule_id}|{finding.path}:{finding.line_number}|{finding.excerpt}"
        )

    if not result.passed:
        print("BLOCKED_BY_SAFETY_GATE")

    print("LIVE TRADING: DISABLED")


def run_safety_scanner(paths: list[str], *, diff_only: bool = False) -> int:
    scan_paths_input = [Path(path) for path in paths]
    result = scan_git_diff(scan_paths_input) if diff_only else scan_paths(scan_paths_input)
    _print_result(result)
    return 0 if result.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Jarvis 10D deterministic safety scanner."
    )
    parser.add_argument("paths", nargs="+", help="Files to scan.")
    parser.add_argument(
        "--diff-only",
        action="store_true",
        help="Scan only added lines in git diff for the supplied paths.",
    )
    args = parser.parse_args()

    return run_safety_scanner(args.paths, diff_only=args.diff_only)


if __name__ == "__main__":
    raise SystemExit(main())
