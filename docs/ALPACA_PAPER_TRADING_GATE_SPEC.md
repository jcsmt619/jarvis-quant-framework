# Alpaca Paper-Trading Gate — Design Spec (EEM RSI Candidate)

**Status: DESIGN SPEC ONLY. Nothing in this document has been
implemented. No code has been written or modified. No trades have been
placed. No live trading has been enabled. No `.env` file has been read,
edited, or created. No API keys have been requested, viewed, or handled
in producing this document. This spec requires explicit human approval
before Phase 1 implementation work (see Section 12) begins, and each
subsequent phase requires its own separate approval before it begins.**

## Sources read

- `docs/JARVIS_PAPER_TRADING_CANDIDATES.md` (candidate approval basis)
- `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` (independent-engine validation)
- `docs/EEM_EXPANSION_DECISION_MEMO.md` (expansion scope decision)
- `broker/alpaca_client.py`, `broker/base.py` (existing broker adapter —
  read only, not modified)
- `core/risk_manager.py` (existing `RiskManager` / `RiskLimits` /
  `PortfolioRiskManager` — read only, not modified)
- `utils/state_gatekeeper.py` (existing `StateGatekeeper` — read only,
  not modified)
- `paper_loop.py` (existing paper-trading daemon pattern for the
  structural-arb signal — read only, not modified; this spec reuses its
  architecture rather than replacing it)
- `monitoring/logger.py` (existing structured JSON logger — read only,
  not modified)

## Why this spec exists

Per `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` Section 10, the EEM
`rsi_revert(14, 30/70)` candidate's confidence was raised "meaningfully
higher" after an independent LEAN mirror confirmed it beats EEM
buy-and-hold on both return and drawdown — but that same report
explicitly concluded the candidate is **"eligible for paper-trading gate
design work... not for live deployment."** This document is that gate
design. Per `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`, EEM
`rsi_revert(14, 30/70)` is the **only** candidate classified
`APPROVED_FOR_PAPER_TEST`; every other candidate in that report is either
a conditional backup pending an unmet requirement, a defensive/research
classification, or an outright reject. Accordingly, this gate is
designed around a **single-strategy allowlist**, not a general-purpose
multi-strategy paper-trading framework.

---

## 1. Strategy allowlist (Requirements #1, #2)

The gate must refuse to run any strategy that is not both (a) present in
`docs/JARVIS_PAPER_TRADING_CANDIDATES.md`, and (b) classified exactly
`APPROVED_FOR_PAPER_TEST` in that document at the time the gate starts.

**Initial allowlist (hardcoded, not user-configurable at runtime):**

```
ALLOWED_STRATEGIES = [
    {
        "strategy": "rsi_revert",
        "asset": "EEM",
        "params": {"window": 14, "oversold": 30, "overbought": 70},
        "candidate_doc_status": "APPROVED_FOR_PAPER_TEST",
    },
]
```

Design rules for the allowlist mechanism:

- The allowlist is a Python constant (or a small, version-controlled
  YAML/JSON file reviewed alongside code, e.g.
  `config/paper_trading_allowlist.yaml`), **not** a value read from an
  environment variable, a database, or any other runtime-mutable source
  — this prevents a config change alone from silently adding a second,
  unreviewed strategy.
