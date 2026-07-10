from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br20_paper_research_decision_journal import (
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_EVIDENCE_PATH,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    paper_research_decision_journal_payload,
    run_paper_research_decision_journal,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-20 paper research decision journal.")
    parser.add_argument("--source-evidence-path", type=Path, default=DEFAULT_SOURCE_EVIDENCE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    journal = run_paper_research_decision_journal(
        source_evidence_path=args.source_evidence_path,
        out_dir=args.out_dir,
    )
    payload = paper_research_decision_journal_payload(journal)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"journal_record_count={payload['metrics']['journal_record_count']}")
    print(f"held_count={payload['metrics']['held_count']}")
    print(f"rejected_count={payload['metrics']['rejected_count']}")
    print(f"sent_for_review_count={payload['metrics']['sent_for_review_count']}")
    print(f"journal_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"journal_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
