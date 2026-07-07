# 18A Safe Workflow Catalog

Catalog ID: 18A-SAFE-WORKFLOW-CATALOG-2026-07-07
Catalog Date: 2026-07-07
Generated: 2026-07-07T17:36:23.773114+00:00

Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.
BLOCKED_BY_SAFETY_GATE behaviors remain blocked.
LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.

## Summary

- Workflows: 10

## Workflows

- daily_research_summary | daily_research_summaries | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED | LIVE TRADING: DISABLED | python scripts/run_daily_research_command_center.py | outputs: reports/daily_research_command_center/daily_research_summary.json, reports/daily_research_command_center/daily_research_summary.md
- weekly_review | weekly_reviews | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_weekly_review.py | outputs: reports/weekly_review/weekly_review.json, reports/weekly_review/weekly_review.md
- operator_dashboard_snapshot | operator_dashboards | MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_operator_dashboard_snapshot.py | outputs: reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json, reports/operator_dashboard_snapshot/operator_dashboard_snapshot.md
- operator_runbook | operator_dashboards | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_operator_runbook.py | outputs: reports/operator_runbook/operator_runbook.json, reports/operator_runbook/operator_runbook.md
- research_evidence_pack | evidence_packs | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_research_evidence_pack.py | outputs: reports/research_evidence_pack/research_evidence_pack.json, reports/research_evidence_pack/research_evidence_pack.md
- decision_journal | decision_journals | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_decision_journal.py | outputs: reports/decision_journal/decision_journal.json, reports/decision_journal/decision_journal.md
- report_index | report_generators | RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/run_report_index.py | outputs: reports/report_index/report_index.json, reports/report_index/report_index.md
- safety_scanner | safety_scanners | MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/check_jarvis_safety_scanner.py; powershell scripts/run_jarvis_safety_scanner.ps1 | outputs: reports/safety_scanner/safety_scanner_status.json, reports/safety_scanner/safety_scanner_status.md
- orchestrator_audit_reader | queue_readers | MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/view_orchestrator_audit.py | outputs: reports/orchestrator/audit_reader/audit_reader.json, reports/orchestrator/audit_reader/audit_reader.md
- orchestrator_heartbeat_reader | queue_readers | MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE | LIVE TRADING: DISABLED | python scripts/view_orchestrator_heartbeat.py | outputs: reports/orchestrator/heartbeat_reader/heartbeat_reader.json, reports/orchestrator/heartbeat_reader/heartbeat_reader.md

## Allowed Human-Review Behaviors

- review generated research artifacts
- record operator notes
- record blocked outcomes
- request more deterministic evidence
- keep trade-relevant interpretation HUMAN_REVIEW_REQUIRED

## Blocked Behaviors

- enable live trading
- submit broker orders
- add broker order routing
- perform broker order calls
- open secrets or credential files
- convert research output into trade instructions

## Safety Boundary

- RESEARCH_ONLY workflows may generate research artifacts.
- MONITOR_ONLY workflows may read and summarize operational state.
- PAPER_ONLY workflows may summarize paper-state artifacts only.
- HUMAN_REVIEW_REQUIRED workflows may record review notes without execution.
- BLOCKED_BY_SAFETY_GATE behaviors remain blocked.
- LIVE TRADING: DISABLED.
