from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.operator_acknowledgment_ledger import (
    DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR,
    OperatorAcknowledgmentLedgerInput,
    build_default_operator_acknowledgment_ledger_input,
    write_operator_acknowledgment_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 21B operator acknowledgment ledger.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OPERATOR_ACKNOWLEDGMENT_LEDGER_DIR))
    parser.add_argument("--ledger-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--human-review-queue-path", default=None)
    parser.add_argument("--operator-acknowledgments-path", default=None)
    args = parser.parse_args()

    ledger_date = (
        datetime.strptime(args.ledger_date, "%Y-%m-%d").date()
        if args.ledger_date
        else None
    )
    ledger_input = build_default_operator_acknowledgment_ledger_input(
        ledger_date=ledger_date,
        now=datetime.now(tz=UTC),
        operator_acknowledgments_path=Path(args.operator_acknowledgments_path)
        if args.operator_acknowledgments_path
        else None,
    )
    ledger_input = OperatorAcknowledgmentLedgerInput(
        **{
            **ledger_input.__dict__,
            **(
                {"human_review_queue_path": Path(args.human_review_queue_path)}
                if args.human_review_queue_path
                else {}
            ),
        }
    )
    json_path, markdown_path = write_operator_acknowledgment_ledger(
        ledger_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 21B OPERATOR ACKNOWLEDGMENT LEDGER: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("Acknowledgments are records only; no automatic actions or live-trading approvals")
    print("BLOCKED_BY_SAFETY_GATE workflows remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
