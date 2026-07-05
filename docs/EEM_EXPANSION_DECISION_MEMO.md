# EEM Expansion — Decision Memo

**Status: DECISION MEMO ONLY. No strategy code was edited. No backtests
were re-run. No parameters were tuned. No new candidate is promoted to
paper trading. Paper trading and live trading remain disabled. This
document only reads and interprets outputs that already existed before
it was written.**

## Sources read (no backtests re-run; all files already existed)

- `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
- `docs/EEM_MEAN_REVERSION_EXPANSION_SPEC.md`
- `reports/eem_expansion/eem_expansion_summary.json`
- `reports/eem_expansion/eem_expansion_report.md`
- `reports/eem_expansion/eem_expansion_results.csv`

---

## 1. Did the original EEM RSI edge generalize?

**Yes, partially confirmed, with an important caveat.** The `rsi_revert`
family was classified **GENERALIZES** across the 13-asset EM universe: 9
of 13 assets (EEM, VWO, IEMG, EWZ, EWT, EWY, EWW, EZA, TUR) produced at
least one independent (non-`DUPLICATE_SIGNAL`) survivor through the full
funnel → bootstrap → slippage → benchmark pipeline, and the pooled
parameter-sensitivity flag for `rsi_revert` came back **ROBUST**, not
`LIKELY_CURVE_FIT`. This clears the spec's "at least 4 of 13" bar for
GENERALIZES by a wide margin (9 of 13).

The caveat: of the 30 gate-clearing configs, only 3 assets (EWZ, EWW,
TUR) produced a strictly `UNIQUE_SIGNAL` survivor. The remaining 27,
across EEM/VWO/IEMG/EWT/EWY/EZA, are `NEAR_DUPLICATE` of one another —
expected, since these are all broad or overlapping EM baskets, and
exactly the effect the spec's duplicate-signal gate (Section 5.7) was
designed to catch and disclose rather than let inflate the count. The
generalization finding is real by the pre-registered test, but it rests
more heavily on a handful of independent data points (EWZ, EWW, TUR)
than the raw "9 of 13 assets" headline number alone would suggest.

## 2. Is EEM an outlier?

**No.** The Section 6.3 EEM-outlier check reports `NO_OUTLIER_DETECTED`:
EEM's mean OOS Sharpe across the 80-config RSI center grid is 0.360,
versus a mean of 0.344 (std 0.157) across the other 12 assets — EEM is
essentially at the pack average, not more than one standard deviation
above it (threshold for outlier status was 0.501). EEM is not secretly
propping up the pooled `rsi_revert` result; the effect shows up on other
EM assets at a comparable strength.

## 3. Which strategy family generalized?

**`rsi_revert` only.** It is the sole family among the seven tested that
was classified `GENERALIZES` (9 independent survivor assets, ROBUST
sensitivity flag, no EEM-outlier downgrade applied).

## 4. Which families failed to generalize?

All six other mean-reversion families tested — `percent_b_revert`,
`bollinger_revert`, `keltner_revert`, `zscore_revert`, `cci_revert`, and
`williams_r_revert` — were classified
`DOES_NOT_GENERALIZE_LIKELY_SINGLE_ASSET_ARTIFACT`, each with **0**
independent survivor assets across the entire 13-asset universe, despite
each family's own sensitivity flag also coming back ROBUST (a ROBUST
sensitivity flag with zero survivors simply means the family's few
tested configs behaved consistently with each other — consistently
unable to clear the funnel/bootstrap/benchmark gates on any EM asset in
this universe, not that any of them worked).

## 5. How many assets showed independent evidence?

**9 of 13** non-RSX assets in the universe produced at least one
survivor for `rsi_revert` that was not itself a `DUPLICATE_SIGNAL` of
another survivor: EEM, VWO, IEMG, EWZ, EWT, EWY, EWW, EZA, TUR. Of
those 9, only **3** (EWZ, EWW, TUR) are strictly `UNIQUE_SIGNAL`
(genuinely low pairwise correlation to every other survivor); the other
6 carry a `NEAR_DUPLICATE` flag against at least one other survivor,
meaning they corroborate the effect but should not each be counted as a
fully independent confirmation with equal weight. RSX itself was
excluded from every aggregate calculation per the spec's delisting rule
and contributed no evidence either way.

## 6. Why are the 30 gate-clearing candidates not automatically promoted?

The approved spec (Section 7.1, "anti-overfitting warnings") and the
existing 10-point approval bar in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
both explicitly forbid this shortcut, for three concrete reasons visible
in this expansion's own output:

1. **Multiple-comparisons problem.** 1,183 configs were tested. Finding
   30 that pass the funnel → bootstrap → slippage → benchmark chain by
   chance alone is exactly the kind of result the spec warned would occur
   at standard significance levels; passing this pipeline is necessary
   but was never treated as sufficient for promotion on its own, for any
   candidate in this codebase, EEM's own primary setting included.
2. **Duplication inflation.** 27 of the 30 candidates are `NEAR_DUPLICATE`
   of another candidate already in the list (mostly of each other within
   the same broad-EM-basket group). Counting each of these as an
   independently-earned paper-test slot would multiply exposure to what
   is substantially one underlying signal, not diversify it.
3. **No future out-of-sample confirmation yet exists for any of the 29
   new configs.** Every one of them — unlike the original EEM
   `rsi_revert(14,30/70)` setting, which has already gone through the
   full independent scorecard process in
   `docs/JARVIS_PAPER_TRADING_CANDIDATES.md` — would need that same
   independent scrutiny (and, per Section 7.1 of the spec, its own
   future OOS confirmation) before being treated as paper-test-ready.
   This expansion's job was to test generalization, not to fast-track
   new candidates around the process the original candidate went through.

## 7. What remains the single approved paper-test candidate?

**EEM `rsi_revert(window=14, oversold=30, overbought=70)`** —
`APPROVED_FOR_PAPER_TEST (PRIMARY)` in
`docs/JARVIS_PAPER_TRADING_CANDIDATES.md`. This expansion did not alter,
re-score, or re-run that candidate's classification anywhere; it appears
in the expansion's own results as the same config, flagged
`is_original_eem_setting: true`, `ROBUST_CANDIDATE`, `NEAR_DUPLICATE` —
consistent with, not different from, its existing approved status.

## 8. Which candidates are research candidates only?

All **30 configs** that cleared every automated gate in this expansion —
**including the original EEM primary setting's own entry in this
expansion's results** — are, for purposes of *this expansion's own
output*, research-only findings that support the generalization
conclusion; they are not a new slate of paper-test approvals. Concretely,
that is:

- 6 EEM `rsi_revert` neighborhood variants (1 of which is the already-
  approved primary setting — no change to its status)
- 2 VWO `rsi_revert` variants
- 3 IEMG `rsi_revert` variants
- 1 EWZ `rsi_revert` variant (`UNIQUE_SIGNAL`)
- 5 EWT `rsi_revert` variants
- 1 EWY `rsi_revert` variant
- 1 EWW `rsi_revert` variant (`UNIQUE_SIGNAL`)
- 9 EZA `rsi_revert` variants
- 1 TUR `rsi_revert` variant (`UNIQUE_SIGNAL`)

Any one of the 29 *new* configs in this list that a future decision-maker
wants to consider for paper testing would need to go through its own
independent scorecard process — the same one already applied to the
original EEM setting in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md` — not
be promoted on the strength of appearing in this list alone.

