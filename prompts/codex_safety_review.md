# Codex Safety Review Prompt

Read AGENTS.md and CLAUDE.md first.

Do not edit files.
Do not modify code.
Do not touch .env or secrets.

Review the current git diff.

Check specifically:
1. any broker order submission path
2. any live trading enablement
3. any .env/API key/secret access
4. any removal of safety gates
5. any production order execution path changes
6. any dangerous labels used as trade instructions
7. missing tests for new safety behavior
8. missing output/report assertions
9. missing heartbeat/audit assertions when relevant
10. whether full regression should run before commit

Return:
- BLOCKING ISSUES
- NON-BLOCKING ISSUES
- TESTS TO RUN
- EXACT FILES TO INSPECT
- SAFE TO COMMIT: YES/NO

Do not make changes.
