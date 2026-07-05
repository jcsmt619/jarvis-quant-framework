# YouTube → Jarvis Action Plan
# Source: AI Pathways YouTube video "I Tested Letting Claude Trade For A Month and Made $102k"
# Full private notes: private_research/youtube/AI_PATHWAYS_CLAUDE_TRADER_102K.md (gitignored, not committed)

> **Created:** 2026-07-04
> **Purpose:** Classify every idea from the video into what Jarvis should adopt, what's already covered, and what should be rejected, with reasoning.
> **Rule:** Nothing in this document authorizes implementation. Every item marked "Requires approval" needs explicit user sign-off before any code is written.

---

## Executive Summary

The video is a marketing/anecdote piece for the creator's paid community, not a research artifact. Its headline claim (~155% in one month letting Claude pick options trades via web chat) is **unverifiable, non-backtestable by the creator's own admission, and not something Jarvis should adopt as a strategy**. However, the video does describe some generically useful *infrastructure/monitoring patterns* (options Greeks dashboard, macro regime score, day-over-day chain diffing, alerting) that are reasonable engineering ideas independent of whether the underlying trade-picking method has any edge.

**Overall recommendation: Reject the "strategy," evaluate the monitoring infrastructure ideas separately, and only if/when Jarvis takes on options support (currently out of scope).**

---

## Classification Table

