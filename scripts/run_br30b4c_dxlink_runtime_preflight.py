from __future__ import annotations

import sys

from engines.moonshot.deterministic.br30b_tastytrade_sandbox_read_only_connectivity_smoke_test import (
    run_dxlink_runtime_preflight,
)


def main() -> int:
    completed = run_dxlink_runtime_preflight()
    if completed.returncode == 0 and completed.stderr == "":
        sys.stdout.write(completed.stdout)
        return 0
    sys.stderr.write(completed.stderr or "dxlink_process_failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