- At startup, the gate must load `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  (or a machine-readable companion export of it, e.g. a
  `candidates_status.json` regenerated only when that doc is regenerated)
  and verify that every entry in `ALLOWED_STRATEGIES` still maps to a
  candidate marked `APPROVED_FOR_PAPER_TEST` there. If the classification
  has changed (e.g. downgraded after a future re-review) or the entry is
  missing, the gate must refuse to start for that strategy and log why.
- Adding a second strategy to `ALLOWED_STRATEGIES` in the future requires
  a separate, explicit code change and its own review — it must never be
  possible via a config flag alone, an API call, or a runtime toggle.
- The strategy's actual trading logic (the RSI computation and
  entry/exit rule) must be imported unmodified from the existing,
  already-tested `edge_hunting/strategy_library.py::strategy_rsi_revert`
  function (or an equivalent read-only adapter around it) — the gate
  does not reimplement or approximate the rule; it only decides whether
  and how the existing rule's signals are allowed to reach a broker.

## 2. Alpaca paper-mode-only enforcement (Requirements #3, #4, #5)

This reuses and hardens the existing, already-correct pattern in
`broker/alpaca_client.py::AlpacaBroker.__init__` rather than replacing
it:

- The gate must construct its broker adapter as `AlpacaBroker(paper=True)`
  with `paper` **hardcoded** in the paper-trading-gate entry point — not
  read from a CLI flag, environment variable, or config file. There is
  no code path in the paper-trading gate that can pass `paper=False`.
- `ALPACA_CONFIRM_LIVE` must remain `false` (or unset) for the entirety
  of the paper-trading evaluation period. The gate must actively check
  this at every startup and refuse to run at all — not just refuse to
  go live — if `ALPACA_CONFIRM_LIVE` is set to any live-confirming value
  in the environment, on the theory that if that flag is set, a human
  is mid-way through a live-trading change and the paper gate should not
  be running concurrently against a possibly-being-reconfigured broker
  session. This is a **belt-and-suspenders** check on top of the
  existing `AlpacaBroker` constructor guard, not a replacement for it.
- **Live trading requires a separate, explicit dual-gate that is
  explicitly NOT implemented by this spec or by any of its six phases**
  (see Section 12, Phase 6 — design-only). The dual-gate's two
  independent conditions (sketched here for future reference only, not
  built now) would be: (a) `paper=False` passed explicitly by a human
  at the call site, AND (b) `ALPACA_CONFIRM_LIVE=YES` set explicitly in
  the environment by a human — both already required by the existing
  `AlpacaBroker` constructor. A third, new condition this future gate
  would add on top of the existing two: (c) a signed-off paper-trading
  evaluation report (Section 9) showing a PASS verdict, filed and
  reviewed by a human, with its file path hardcoded into the go-live
  check so an unreviewed or FAIL report cannot satisfy it. No code for
  this third condition exists yet, and none should be written before
  Phase 6 is separately approved.
- This spec, and every phase of its implementation through Phase 5, is
  explicitly a **paper-only artifact**. No phase 1-5 deliverable should
  contain any code path, flag, or config value that could set
  `paper=False` or `ALPACA_CONFIRM_LIVE=YES`.

## 3. Position sizing limits (Requirement #6)

- **Max position size**: hardcoded, small, fixed-dollar notional cap
  for the paper-trading evaluation, independent of the backtest's
  100%-of-equity sizing convention (Section 6 of
  `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` notes the backtest sizing
  was never strictly confirmed against the LEAN mirror either). Proposed
  default: **$5,000 notional per EEM position**, configurable only via
  a reviewed constant, not a runtime input. This is a deliberately small
  fraction of a typical Alpaca paper account's starting equity
  ($100,000 by Alpaca's own paper-account default), so that even a
  worst-case single-position loss during evaluation cannot be
  confused with a meaningful capital event — this is a plumbing/behavior
  test, not a capital-efficiency test.
- **Max concurrent EEM position**: exactly one (the strategy is
  single-asset, long/short/flat per `TradeSignal.direction ∈
  {-1,0,+1}` in `core/risk_manager.py`) — the gate must never hold two
  simultaneous EEM positions (e.g. a stale one plus a new one) as a
  matter of design, checked explicitly before every new-position order.
- This position-size cap is enforced **in addition to**, not instead
  of, the existing `RiskManager.validate_signal()` mandatory-stop and
  single-position-cap checks in `core/risk_manager.py` — the paper gate
  must construct a `RiskLimits` instance with `max_position_pct` and
  `min_position_usd` set so that the existing risk manager's own
  independent math also cannot produce a notional above the $5,000 cap
  for this specific strategy/account-size combination. Both layers must
  agree; neither replaces the other.

## 4. Max daily loss (Requirement #7)

- **Max daily loss: 1% of paper-account equity at the start of that
  trading day**, hardcoded. If realized + unrealized daily P&L on the
  EEM position (there is only ever one) breaches -1%, the gate must:
  (a) immediately flatten the EEM position if one is open, (b) block
  any new entries for the remainder of that trading day, (c) log a
  `DAILY_LOSS_LIMIT_BREACHED` event with the exact P&L, equity, and
  position detail, and (d) resume normal operation only at the next
  trading day's open, after startup reconciliation (Section 10) passes.
- This is intentionally a much tighter daily-loss bar than
  `RiskLimits.daily_dd_reduce` (4%) / `daily_dd_halt` (6%) in
  `core/risk_manager.py`'s existing defaults — those defaults are tuned
  for the aggressive, multi-strategy, potentially-leveraged production
  risk manager described in that file's own docstring ("300% gross
  exposure with full Kelly on 3x LETFs"), which is not this candidate's
  profile (EEM, unleveraged, single-asset, `~55` OOS trades over 4.5
  years — a low-frequency strategy where a 4-6% daily move would be a
  major, not routine, event). The paper gate must instantiate its own
  `RiskLimits` (or an equivalent, tighter dataclass) rather than reusing
  the production defaults unmodified, precisely because the point of
  this evaluation period is to observe this specific low-frequency
  candidate's live behavior under a conservative, easily-tripped ceiling
  — not to test the general-purpose risk manager's own aggressive
  defaults, and not to risk a paper-only misconfiguration being confused
  with the general risk manager's intended live-trading dial.

## 5. Max total drawdown (Requirement #8)

- **Max total (peak-to-current) drawdown on the paper account: 5%** of
  the peak equity observed since the evaluation began, hardcoded. On
  breach: (a) flatten all positions, (b) write a hard-halt lock file
  (reusing the existing `CircuitBreaker._write_lock` /
  `DEFAULT_LOCK` pattern in `core/risk_manager.py`, but at a
  paper-gate-specific path, e.g. `logs/paper_gate_halted.lock`, so it
  cannot be confused with or accidentally cleared by the production
  risk manager's own lock file), (c) require a manual, explicit review
  and lock-file deletion before the gate can run again — mirroring the
  existing `RiskManager.kill_switch_engaged()` / `clear_lock()` pattern,
  reused rather than reimplemented.
- Given the candidate's own backtest-reported max OOS drawdown (-9.9%
  at Jarvis's 1bp cost assumption) and the LEAN mirror's full-period
  max drawdown (-29.25%, on a much longer, unfiltered window — see
  `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` Section 7), a 5% total-DD
  paper-account halt is deliberately tighter than either backtest
  number, not a prediction that -5% is expected. The gate is designed
  to fail loudly and stop long before it could ever accumulate a loss
  large enough to be informative about "how bad could this really get"
  — that number is already known from backtests; the paper period's job
  is to test **process fidelity** (does live signal generation, order
  submission, and fills match backtest assumptions — Section 9), not to
  re-derive a worst-case drawdown figure with real (even if paper)
  capital.

## 6. Max orders per day (Requirement #9)

- **Max orders per day: 4**, hardcoded. This is deliberately generous
  relative to the candidate's own expected trade frequency (~55 OOS
  trades over ~1,134 trading days, i.e. roughly one trade every 20
  trading days on average — see `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  candidate #1's "Expected trade frequency" field) — 4 orders/day is not
  a cap the strategy should ever approach in normal operation. Its
  purpose is purely defensive: if a bug (e.g. a flapping RSI signal
  right at the 30/70 threshold, a broker reconnect causing duplicate
  order submission, or a state-gatekeeper desync) caused unexpectedly
  frequent order submission, this cap stops it well before it could
  compound into a large number of unintended fills, while still leaving
  enough headroom (open + close in the same day is already 2 orders)
  for entirely normal, non-bug behavior.
