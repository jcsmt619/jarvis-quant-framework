from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br14_local_paper_research_session_runner import (
    DEFAULT_REPORT_DIR,
    local_paper_research_session_payload,
    run_local_paper_research_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-14 local paper-only research session.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    report = run_local_paper_research_session(out_dir=args.out_dir)
    payload = local_paper_research_session_payload(report)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"session_json={payload['written_artifacts']['session'][0]}")
    print(f"session_markdown={payload['written_artifacts']['session'][1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
