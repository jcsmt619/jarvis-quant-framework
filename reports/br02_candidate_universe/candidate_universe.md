# BR-02 Candidate Universe Builder

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Metrics
- candidate_count: 5
- included_count: 3
- blocked_count: 2
- human_review_required_count: 5

## Primary Watchlist
- NVDA
- MSFT
- TSLA

## Included Candidates
- NVDA: score=89, sector=Technology, trend_60d_pct=0.1800, volatility_30d=0.4200, label=MONITOR_ONLY
  catalysts: earnings_revision, ai_datacenter
- MSFT: score=83, sector=Technology, trend_60d_pct=0.0900, volatility_30d=0.2600, label=MONITOR_ONLY
  catalysts: cloud_margin, ai_datacenter
- TSLA: score=70, sector=Consumer Discretionary, trend_60d_pct=0.0400, volatility_30d=0.6800, label=MONITOR_ONLY
  catalysts: product_cycle, margin_review

## Blocked Candidates
- ABCD: label=BLOCKED_BY_SAFETY_GATE, reasons=price_trend_below_minimum, volatility_above_maximum
- XYZL: label=BLOCKED_BY_SAFETY_GATE, reasons=average_volume_below_minimum, dollar_volume_below_minimum, options_not_available

## Safety
- Static candidate universe report only; no broker routing or order submission.
- Candidate inclusion is monitor-only research and requires human review.
- Report-level state remains blocked by safety gate.