const assert = require("node:assert");
const reducers = require("../ui02_desktop_shell/static/state.js");

function test(name, fn) {
  try {
    fn();
    console.log("ok - " + name);
  } catch (error) {
    console.error("not ok - " + name);
    throw error;
  }
}

const envelope = {
  provider_validation_status: "pending",
  source_mode: "fixture",
  generated_at: "2026-07-21T00:00:00Z",
  safety_state: {
    live_trading_enabled: false,
    is_live: false,
    live_trading_status: "LIVE TRADING: DISABLED",
  },
  warnings: ["partial-evidence"],
  errors: [],
  data: {
    status: "available",
    is_live: false,
    ui03: {
      schema_version: "ui03.research_workbench.view_model.v1",
      status: "available",
      generated_at: "2026-07-21T00:00:00Z",
      observation_time: "2026-07-11T06:26:51Z",
      freshness: { state: "stale", reason: "committed_offline_evidence_only" },
      provenance: {
        source_ids: ["BR-29"],
        source_paths: ["reports\\br29_offline_snapshot_research_replay_evidence_pack\\offline_snapshot_research_replay_evidence_pack.json"],
        validation_state: "partial-evidence",
        provider_validation: "pending",
      },
      candidates: [
        { id: "c-2", rank: 2, symbol: "SPY", engine: "offline_snapshot_replay", strategy_family: "index_etf_replay", lifecycle_state: "paper_only", risk_state: "PAPER_ONLY", validation_state: "partial-evidence", freshness: "stale", source_mode: "fixture" },
        { id: "c-1", rank: 1, symbol: "QQQ", engine: "offline_snapshot_replay", strategy_family: "index_etf_replay", lifecycle_state: "blocked", risk_state: "BLOCKED_BY_SAFETY_GATE", validation_state: "blocked", freshness: "stale", source_mode: "fixture", rejection_reasons: ["missing_outcomes"] },
      ],
      theses: [
        { id: "t-1", candidate_id: "c-1", summary: "review only", confidence: null, uncertainty: "missing outcomes", status: "HUMAN_REVIEW_REQUIRED" },
      ],
      market_regime: { label: "unavailable", confidence: null, status: "unavailable", contradicting_factors: ["no evidence"] },
      lifecycle: { stage_counts: { blocked: 1, paper_only: 1 }, allowed_transitions: [] },
    },
  },
};

test("UI-03 normalizer preserves provenance, freshness, pending provider, and disabled safety", () => {
  const vm = reducers.normalizeUi03Envelope(envelope, "screener");

  assert.equal(vm.schemaVersion, "ui03.research_workbench.view_model.v1");
  assert.equal(vm.providerValidationStatus, "pending");
  assert.equal(vm.isLive, false);
  assert.equal(vm.liveTradingStatus, "LIVE TRADING: DISABLED");
  assert.equal(vm.freshnessState, "stale");
  assert.equal(vm.provenance.validationState, "partial-evidence");
  assert.equal(vm.provenance.sourceIds[0], "BR-29");
});

test("UI-03 filtering and sorting are deterministic and in-memory only", () => {
  const vm = reducers.normalizeUi03Envelope(envelope, "screener");
  const filtered = reducers.filterCandidates(vm.candidates, { query: "qqq", riskState: "BLOCKED_BY_SAFETY_GATE" });
  const sorted = reducers.sortCandidates(vm.candidates, "rank", "asc");

  assert.deepEqual(filtered.map((item) => item.id), ["c-1"]);
  assert.deepEqual(sorted.map((item) => item.id), ["c-1", "c-2"]);
  assert.deepEqual(reducers.candidateOptions(vm.candidates, "lifecycleState"), ["blocked", "paper_only"]);
});

test("UI-03 candidate selection falls back without persistence", () => {
  const vm = reducers.normalizeUi03Envelope(envelope, "lifecycle");

  assert.equal(reducers.selectCandidate(vm.candidates, "c-2").symbol, "SPY");
  assert.equal(reducers.selectCandidate(vm.candidates, "missing").id, "c-2");
});

test("UI-03 thesis uncertainty and regime no-data do not invent confidence", () => {
  const vm = reducers.normalizeUi03Envelope(envelope, "analyst-theses");

  assert.equal(vm.theses[0].confidence, null);
  assert.equal(vm.theses[0].uncertainty, "missing outcomes");
  assert.equal(vm.marketRegime.label, "unavailable");
  assert.equal(vm.marketRegime.confidence, null);
});

test("unsafe UI-03 envelope is blocked by normalizer", () => {
  const unsafe = JSON.parse(JSON.stringify(envelope));
  unsafe.safety_state["live_trading_" + "enabled"] = Boolean(1);

  const vm = reducers.normalizeUi03Envelope(unsafe, "research");
  assert.equal(vm.status, "blocked");
  assert.equal(vm.safe, false);
});
