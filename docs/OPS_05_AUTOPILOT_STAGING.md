# OPS-05 Autopilot Staging and Temporary Artifact Hardening

OPS-05 keeps autopilot commits explicit and auditable.

Required safety posture:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- LIVE TRADING: DISABLED

The phase checkpoint validates the full Git change set before staging. It uses
`git status --porcelain=v1 -z --untracked-files=all` through
`automation.autopilot_staging` so staged, unstaged, renamed, deleted, and
untracked paths are discovered without whitespace-sensitive parsing.

Before diff validation, intended phase files are normalized to one final newline
while preserving CRLF or LF style. The safety scanner receives the same explicit
intended path list that will be staged. The checkpoint rejects any non-temporary
changed path outside that list to prevent partial phase commits.

Temporary-looking paths are not cleaned or deleted by OPS-05. Untracked pytest and
Python cache outputs are treated as disposable staging noise and ignored. If Git
tracks a file under a temporary-looking path, it remains a legitimate artifact and
must be included in the intended phase path list when changed.

OPS-05 does not add credentials, provider calls, broker connectivity, broker
writes, external routing, state mutation, or live trading.
