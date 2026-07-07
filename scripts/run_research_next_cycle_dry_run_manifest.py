from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_dry_run_manifest import (
    DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR,
    build_default_research_next_cycle_dry_run_manifest_input,
    write_research_next_cycle_dry_run_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 25B next cycle dry-run manifest.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_DRY_RUN_MANIFEST_DIR))
    parser.add_argument("--dry-run-manifest-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--safety-preflight-path", default=None)
    parser.add_argument("--next-cycle-plan-path", default=None)
    parser.add_argument("--rollover-gate-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    dry_run_manifest_date = (
        datetime.strptime(args.dry_run_manifest_date, "%Y-%m-%d").date()
        if args.dry_run_manifest_date
        else None
    )
    manifest_input = build_default_research_next_cycle_dry_run_manifest_input(
        dry_run_manifest_date=dry_run_manifest_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "safety_preflight_path": args.safety_preflight_path,
        "next_cycle_plan_path": args.next_cycle_plan_path,
        "rollover_gate_path": args.rollover_gate_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    manifest_input = manifest_input.__class__(
        **{
            **manifest_input.__dict__,
            **{key: Path(value) for key, value in overrides.items() if value is not None},
        }
    )
    json_path, markdown_path = write_research_next_cycle_dry_run_manifest(
        manifest_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 25B NEXT CYCLE DRY RUN MANIFEST: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Next-cycle dry-run manifest is read-only and records-only")
    print("Command hints are inert records only and are not executed")
    print("The next cycle is not run and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, or order paths are created")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
