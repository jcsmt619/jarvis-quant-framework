from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br24_consolidated_research_dossier import (
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    consolidated_research_dossier_payload,
    run_consolidated_research_dossier,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-24 consolidated research dossier.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    dossier = run_consolidated_research_dossier(out_dir=args.out_dir)
    payload = consolidated_research_dossier_payload(dossier)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"source_phase_count={payload['metrics']['source_phase_count']}")
    print(f"dossier_section_count={payload['metrics']['dossier_section_count']}")
    print(f"unresolved_blocker_count={payload['metrics']['unresolved_blocker_count']}")
    print(f"required_human_review_action_count={payload['metrics']['required_human_review_action_count']}")
    print(f"dossier_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"dossier_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