| # | Idea | Category | Jarvis Has? | Verdict | Requires Approval? |
|---|---|---|---|---|---|
| 1 | LLM (Claude) qualitative web-chat stock/options picking as a "strategy" | Strategy | No (by design) | **REJECT** — not backtestable, not deterministic, fails STRATEGY_VALIDATION_GATE by construction. Contradicts Jarvis's edge-hunting philosophy which requires walk-forward validated, deflated-Sharpe-tested edges before any real capital. | N/A — not planned |
| 2 | "$66k → $169k in 30 days" as evidence of anything | Evidence/Marketing claim | N/A | **REJECT** — anecdotal single-run claim, no verifiable statements, huge survivorship/selection bias, not a controlled study. Not usable as a benchmark or target. | N/A |
| 3 | LEAPS-based (long-dated, >45 DTE, Theta-aware) options strategy | Strategy | No — Jarvis has no options support at all (no options data fetcher, no Greeks engine, no options broker adapter) | **NOT PLANNED** — major scope expansion identical to the "Options strategies" gap already logged in `private_research/skool/SKOOL_JARVIS_GAP_REPORT.md` (section 1 & 2). Would require new data source, new broker capability, new risk model. | Yes — major scope expansion, not currently planned |
| 4 | Daily options Greeks/valuation dashboard (chain pull, local Greeks calc, P&L, snapshot diffing) | Monitoring infra | No (no options at all) | **DEFERRED** — reasonable engineering pattern, but has no target to monitor until/unless Jarvis adds options support. Revisit only if options scope is approved. | Yes — contingent on options scope approval |
| 5 | Macro regime "gate" score from VIX / market breadth / credit spreads (deterministic) | Regime/Risk signal | Partial — Jarvis already has HMM regime detection (`core/hmm_engine.py`, `core/regime_strategies.py`) using returns + volatility | **LOW-VALUE OVERLAP** — Jarvis's HMM regime engine already serves this purpose in a more rigorous (probabilistic, backtestable) way. A simple deterministic VIX/breadth/credit-spread score would be a step backward in rigor, not a step forward. Not recommended. | Yes, if pursued anyway |
| 6 | LLM-driven daily news/sentiment read per holding, non-deterministic overlay | Feature/signal | No | **HIGH RISK, REJECT for now** — non-deterministic, non-backtestable, introduces lookahead/curve-fit and reproducibility risk (same news → different Claude output on different days). Directly conflicts with Jarvis's "deterministic, testable" requirement in `01_CLAUDE.md` and the look-ahead bias testing discipline (`write-lookahead-test` skill). | Yes — but not recommended |
| 7 | Day-over-day options-chain diffing to detect new strikes/expiries | Alerting mechanic | No (no options) | **DEFERRED** — same as #4, tied to options scope. | Yes — contingent on options scope |
| 8 | Catalyst-diversified multi-name portfolio construction (stagger catalyst horizons/sectors across positions) | Portfolio construction heuristic | Partial — Jarvis already has multi-strategy blending (`core/capital_allocator.py`, `execution/multistrat_engine.py`) and correlation caps in the risk manager | **LOW PRIORITY, MOSTLY COVERED** — the underlying principle (don't concentrate risk in one catalyst/sector/timeframe) is already enforced structurally via correlation checks (`core/risk_manager.py`, 0.7 reduce / 0.85 reject) and multi-strategy allocation. No new work needed unless a specific new correlation/sector-exposure dimension is requested. | No — already substantively covered |
| 9 | Telegram / iMessage push alerting for portfolio events | Notification / execution layer | No — Jarvis has `monitoring/alerts.py` but need to confirm delivery channels | **POSSIBLE SMALL ENHANCEMENT** — adding a push-notification channel (e.g., Telegram) to `monitoring/alerts.py` is a small, self-contained, low-risk addition independent of the video's trading claims. This is the one item in the video with plausible standalone value to Jarvis. | Yes — before implementing any new alert channel |
| 10 | "More specific prompts = better LLM output" / context-rich prompting practice | Process/meta | N/A | **NOT CODE-RELEVANT** — a prompting best-practice for human-in-the-loop use of Claude, not a change to Jarvis's automated system. No action. | No |

---

## Recommended Actions (Ranked)

### Do Nothing / Reject
1. Do **not** implement any options-trading strategy based on this video. Options remain out of scope per existing gap report.
2. Do **not** adopt "Claude qualitative web-chat picks trades" as a strategy pattern anywhere in Jarvis. It cannot pass `STRATEGY_VALIDATION_GATE.md` and conflicts with the deterministic/testable requirement in `01_CLAUDE.md`.
3. Do **not** use the LLM-driven daily news/sentiment overlay as a feature or signal input — non-deterministic and look-ahead-risk-prone.
4. Do **not** replace or duplicate the existing HMM regime engine with a simpler deterministic VIX/breadth score — it would reduce rigor.

### Only If Explicitly Approved Later
5. If/when options support is ever approved as a scope expansion (separate large decision, already flagged in the Skool gap report), the video's 4-layer dashboard pattern (data/valuation → portfolio analytics → macro/news context → alerts/dashboard) is a reasonable structural reference for a monitoring layer — but the trade *selection* logic would still need to come from Jarvis's own validated edge-hunting pipeline, not from ad hoc LLM chat.

### Small, Standalone, Low-Risk (worth a real proposal if desired)
6. Consider adding a Telegram (or similar) push-alert channel to `monitoring/alerts.py` as a delivery mechanism for existing alerts. This is decoupled from every other claim in the video and is the only idea here with straightforward, low-risk standalone value. **Still requires explicit approval and its own small design before implementation** — no code has been written as part of this action plan.

---

## Relationship to Existing Docs

- This supplements, but does not duplicate, `private_research/skool/SKOOL_JARVIS_GAP_REPORT.md` — options trading is already logged there as "not planned / major scope expansion." This document independently reaches the same conclusion from a different source.
- Full raw video notes (transcript-derived, unredacted) live in `private_research/youtube/AI_PATHWAYS_CLAUDE_TRADER_102K.md`, which is gitignored under the existing `private_research/` rule in `.gitignore` and must never be committed.

---

## Conclusion

No implementation work is recommended as a direct result of this video. The single item with plausible independent value (Telegram/push alert channel) is minor, decoupled from the video's central (unverifiable, non-backtestable) claims, and still requires its own explicit approval before any code changes are made.
