# BR-09 Local Operator Dashboard

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Operator Summary
- candidate_count: 5
- included_candidate_count: 3
- paper_position_count: 2
- alert_count: 0
- thesis_note_count: 1
- total_pnl: 143.2
- unrealized_pnl: 143.2
- realized_pnl: 0.0

## Candidates
- NVDA: candidate_score=89, risk_score=97, position_count=2, alert_count=0, label=PAPER_ONLY
- MSFT: candidate_score=83, risk_score=None, position_count=0, alert_count=0, label=MONITOR_ONLY
- TSLA: candidate_score=70, risk_score=None, position_count=0, alert_count=0, label=MONITOR_ONLY
- ABCD: candidate_score=60, risk_score=33, position_count=0, alert_count=0, label=BLOCKED_BY_SAFETY_GATE
- XYZL: candidate_score=38, risk_score=None, position_count=0, alert_count=0, label=BLOCKED_BY_SAFETY_GATE

## Paper Positions
- NVDA-20271217-C-140: contracts=1, market_value=4365.60, unrealized_pnl=85.60, label=PAPER_ONLY
- NVDA-20271217-C-180: contracts=1, market_value=2937.60, unrealized_pnl=57.60, label=PAPER_ONLY

## Alerts
- no_local_operator_dashboard_alerts

## Thesis Notes
- THESIS-BR05-NVDA-001: symbol=NVDA, confidence=medium, label=HUMAN_REVIEW_REQUIRED
  summary: NVDA LEAPS contracts remain a research-only monitor candidate because the supplied scored contracts show strong liquidity, acceptable spreads, and long DTE, but all conclusions require human review.

## Safety Status
- Read-only local operator dashboard; static JSON and Markdown output only.
- Consumes local research, paper, monitor, alert, and thesis reports.
- No broker routing, broker calls, live trading, or order submission.