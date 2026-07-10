# BR-10C Track B Config Driven Screener Pipeline

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Dashboard
- candidate_count: 6
- research_queue_count: 3
- blocked_count: 3
- stock_profile_count: 3
- crypto_profile_count: 3
- human_review_required_count: 6

## Ranked Research Queue
- rank=1 NVDA: asset_class=stock, score=87.30, filters=stock_growth_quality, label=HUMAN_REVIEW_REQUIRED
  profile: large liquid equity; requires human review before any paper workflow
- rank=2 BTC: asset_class=crypto, score=81.00, filters=crypto_liquid_momentum, label=HUMAN_REVIEW_REQUIRED
  profile: crypto-compatible schema candidate; monitor-only research queue candidate
- rank=3 MSFT: asset_class=stock, score=78.40, filters=stock_growth_quality, label=HUMAN_REVIEW_REQUIRED
  profile: mega-cap quality screen candidate; research queue entry only

## Blocked Profiles
- DOGE: asset_class=crypto, reasons=stock_growth_quality:asset_class_filter_mismatch, stock_growth_quality:sector_filter_mismatch, stock_growth_quality:volatility_score_below_minimum, crypto_liquid_momentum:network_filter_mismatch, crypto_liquid_momentum:drawdown_risk_above_maximum
- SOL: asset_class=crypto, reasons=queue_limit_exceeded
- XYZL: asset_class=stock, reasons=stock_growth_quality:required_tags_missing, stock_growth_quality:sector_filter_mismatch, stock_growth_quality:liquidity_score_below_minimum, crypto_liquid_momentum:asset_class_filter_mismatch, crypto_liquid_momentum:required_tags_missing, crypto_liquid_momentum:network_filter_mismatch, crypto_liquid_momentum:liquidity_score_below_minimum

## Safety
- Ranked research queue only; entries are not trade signals.
- Stock and crypto candidates are local fixture inputs for paper-only review.
- No broker routing, broker calls, live trading, or order submission.