## 9. What would invalidate this edge in future testing?

- **RSI-specific artifact, not EM-specific.** If a future test found that
  `rsi_revert`'s apparent EM generalization also shows up at a similar
  rate on a matched control basket of *non*-EM, non-mean-reversion-prone
  assets (e.g., broad developed-market sector ETFs), that would suggest
  the effect is closer to "RSI mean reversion works reasonably often on
  liquid ETFs in general" rather than an EM-structural effect specifically.
  This expansion did not test that control group.
- **Duplication collapse.** If a stricter duplicate-signal threshold (or
  a longer lookback window revealing higher true correlation) reclassified
  the 6 `NEAR_DUPLICATE` EEM/VWO/IEMG/EWT/EWY/EZA-family survivors as
  outright `DUPLICATE_SIGNAL`, the independent-survivor count could drop
  from 9 toward the 3 `UNIQUE_SIGNAL` assets (EWZ, EWW, TUR) alone, which
  would fall the classification from GENERALIZES to
  PARTIALLY_GENERALIZES per the spec's own Section 6.2 thresholds.
- **Sample-period dependency.** All 1,183 backtests share the same
  2010–2025 cached window and the same six-regime historical sample. A
  genuinely different EM stress regime (e.g., a multi-year EM debt crisis
  or currency-crisis cluster materially unlike anything in 2010–2025)
  could invalidate the bootstrap SOLID and regime-decomposition results
  for some or all of the 9 survivor assets, exactly as already disclosed
  for the original EEM candidate.
