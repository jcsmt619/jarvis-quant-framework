# BR-05 LLM Analyst Thesis Generator

Research labels: RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE
LIVE TRADING: DISABLED

## Metrics
- prompt_package_count: 1
- parsed_thesis_record_count: 1
- human_review_required_count: 2

## Prompt Packages
- BR-05-NVDA-20260708160000: symbol=NVDA, contracts=NVDA-20271217-C-140, NVDA-20271217-C-180, NVDA-20271217-C-220, label=HUMAN_REVIEW_REQUIRED

## Parsed Thesis Records
- THESIS-BR05-NVDA-001: symbol=NVDA, confidence=medium, label=HUMAN_REVIEW_REQUIRED
  summary: NVDA LEAPS contracts remain a research-only monitor candidate because the supplied scored contracts show strong liquidity, acceptable spreads, and long DTE, but all conclusions require human review.

## Safety
- Local prompt packaging and response parsing only; no live API calls are required.
- Analyst thesis records are research-only and human-review-required.
- Report-level state remains blocked by safety gate.