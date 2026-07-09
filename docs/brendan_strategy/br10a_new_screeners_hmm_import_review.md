# BR-10A - New Brendan Screeners and HMM Import Review

**Status:** RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED
**Live trading:** LIVE TRADING: DISABLED
**Phase type:** Docs-only import review

This review summarizes sanitized concepts from the new Brendan screeners and
advanced HMM module analysis. It does not copy raw paid source content, prompt
libraries, templates, checklists, screenshots, private links, credentials, or
session material.

## Source Boundary

- Only paraphrased concepts are retained in this repository.
- Raw paid source content is not committed and should not be reconstructed here.
- The review is not a trading signal, order instruction, broker integration,
  or automation grant.
- Any trade-relevant interpretation remains HUMAN_REVIEW_REQUIRED.

## Sanitized Findings

### Manual screeners

The manual screener material is best treated as operator discipline for a
human-reviewed research funnel. The useful import is not prompt wording; it is
the habit of defining the universe, applying a small number of explainable
filters, accepting empty result sets, and recording why any threshold changes.

Jarvis should preserve the rule that a screen creates a research queue only.
Candidates still need deterministic scoring, risk gates, paper-only simulation,
and human review before any later workflow can treat them as actionable.

### Automated screeners

The automated screener material supports a deterministic Track B pattern:
configuration-first inputs, independently testable filter families, explainable
ranked output, archived run reports, and capped monitor alerts. This maps
naturally to a future BR-10C phase, downstream of BR-02 and upstream of BR-03
through BR-06.

The important change before BR-11 and BR-12 is to formalize screening as a
repeatable research stage, not as an execution trigger. A correct screener can
return no candidates, and that outcome should be preserved in tests.

### Advanced HMM review

The advanced HMM material highlights gaps that should be resolved before any
broker-boundary design depends on regime detection:

- per-asset HMM configuration profiles;
- explicit confidence and persistence gates;
- out-of-sample validation against simpler regime baselines;
- drift or retraining rules that match the walk-forward simulation;
- a tuning log that records hypotheses, changes, results, and keep/revert
  decisions.

These ideas should remain research and paper workflow improvements until they
earn their place through deterministic validation.

## Recommended Changes Before BR-11 and BR-12

1. Add a docs-only BR-10B operator workflow for manual screener review.
2. Add a deterministic BR-10C config-driven screener pipeline with fixture-based
   tests and explainable empty-list behavior.
3. Add a BR-10D HMM gating/profile layer before using HMM output in any
   operational routing decision.
4. Add a BR-10E HMM regime validation and tuning registry so complexity is
   measured against naive baselines before it is trusted.

These changes strengthen the paper/research pipeline before read-only broker
sync design and human-approved execution safety design. They do not require
broker credentials, broker calls, order routing, or live trading.

## Deferred or Rejected

- Raw paid prompts, course templates, screenshots, and exact checklists.
- Credential-backed alert delivery integrations.
- Broker account reads, broker account writes, and broker order submission.
- Confidence-scaled sizing until hard gates and validation are proven first.
- Scheduled deployment work until a local deterministic screener exists.

## Safety Conclusion

BR-10A imports only sanitized review conclusions. The next roadmap work should
remain RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, and HUMAN_REVIEW_REQUIRED. Any
future broker-facing phase must continue to prove LIVE TRADING: DISABLED.
