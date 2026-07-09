# BR-10B - Track A Manual Screener Operator Workflow

**Status:** RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED
**Live trading:** LIVE TRADING: DISABLED
**Phase type:** docs-only operator workflow

This workflow defines how an operator may use a manual Claude Web style review
session as a research screener. It is a paraphrased Jarvis operating procedure,
not raw course content, prompt library content, copied templates, or an
automation grant.

Track A output is a candidate research queue only. It is not a signal, order
instruction, broker action, or permission to bypass deterministic Jarvis gates.
Any trade-relevant note remains HUMAN_REVIEW_REQUIRED and must be handed off
only to PAPER_ONLY review paths.

## Source and Safety Boundary

- Do not paste secrets, credentials, private account data, broker tokens, or
  private portfolio identifiers into an external chat session.
- Do not request broker connectivity, order routing, live position changes, or
  execution steps from the analyst tool.
- Do not reconstruct raw paid prompts, screenshots, checklists, or lesson text
  in this repository.
- Treat every response as non-deterministic research context that can be wrong,
  stale, incomplete, or overfit to the prompt.
- Preserve LIVE TRADING: DISABLED for every Track A artifact.

## Operator Workflow

1. Define the research universe before asking for any screen.
2. Select one primary screen family and no more than two supporting families.
3. State the market regime assumption and why the chosen screen matches it.
4. Ask for a narrowed research queue, including reasons for each inclusion and
   the most important disqualifiers.
5. Record empty results as valid outcomes instead of relaxing thresholds without
   a written reason.
6. Convert surviving names into a local review note labeled RESEARCH_ONLY and
   HUMAN_REVIEW_REQUIRED.
7. Hand off only to existing paper-only Jarvis review workflows.

## Universe Definition

Define the universe in plain language before applying filters. The operator
should record:

- asset class: equities, ETFs, crypto, or another explicitly allowed research
  set;
- geography and exchange scope;
- liquidity floor, such as minimum average dollar volume or quote quality;
- price or market-cap limits if they are part of the research question;
- options availability when the downstream review is LEAPS or options-related;
- exclusion rules for unavailable data, halted symbols, extreme spreads, or
  assets that cannot be reviewed with local evidence.

The universe should be narrow enough that results can be reviewed manually.
Changing the universe after seeing results requires a note explaining why the
first definition was insufficient.

## Filter Families

Use filter families as explainable narrowing tools, not as independent proof of
quality. Common Track A families include:

- Liquidity and tradability: volume, dollar volume, spread quality, quote
  stability, options open interest, and data freshness.
- Trend and momentum: relative strength, moving-average position, higher-high
  structure, breakout proximity, or failed-breakdown recovery.
- Mean reversion and stretch: distance from moving averages, Z-score style
  extension, oversold or overbought context, and support or resistance
  proximity.
- Volatility and range: compression, expansion, average true range behavior,
  realized volatility, and gap risk.
- Catalyst and narrative: earnings, product events, macro dates, sector
  rotation, regulatory events, or news that still requires source review.
- Risk and exclusion: crowded moves, poor liquidity, stale data, binary event
  exposure, broken thesis evidence, or unclear tradability.

The operator should prefer fewer filters with clear reasons. A screen that only
works after many threshold changes should be marked weak and reviewed later, not
forced into the handoff.

## Screen-Not-Signal Discipline

A Track A screen answers, "What deserves more research?" It does not answer,
"What should be traded?"

Required discipline:

- Candidate inclusion means "review next," not "act now."
- Candidate ranking is provisional and must not override BR-03 through BR-06
  deterministic checks.
- Any analyst explanation that mentions position timing, risk/reward, or
  suitability is HUMAN_REVIEW_REQUIRED.
- If evidence conflicts, preserve the conflict instead of asking the analyst to
  force a single conclusion.
- If no candidate passes, record the empty queue as a valid MONITOR_ONLY result.

## Regime-Matched Screens

The screen family should match the current regime assumption. The operator does
not need to prove the regime inside Track A, but the assumption must be explicit.

| Regime assumption | Screen emphasis | Avoid forcing |
|---|---|---|
| Trending / risk-on | Trend quality, momentum persistence, relative strength, liquidity | Deep mean-reversion setups without confirmation |
| Choppy / range-bound | Mean reversion, range edges, volatility normalization, support and resistance | Breakout-only screens that ignore failed moves |
| High volatility / event risk | Liquidity, spread quality, gap risk, event calendar, smaller research queue | Thin names, unclear catalysts, crowded narratives |
| Defensive / risk-off | Quality filters, drawdown behavior, cash-flow or balance-sheet review where available | Speculative screens with weak evidence |
| Unknown / mixed | Broad liquidity first, then one conservative secondary filter | Complex multi-filter screens that imply false precision |

If the regime assumption changes during review, start a new screen note rather
than rewriting the original result.

## Review Checklist

Before a candidate can move from Track A to a paper-only handoff, the operator
must confirm:

- the universe definition is written down;
- filter families and thresholds are explainable;
- the regime assumption is named;
- each candidate has at least one inclusion reason and one risk or disqualifier;
- stale data, low liquidity, and event risk have been checked;
- no broker action, execution instruction, or live-trading step is present;
- downstream handling is labeled RESEARCH_ONLY, PAPER_ONLY, and
  HUMAN_REVIEW_REQUIRED;
- empty candidate lists are preserved when filters produce no suitable names.

## Paper-Only Handoff

Track A handoff may include:

- candidate symbol or asset identifier;
- screen date and operator name or initials;
- universe definition;
- filter families used;
- regime assumption;
- inclusion rationale;
- known risks, disqualifiers, and missing evidence;
- required downstream checks;
- final label set: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY /
  HUMAN_REVIEW_REQUIRED.

Track A handoff must not include broker instructions, real order details, live
position changes, or any claim that the candidate passed deterministic Jarvis
risk gates. The next valid destination is paper-only review, deterministic
scoring, local evidence collection, or a monitor-only watchlist.

## Safety Conclusion

BR-10B adds operator discipline for manual screening only. It creates no code,
no broker integration, no scheduler, no alert delivery, and no execution path.
All Track A results remain research queues requiring human review and paper-only
handoff. LIVE TRADING: DISABLED.
