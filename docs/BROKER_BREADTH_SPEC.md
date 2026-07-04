# Broker Breadth (IBKR / TradeStation) — Architecture Specification

> **Status:** DRAFT — awaiting user approval before implementation.
> **Origin:** `docs/SKOOL_VS_JARVIS_IMPLEMENTATION_AUDIT.md`, Finding 11 (Missing).
> **Goal:** Optionality, not urgency. Alpaca is fully wired and is the only
> broker in active use. This spec exists so that adding a second broker is a
> reviewed decision, not an ad-hoc one, whenever it's actually needed.

---

## 1. Purpose

`broker/` currently contains only `__init__.py`, `alpaca_client.py`, and
`base.py`. The Skool gap report flags IBKR and TradeStation as common
broker integrations this framework does not yet support. This is a pure
breadth gap — no defect, no urgency — but this spec documents the intended
approach so it's ready to execute the moment a second broker is actually
needed (e.g., options/futures support that Alpaca doesn't offer, or IBKR's
lower-cost execution for a specific asset class).

## 2. Design Principles

1. **Use the existing abstraction, don't rebuild it.** `broker/base.py`
   already defines `BaseBroker`, an abstract class that
   `broker/alpaca_client.py`'s `AlpacaBroker` implements. A new adapter
   implements the SAME interface — no changes to `BaseBroker` itself unless
   a genuinely new capability is required (see §5).
2. **Never-default-live carries over exactly.** Whatever new adapter is
   built MUST replicate the dual-gate live-trading protection already in
   `AlpacaBroker.__init__` (paper=True default + an explicit
   `..._CONFIRM_LIVE` environment variable check before any live endpoint is
   used). This is non-negotiable per `01_CLAUDE.md` rule 4.
3. **Use the existing skill.** This environment already has an
   `add-broker-adapter` skill (per `SKOOL_CODE_PATTERNS.md`'s "Claude
   Skills" reference and confirmed present in this session's available
   skills) specifically designed to scaffold this — the skill should be
   invoked when this work is actually greenlit, rather than freehand-writing
   a new adapter.
4. **No changes to the rest of the system.** `execution/multistrat_engine.py`,
   `core/risk_manager.py`, and every strategy consume `BaseBroker` through
   its abstract interface only — adding a new adapter should require zero
   changes to any of those files.

## 3. Candidate brokers (from the Skool gap report)

| Broker | Primary use case | Notes |
|---|---|---|
| Interactive Brokers (IBKR) | Multi-asset (equities, options, futures, forex), lower commissions at scale | Requires either the IBKR TWS/Gateway API (`ibapi`) or a wrapper like `ib_insync`/`ib_async`. More complex auth/session model than Alpaca's REST API (needs a running Gateway/TWS process). |
| TradeStation | Equities + options, historically popular for retail algo trading | REST API available; OAuth2 auth flow (different from Alpaca's API-key model). |

## 4. Module Map (what exists vs. what's new)

| Component | Status | Module |
|---|---|---|
| `BaseBroker` abstract interface | **exists (reused unchanged)** | `broker/base.py` |
| Broker registry (`get_broker()`) | **exists (extended, not rewritten)** | `broker/__init__.py` |
| Alpaca adapter (reference implementation) | **exists (reused unchanged, as a pattern reference)** | `broker/alpaca_client.py` |
| IBKR adapter | **new (if/when approved)** | `broker/ibkr_client.py` |
| TradeStation adapter | **new (if/when approved)** | `broker/tradestation_client.py` |

## 5. Proposed interface conformance checklist

Whichever broker is added first, the new adapter must implement (matching
`broker/base.py`'s `BaseBroker` contract, confirmed to include at minimum):
- `get_account()` — fail-fast on bad credentials (mirrors `AlpacaBroker`'s
  pattern of calling this in `__init__` to validate the connection eagerly).
- `get_bars(symbols, limit)` — recent bars per symbol; failed symbols logged
  and omitted, never fabricated (matches `AlpacaBroker`'s documented
  behavior).
- `is_market_open()`
- Order submission / cancellation methods consumed by
  `execution/multistrat_engine.py`'s executor path (exact method signatures
  TBD by reading `broker/base.py`'s full abstract method list before
  implementation — not fully enumerated in this spec since it wasn't
  re-read line-by-line during the audit).

**Before implementation:** read the complete `broker/base.py` abstract
method list to produce an exact conformance checklist — this section is
intentionally a placeholder pending that read.

## 6. Live-trading safety requirements (mandatory, non-negotiable)

Whatever adapter is built must replicate ALL of the following, confirmed
present in `broker/alpaca_client.py`:
1. `paper: bool = True` constructor default.
2. An explicit environment-variable confirmation gate
   (`ALPACA_CONFIRM_LIVE` equivalent, e.g. `IBKR_CONFIRM_LIVE` /
   `TRADESTATION_CONFIRM_LIVE`) that must equal an exact string (`"YES"`)
   before the live endpoint/session is used — raising `PermissionError`
   otherwise.
3. `broker/__init__.py`'s `get_broker()` registry function must continue to
   default to `paper=True` for any new broker name added.
4. A printed confirmation message on connect showing PAPER vs LIVE status
   and account buying power (matching `AlpacaBroker`'s existing UX).

## 7. What this does NOT do

- ❌ Does not implement anything yet — this is a specification only.
- ❌ Does not modify `broker/base.py`'s abstract interface unless a genuine
  new capability is discovered to be required (e.g., options-chain lookups
  that Alpaca's interface doesn't need) — and if so, that change should be
  proposed and approved separately, since it would affect `AlpacaBroker` too.
- ❌ Does not change `execution/multistrat_engine.py`, `core/risk_manager.py`,
  or any strategy.
- ❌ Does not select which broker (IBKR vs TradeStation) to build first —
  that decision should be driven by the actual asset-class need at the time
  (e.g., IBKR if options/futures become in-scope; TradeStation if a
  cheaper-equities alternative to Alpaca is wanted).

## 8. Trigger condition

This spec should be picked up and actually implemented only when a concrete
need arises (a strategy requiring an asset class Alpaca doesn't support, or
an operational reason to diversify broker risk) — not preemptively. At that
point, invoke the `add-broker-adapter` skill rather than hand-building from
scratch.

---

**Approval required:** Do not implement until this architecture is approved
AND a concrete trigger condition (§8) exists.