- On breach: block further order submission for the remainder of the
  day, log `MAX_DAILY_ORDERS_BREACHED` with the order sequence that
  triggered it, and treat it as a signal-quality anomaly worth manual
  review before the next trading day — an order-count breach this far
  above expected frequency is itself evidence something is wrong with
  either the signal or the plumbing, independent of whether any single
  order was individually profitable or a loss.

## 7. Stale data checks (Requirement #10)

- Before evaluating the RSI signal on any cycle, the gate must confirm
  the most recent EEM bar's timestamp is **no older than 1 trading day**
  (i.e., the latest daily bar used for the RSI computation must be from
  the prior completed session or the current session's latest available
  bar, depending on the chosen evaluation cadence — see Section 11 on
  cadence) plus a small buffer for weekends/holidays. If the data is
  staler than this, the gate must skip the cycle entirely (no signal
  evaluated, no order considered) and log a `STALE_DATA_SKIP` event with
  the actual vs. expected bar timestamp — reusing the existing pattern
  in `broker/alpaca_client.py::AlpacaBroker.get_bars`, which already
  logs (rather than fabricates) missing symbols; this spec extends that
  same fail-safe philosophy to staleness, not just absence.
- A secondary check: if EEM bars are present but the *bar count*
  returned is fewer than the RSI lookback window (14 bars, per
  `strategy_rsi_revert`'s `window` parameter) plus a small safety margin,
  the cycle must also be skipped and logged as `INSUFFICIENT_BARS_SKIP`
  — an RSI computed on too few bars is not staleness in the timestamp
  sense but is the same underlying failure mode (unreliable signal
  input) and must be treated with the same "skip, don't guess" policy.
- Stale-data skips must never silently fail closed forever — each skip
  is logged and the gate retries on its next scheduled cycle, but a
  **consecutive stale-data skip counter** (e.g. 3+ consecutive skips)
  should itself raise a `STALE_DATA_PATTERN` alert (Section 8's alerting
  channel), since a data feed that stays stale across multiple cycles is
  itself an operational problem worth a human looking at, not just a
  per-cycle nuisance.

## 8. Market-hours checks (Requirement #11)

- Every cycle must call the existing `AlpacaBroker.is_market_open()`
  (already implemented, reusing `self.api.get_clock().is_open`) before
  evaluating any signal or submitting any order. If the market is
  closed, the cycle must return immediately with no signal evaluation,
  matching the existing pattern already used in `paper_loop.py::cycle()`
  (`if not self.broker.is_market_open(): return`).
- Because this is a **daily-bar** strategy (unlike `paper_loop.py`'s
  1-minute structural-arb signal), the natural evaluation cadence is
  once per trading day, ideally shortly after the market open (to
  capture the most recent completed daily bar and place any order as
  close to the start of the session as practical) rather than a tight
  60-second polling loop — see Section 11 for the specific recommended
  cadence design. The market-hours check remains mandatory even at this
  slower cadence: a daily cron-style trigger firing on a weekend or
  market holiday must still be caught and skipped by this check, not
  assumed away by the scheduler.
- The order-timing lesson from `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md`
  Section 4 (LEAN converts market orders submitted while closed to
  MarketOnOpen for next-session execution) is directly relevant here:
  the paper gate's own market-hours check prevents ever attempting to
  submit while closed in the first place, which is a stricter and more
  transparent behavior than relying on the broker to silently convert
  and delay the order — every order this gate submits should be
  submitted while the market is confirmed open, with the exact
  submission timestamp logged (Section 9), so that any observed
  fill-timing divergence from backtest assumptions is measurable rather
  than hidden inside a broker-side conversion.

## 9. Order reconciliation (Requirement #12)

- This reuses the existing `StateGatekeeper` / `AlpacaBroker.reconcile()`
  pattern from `utils/state_gatekeeper.py` and `paper_loop.py`'s
  `startup_reconciliation()` almost exactly, applied to the single EEM
  position instead of the structural-arb pairs:
  - **At every gate startup**, before any signal is evaluated: run
    `broker.reconcile(gate)` (or the equivalent `reconcile_with_broker`
    call against the gate's local EEM position record). Any mismatch —
    ORPHAN (broker holds EEM but local state doesn't know it), PHANTOM
    (local state thinks it holds EEM but the broker doesn't), or QTY
    MISMATCH — must disarm trading exactly as the existing gatekeeper
    already does (`StateGatekeeper._disarm`), requiring the existing
    supervised `adopt_broker_state()` + `resume_trading()` two-step
    recovery before the gate resumes. No new reconciliation logic is
    invented; the existing, already-tested mechanism is reused as-is.
  - **After every order fill** (not just at startup): re-fetch the
    broker's EEM position and compare it against the local gatekeeper
    state's expectation given the fill just recorded. A mismatch here
    (e.g. a partial fill the gate didn't correctly account for) must
    also disarm trading and require the same supervised recovery — this
    is a stricter, per-fill reconciliation on top of the startup-only
    check in the existing `paper_loop.py` pattern, added specifically
    because Requirement #12 asks for order reconciliation generally, not
    only at startup.
  - **On every scheduled cycle** (even when no order is placed that
    cycle), a lightweight "is the broker's reported EEM position still
    what we expect" check should run before evaluating the day's signal,
    catching any external interference (e.g. a manual trade placed
    directly in the Alpaca paper dashboard by a human, outside the
    gate's own logic) that would otherwise go unnoticed until the next
    fill.

## 10. Kill-switch behavior (Requirement #13)

- Reuses the existing, already-implemented dual kill-switch pattern
  exactly:
  - **Manual kill switch**: a lock file (e.g.
    `logs/paper_gate_halted.lock`, distinct from the production
    `RiskManager`'s own `logs/trading_halted.lock` per Section 5) whose
    mere presence halts the gate (`RiskManager.kill_switch_engaged()`
    already implements exactly this pattern: "if lock file exists ->
    halted"). A human can create this file at any time (e.g.
    `echo halt > logs/paper_gate_halted.lock`) to immediately and
    unconditionally stop the gate before its next cycle, with no code
    changes needed — this is the fastest possible manual stop.
  - **Automatic kill switches**, each of which writes its own
    descriptive halt reason to the lock file content (reusing
    `CircuitBreaker._write_lock`'s pattern of writing the trigger
    reason, drawdown, and timestamp into the file itself, not just its
    existence) and require the same explicit manual-delete-and-review
    to clear:
    - Max total drawdown breach (Section 5)
    - Reconciliation failure (Section 9) that cannot be auto-resolved
    - Unhandled exception in the main cycle loop — the existing
      `paper_loop.py::run()` pattern of catching all exceptions,
      logging with `logger.exception`, disarming the gatekeeper, and
      breaking out of the loop (never silently continuing after an
      unknown error) is reused verbatim for the EEM paper gate.
    - A confirmed stale-data pattern (Section 7) persisting long enough
      to suggest the data feed itself, not just one bad cycle, is
      broken (e.g. 3+ consecutive trading-day skips).
  - **Kill-switch clearing is always a two-step, explicit, human-driven
    process** — never automatic, and never triggered by a scheduled
    retry: (1) a human reviews the halt reason recorded in the lock
    file and the surrounding structured logs (Section 11), (2) the human
    manually deletes the lock file (or calls the existing
    `RiskManager.clear_lock()`-equivalent), only after which the gate's
    normal startup reconciliation (Section 9) runs again on the next
    cycle. This mirrors the existing production pattern exactly, which
    is intentional — paper trading should exercise the same halt/resume
    discipline that would be required in any eventual live path, not a
    looser one.

## 11. Full logging requirement (Requirement #14)

All of the following event types must be logged as structured JSON
records via the existing `monitoring/logger.py::get_logger()` /
`log_state()` pattern (one dedicated log file, e.g.
`logs/eem_paper_gate.jsonl`, rotated per the existing 10MB/5-backup
convention — no new logging framework introduced):

| Event type | Minimum fields logged |
|---|---|
| **Signal computed** | timestamp, EEM close price, RSI value, threshold state (oversold/overbought/neutral), resulting raw direction |
| **Decision (risk manager)** | timestamp, signal detail, `RiskDecision.approved`, `rejection_reason` if rejected, all `modifications` applied (e.g. size clipping) |
| **Skipped trade** | timestamp, reason (stale data, insufficient bars, market closed, daily-loss-limit active, daily-order-cap reached, kill switch engaged, risk-manager rejection) |
| **Submitted order** | timestamp, symbol, side, qty, order type, target notional, broker order ID (once returned) |
| **Filled order** | timestamp, order ID, fill price, fill qty, filled-vs-submitted qty (partial fill flag), slippage vs. the price used at signal-time |
| **Rejected order** | timestamp, order ID (if any), broker-reported rejection reason (from `Order.reason` in `broker/base.py`'s existing dataclass) |
| **Current risk state (every cycle, not just on change)** | timestamp, current EEM position (qty, entry price, unrealized P&L), daily P&L, daily order count so far, peak-to-current drawdown, kill-switch status, days elapsed in evaluation period |

- Every one of these events must be logged **even when the outcome is
  "nothing happened"** — e.g. a cycle where the market is closed, or the
  RSI is neutral and no signal fires, must still produce a "signal
  computed: neutral, no action" record, not silence. The evaluation
  report (Section 9) depends on a complete, gapless record of every
  cycle's outcome, not just the cycles where something interesting
  happened — an incomplete log would make it impossible to later
  distinguish "the strategy correctly stayed flat" from "the gate
  silently failed to run that day."
- Log records must never contain API keys, account numbers, or other
  credentials — consistent with the existing `AlpacaBroker` connection
  banner's explicit avoidance of printing account numbers.

## 12. Recommended staged implementation plan (Requirement: staged plan)

**Each phase below requires its own separate, explicit human approval
before implementation begins. Completing this spec (Phase 1) does not
pre-approve Phases 2-6.**

- **Phase 1 — Design only.** *(This document.)* No code. Defines the
  allowlist mechanism, all risk limits, logging schema, reconciliation
  reuse, kill-switch reuse, and the evaluation pass/fail criteria
  (Section 13). Deliverable: this spec, reviewed and approved by a human
  before Phase 2 begins.
- **Phase 2 — Dry-run signal logger.** Implements *only* the signal
  computation and logging path (Section 11's "signal computed" and
  "skipped trade" events) against live/delayed EEM market data, with
  **no broker connection at all** — no Alpaca API calls, no orders, not
  even in paper mode. Purpose: confirm the RSI signal computed from a
  live data feed matches what the backtest engine would compute on the
  same dates, before any order-placing code exists. This phase can run
  for as long as needed with zero trading risk of any kind, including
  paper-account risk.
- **Phase 3 — Alpaca paper connection.** Adds the `AlpacaBroker(paper=True)`
  connection, startup reconciliation (Section 9), and market-hours /
  stale-data checks (Sections 7-8) — but still **does not submit any
  order**. Purpose: confirm the broker connection, reconciliation, and
  gating checks all behave correctly against the real (paper) Alpaca
  account and its actual clock/data feed, with orders still fully
  disabled at the code level (not just untriggered).
- **Phase 4 — Paper order execution.** Enables actual order submission
  through `AlpacaBroker.submit_order()` (still `paper=True`, still
  `ALPACA_CONFIRM_LIVE` unset/false, both re-verified per Section 2) —
  the first phase where paper orders are actually sent. All limits from
  Sections 3-6, 10 are active from the first cycle of this phase, not
  phased in gradually. This phase is where the 3-month minimum
  evaluation clock (Section 13) begins.
- **Phase 5 — Paper-trading review report.** After the minimum 3-month
  evaluation period (Section 13) completes, produce a written report
  (following the same evidence-based, no-classification-fudging
  standard already used in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  and `docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md`) comparing the observed
  paper-trading behavior against backtest assumptions, and issuing an
  explicit PASS/FAIL verdict per Section 13's criteria.
- **Phase 6 — Live-trading gate review, design only.** If and only if
  Phase 5 issues a PASS verdict, a **separate** design spec (not
  written now, not implied to be pre-approved by this document) would
  define the third live-trading dual-gate condition sketched in
  Section 2 (a signed-off PASS report as a hard precondition, in
  addition to the two conditions the `AlpacaBroker` constructor already
  enforces). Phase 6 is explicitly **design only** — it does not itself
  enable live trading, and a further, separate, explicit human approval
  would still be required before any live-trading code is written after
  Phase 6.

## 13. Paper-trading evaluation period and pass/fail criteria (Requirement #15)

- **Minimum duration: 3 months of active Phase 4 paper trading**, no
  exceptions for early "good-looking" results — the point of a fixed
  minimum window is specifically to prevent stopping early just because
  the first few weeks happened to look favorable (or unfavorable).
- **No live capital deployment of any kind during this evaluation** —
  reinforced explicitly here on top of Section 2's structural
  enforcement, because this is also a *procedural* commitment: the
  evaluation period's entire purpose is invalidated if live capital is
  deployed on the same signal concurrently, even via a different,
  unrelated code path, since that would contaminate any comparison of
  "paper behavior vs. backtest assumptions" with a second, live
  data point that this spec's design has no visibility into.
- **What is compared, and against what:**
  - *Slippage*: observed fill price vs. the price used at signal-time
    (the price of the bar that generated the RSI signal), compared
    against Jarvis's 1bp assumption (`DEFAULT_COST_BPS` in
    `backtest_engine.py`) and the LEAN mirror's disclosed $429.13/20-order
    average (~$21.50/order) as two independent reference points
    (`docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` Section 5).
  - *Missed fills*: any signal that was correctly computed and approved
    by the risk manager but did not result in a filled order (broker
    rejection, market-hours miss, data outage) — counted and reasoned
    individually, not averaged away.
  - *Order timing*: actual submission timestamp vs. market open, and
    fill timestamp vs. submission timestamp, compared against the
    close-to-close assumption in Jarvis's vectorized backtest and the
    MarketOnOpen conversion disclosed in the LEAN mirror
    (`docs/QUANTCONNECT_LEAN_EEM_COMPARISON.md` Section 4) — both are
    already-known sources of expected, small timing divergence; this
    tracking exists to confirm the divergence stays small, not to
    re-discover that it exists.
  - *Drawdown*: observed paper-account peak-to-current drawdown vs. the
    backtest's -9.9% OOS figure and the LEAN mirror's -29.25%
    full-period figure — both cited as reference bands, not hard
    pass/fail thresholds on their own (a short 3-month paper window is
    not long enough to expect to reproduce a multi-year drawdown
    statistic; what matters is whether the *shape* of behavior — e.g.
    exiting on RSI mean-reversion in the way the backtest assumes  — is
    consistent, not whether the exact percentage matches).
  - *Signal frequency*: observed trade count over the 3-month window vs.
    the backtest's expected pace (~55 trades / 1,134 days ≈ roughly 1
    trade per 3-4 weeks; over a 3-month/~65-trading-day window, a rough
    expectation of 0-3 trades is consistent with that pace — this is a
    sanity check for wildly divergent frequency, not a strict count).
- **Fail conditions (any one of these triggers a FAIL verdict, not a
  judgment call):**
  1. Any kill-switch event (Section 10) triggered by an automatic
     breaker (drawdown, daily loss, reconciliation failure, unhandled
     exception, stale-data pattern) during the evaluation window.
  2. Observed slippage materially exceeds both reference points above
     (e.g. realized cost per trade is a large multiple of either the
     1bp Jarvis assumption or the LEAN $21.50/order average) on more
     than an isolated single trade.
  3. Any missed fill caused by a plumbing failure (as opposed to a
     legitimate market-hours/data-outage skip that was correctly
     logged and did not silently fail) — i.e., any bug-driven trade
     that should have fired and did not, or fired when it should not
     have.
  4. Observed trade frequency is wildly inconsistent with backtest
     expectation in a way not explained by the specific market
     conditions of the evaluation window (e.g. zero signals across the
     entire 3 months in a period where EEM visibly touched RSI 30/70
     multiple times, suggesting a live-data or live-computation bug
     rather than genuine inactivity).
  5. Any reconciliation mismatch (Section 9) that required manual
     `adopt_broker_state()` recovery more than once during the
     evaluation window (a single, explained, promptly-resolved
     mismatch is a yellow flag worth noting in the report; a recurring
     pattern is a FAIL).
- **PASS verdict**: no fail condition triggered, AND the qualitative
  comparisons above (slippage, timing, drawdown shape, frequency) are
  judged consistent with backtest assumptions in the written Phase 5
  report — a PASS is a necessary, not sufficient, condition for even
  considering Phase 6; it does not itself authorize live trading.

---

## Explicit scope boundary

- This document is a design specification only. No implementation code
  for any phase has been written.
- No strategy logic was created, modified, or approximated — the spec
  requires reusing the existing, unmodified `strategy_rsi_revert`
  function from `edge_hunting/strategy_library.py`.
- No `.env` file was read, created, or edited in producing this spec.
- No Alpaca API key, secret key, or other credential was requested,
  viewed, or referenced in this document.
- `ALPACA_CONFIRM_LIVE` is assumed to remain `false`/unset throughout;
  nothing in this spec sets it, checks its value in a way that would
  change behavior toward live trading, or recommends changing it.
- No trades — paper or live — have been placed as a result of this
  document.
- Implementation of Phase 1 is complete upon approval of this document;
  Phases 2 through 6 each require their own separate, explicit approval
  before any corresponding code is written.