- **Data-source dependency.** All data came from a single source
  (`yfinance`, `auto_adjust=True`) through the existing
  `edge_hunting/data_loader.py`. A material discrepancy in bar data,
  corporate-action adjustment, or survivorship handling from an
  independent data source could change individual asset results,
  especially for the thinner-history/thinner-liquidity assets (IEMG,
  INDA, EIDO, EZA) already flagged as lower-confidence in the spec.
- **Thin-sample survivors.** TUR and EZA carry the noisiest, thinnest
  histories/liquidity in the universe (per spec Section 1); if either
  asset's survivor result were later shown to be a data or liquidity
  artifact specific to that ticker, the `UNIQUE_SIGNAL` count (currently
  3: EWZ, EWW, TUR) would shrink toward 2, weakening the case for
  genuinely independent confirmation beyond EWZ/EWW.

## 10. What is the recommended next validation step?

**Independent data/source validation before any further internal
analysis or any paper-trading decision** — specifically:

1. **QuantConnect/LEAN mirror test.** Re-implement the EEM
   `rsi_revert(14,30/70)` primary candidate (and, time permitting, the 3
   `UNIQUE_SIGNAL` expansion survivors — EWZ, EWW, TUR — as the strongest
   independent-evidence points) on an independent backtesting engine and
   independent data pipeline (QuantConnect/LEAN), using the same
   parameters, same walk-forward windowing logic, and same cost
   assumptions, to confirm the result is not an artifact specific to this
   codebase's own `walk_forward.py`/`data_loader.py` implementation.
2. **Norgate (or equivalent survivorship-bias-free vendor) data
   cross-check**, particularly for the corporate-action and
   adjusted-close handling on the longer-history assets (EEM, VWO, EWZ,
   FXI, EWT, EWY, EWW, ILF), to rule out a `yfinance`-specific
   adjustment artifact driving part of the result.
3. Only **after** both independent checks corroborate the primary EEM
   setting (and, ideally, at least the EWZ/EWW/TUR unique-signal
   survivors) should any of the 29 new expansion candidates be considered
   for their own full, independent scorecard process per
   `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`'s existing 10-point bar —
   not before.

This is a deliberately more conservative next step than moving directly
to paper trading: it targets the two things this internal expansion
*cannot* rule out on its own — implementation-specific backtest bugs and
single-vendor data artifacts — before spending any paper-trading capital
allocation slot on a new candidate.

---

## Summary position (restated)

- The original EEM `rsi_revert(14,30/70)` **remains the only approved
  primary paper-test candidate.** This memo changes nothing about that
  classification.
- The EEM `rsi_revert(14,25/70)` backup **remains classified
  `BACKUP_PENDING_BOOTSTRAP`** in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  — it has not been bootstrap-tested as of the sources read for this
  memo, and this expansion did not run that specific test either (the
  expansion's own 25/70-adjacent grid points are different `window`
  values, not a re-test of the exact pending backup config). It remains
  blocked pending its own bootstrap stress test, unchanged.
- The 30 expansion candidates **prove structural support for the
  `rsi_revert`-on-EM-assets effect, not automatic paper-trading
  approval** for any of the 29 configs beyond the already-approved
  primary setting.
- The recommended next validation step is **independent data/source
  validation** — QuantConnect/LEAN mirror testing and/or Norgate data
  cross-check — before any new candidate from this expansion is
  considered for paper testing.

## Explicit scope boundary

- This memo is a read-only interpretation of already-existing report
  files. No code in `edge_hunting/` or `strategies/` was edited to
  produce it.
- No backtest was re-run and no parameter was tuned to produce this memo.
- No candidate's classification in `docs/JARVIS_PAPER_TRADING_CANDIDATES.md`
  was changed by this memo.
- Paper trading and live trading remain disabled; nothing in this memo
  authorizes either.
