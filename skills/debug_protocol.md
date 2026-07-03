# Debug Protocol — Emergency Manual

Synthesized 2026-07-02 from `debugging_dump.txt` (the creator's Debug Playbook),
the installed skills pack conventions, and protocols validated in this repo's
own sessions. Sections marked **[repo-validated]** are not from the dump — the
dump contains no loop-breaking protocol, so that gap is filled from practices
proven here.

---

## 1. Triage checklist (run in order, always)

1. **Read the actual error.** Exact message + full traceback before any hypothesis.
2. **Find what it was doing:** last entry in `logs/main.log` (or `logs/trading.jsonl` here).
3. **Find what fired first:** `logs/alerts.jsonl` — breaker type, DD, equity, regime are logged on every fire.
4. **Check state integrity:** `state_snapshot.json` timestamp — recent = clean exit, stale = killed.
5. **Reproduce before believing:** clean environment, different seed, then debug.

When asking for help, include: exact traceback, triggering command, last 50 log
lines, what you already tried, Python version + `pip freeze`.

---

## 2. Interpreting cryptic errors (symptom → cause tables)

### Broker order rejections

| Rejection | Cause → Fix |
| --- | --- |
| `insufficient_buying_power` | leverage over broker limit → reduce `max_leverage` |
| `not_tradeable` | symbol halted/delisted → remove from universe |
| `wash_trade` | opposite direction too soon → increase duplicate window |
| `market_closed` | `is_market_open()` wrong → check session logic |
| `invalid_stop` | stop on wrong side of price or too close → check stop construction |
| `bid_ask_spread_too_wide` | our own pre-trade check → wait or skip, do not loosen |

### Backtest Sharpe > 2.5 (daily rebalancing) — assume look-ahead until proven otherwise

1. `pytest tests/test_look_ahead.py -v` — if it fails, that's the answer.
2. Grep `core/` + `data/` for `model.predict` / `hmm.predict` (only `predict_regime_filtered` is approved — Viterbi sees the whole sequence).
3. Grep for `StandardScaler().fit_transform` on a full frame (future data in the mean) — must be rolling z-scores (252w).
4. Grep for `.shift(-` (negative shift pulls the future into the present).
5. Slippage: 5 bps is optimistic below SPY liquidity — retry at 10–15 bps.
6. Backtest end date within 6 months of HMM training = training contamination.
7. Still >2.5? Reproduce in a clean env with a different seed before believing it.

### Look-ahead test fails on code that "looks correct"

- The test names the differing value — start there, not in the code.
- Specific feature flagged → hunt `fit_transform`, negative shifts, `center=True`, `bfill`.
- Fails on some bars only → warmup NaN handling: **accept the NaN**, never fill with forward-looking values.
- Pattern hit inside a comment/docstring → AST scan too aggressive; tighten pattern.

### Paper vs backtest divergence

- **Paper worse:** slippage too optimistic (compare fills vs bar closes), missing 1-bar fill delay, hidden look-ahead, survivorship in the test universe.
- **Paper better:** Alpaca paper fills at mid (live fills at bid/ask — live WILL be worse), or you're running different code than you backtested — diff it.

### HMM flickering / dashboard stuck UNCERTAIN

- Too many regime candidates (BIC overfit) → `n_candidates: [3, 4]`, retrain.
- Under ~504 daily bars of training data → get more history.
- Features with lookback < 5 bars are noise → remove or smooth.
- Always-low probabilities in `logs/regime.log` → retrain with more data before touching `min_confidence`.
- Flicker lock engaged → check `get_regime_flicker_rate()`; the lock is doing its job.

---

## 3. Loop breaking — stopping infinite repair loops **[repo-validated]**

(Not covered by the creator's playbook; these rules are from this repo's operating discipline.)

1. **Two-strike rule:** the same fix attempted twice with the same failure means the
   hypothesis is wrong. STOP. Re-read the actual error; form a new hypothesis before
   any third attempt.
2. **Never bypass to converge.** Deleting a failing test, loosening a threshold, or
   adding `--no-verify` to make an error go away is not a repair — it is disabling
   the smoke alarm. The rules exist because someone already made that mistake.
3. **Reduce before retrying:** reproduce with the smallest input that still fails
   (one symbol, 100 bars, one window). Loops persist because each iteration takes
   minutes and hides the signal.
4. **Change exactly one variable per attempt** — same seed, same data, one delta —
   or the loop teaches you nothing.
5. **Environment vs code:** if the error mutates run-to-run with no code change, stop
   editing code — suspect the environment (see terminal recovery below).
6. **Escalate after 3 distinct failed hypotheses:** stop repairing, write down the
   evidence, and question the design instead ("this parameter cannot be optimized
   into compliance" was the correct exit from the SOXL grid loop — the answer was
   NO, not another iteration).

### Windows/PowerShell environment loop (this repo, recurring)

Symptom: `The term '...' is not recognized` for commands that just worked, mojibake
box characters, empty output from commands that ran.

- This is terminal corruption, NOT a code bug. Do not edit code in response.
- Recovery: run a bare `Get-Location`; retry the identical command once.
- Long/unicode-emitting runs: redirect to file (`*> out.txt`) and read back with
  `open(path, encoding='utf-16', errors='ignore')`; set `$env:PYTHONIOENCODING='utf-8'`.
- Verify side effects (output files, exit codes) before concluding a run failed.

---

## 4. State restoration — crash mid-trade

### Diagnostic order (creator's playbook)

1. `logs/main.log` last entry — what was it doing?
2. `logs/alerts.jsonl` — what fired right before?
3. `state_snapshot.json` timestamp — clean save or hard kill?
4. Linux: `journalctl -u your-bot-service` for OOM kills / systemd restarts.
5. **Broker web UI** — look for orphan positions the bot doesn't know about.

### Recovery rules (playbook + review-for-prod skill, Section 7)

- Save `state_snapshot.json` on SIGINT/SIGTERM; on SIGINT also cancel pending
  orders, keep positions, log everything.
- On startup: **reconcile against actual broker positions BEFORE doing anything
  else.** If the broker holds positions the bot doesn't know about → HALT and
  alert. Never trade against an unreconciled book.
- Test the path deliberately: SIGKILL the process, restart, verify it neither
  double-enters nor ignores an open position. If it does either, that is a
  critical (go-live-blocking) bug.
- Prevention: systemd/supervisord auto-restart + reconcile-on-startup.

### Circuit breaker / lock file protocol

- Every fire logs breaker type, actual DD, equity, and regime — read it.
- Daily DD is measured from **daily peak equity**, not from the open — intraday
  highs count.
- Peak-DD lock file: **read the file contents and understand the cause FIRST,
  then delete it manually.** The manual step is the review. Never automate or
  skip it.

---

## 5. Adoption notes (delta vs current practice)

Already our practice (converges with the playbook): forward-filter only, mandatory
look-ahead test, honest slippage, lock-file semantics, structured JSON logs.

Adopted from this ingestion:

- The order-rejection table (§2) as the first stop for broker errors.
- The Sharpe > 2.5 decision tree, including the training-contamination check
  (backtest end within 6 months of HMM training) — previously not on our list.
- "Accept the NaN" as the standard warmup ruling.
- The help-request template (§1).

Known gaps in OUR repo surfaced by this manual: no `state_snapshot.json`
implementation and no startup reconciliation exist yet — flagged by
review-for-prod as go-live blockers. Build before any live consideration.
