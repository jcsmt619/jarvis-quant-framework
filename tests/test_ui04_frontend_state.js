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
    broker_order_call_performed: false,
    real_paper_wrapper_connected: false,
    real_paper_wrapper_attempted: false,
    real_paper_order_submitted: false,
    live_trading_status: "LIVE TRADING: DISABLED",
  },
  warnings: ["stale"],
  errors: [],
  data: {
    status: "available",
    is_live: false,
    ui04: {
      schema_version: "ui04.operator_workbench.view_model.v1",
      status: "available",
      source_identifier: "UI04-CANONICAL-OFFLINE-FIXTURE",
      generated_at: "2026-07-21T00:00:00Z",
      observation_time: "2026-07-11T06:26:51Z",
      freshness: { state: "stale", reason: "committed_offline_evidence_only" },
      validation_state: "partial-evidence",
      safety_labels: ["RESEARCH_ONLY", "MONITOR_ONLY", "PAPER_ONLY", "HUMAN_REVIEW_REQUIRED", "BLOCKED_BY_SAFETY_GATE"],
      provenance: { source_ids: ["BR-29"], source_paths: ["reports\\br29.json"], validation_state: "partial-evidence", provider_validation: "pending" },
      risk_gate: { decision: "BLOCKED_BY_SAFETY_GATE", blocked_reasons: ["provider_validation_pending"], required_labels: ["RESEARCH_ONLY"], provider_gate: "blocked", data_freshness_gate: "stale", model_validation_gate: "partial-evidence", portfolio_risk_gate: "unavailable", human_review_requirement: "HUMAN_REVIEW_REQUIRED", evidence_refs: ["BR-29"] },
      portfolio: { snapshot_id: "snap", mode: "PAPER_ONLY", freshness: "stale", position_count: 1, positions: [], cash: { state: "unavailable" }, gross_exposure: { state: "unavailable" }, net_exposure: { state: "unavailable" }, allocation: [{ bucket: "Moonshot Engine", state: "separate", count: 1 }], wealth_engine: { state: "separate" }, moonshot_engine: { state: "separate" }, warnings: ["cash_unavailable"] },
      alerts: [{ id: "a1", severity: "critical", category: "safety", state: "open-read-only", created_at: "2026-07-11T06:26:51Z", freshness: "stale", source: "BR-29", related: "risk_gate", human_review_required: true, evidence_details: ["live_trading_disabled"] }],
      models: [{ id: "m1", family: "offline", version: "v1", validation_state: "partial-evidence", drift_state: "unavailable", supported_strategy_families: ["index"], last_validated_at: "2026-07-11T06:26:51Z", freshness: "stale", warnings: ["drift_unavailable"], promotion_eligibility: "blocked", evidence_refs: ["BR-29"] }],
      performance: { metric_set_id: "perf", return_series: { state: "unavailable" }, warnings: ["do_not_infer_performance_from_incomplete_outcomes"] },
      backtests: [{ run_id: "bt1", strategy_family: "index", symbols: ["QQQ"], result_label: "HUMAN_REVIEW_REQUIRED", promotion_gate_state: "blocked", insufficient_trade_warning: "trade_count_unavailable" }],
      paper_activity: [{ paper_run_id: "p1", approval_or_review_state: "HUMAN_REVIEW_REQUIRED", ledger_refs: ["BR-22"], proposed_actions: ["review"], simulated_fills: "unavailable", rejected_actions: ["live_order_routing"], safety_gate_reasons: ["BLOCKED_BY_SAFETY_GATE"], timestamps: ["2026-07-11T06:26:51Z"], freshness: "stale" }],
      options: { chain_quality_state: "no-data", delta: "unavailable", implied_volatility: "unavailable", risk_warnings: ["option_chain_data_unavailable"] },
      moonshot_research: [{ candidate_id: "c1", underlying: "QQQ", thesis: "review", strategy_family: "LEAPS_RESEARCH", scenario_outcomes: "unavailable", risk_state: "HUMAN_REVIEW_REQUIRED", lifecycle_state: "paper_only" }],
    },
  },
};

test("UI-04 normalizer preserves provenance, freshness, provider pending, and disabled safety", () => {
  const vm = reducers.normalizeUi04Envelope(envelope, "risk-gate");

  assert.equal(vm.schemaVersion, "ui04.operator_workbench.view_model.v1");
  assert.equal(vm.sourceIdentifier, "UI04-CANONICAL-OFFLINE-FIXTURE");
  assert.equal(vm.providerValidationStatus, "pending");
  assert.equal(vm.isLive, false);
  assert.equal(vm.liveTradingStatus, "LIVE TRADING: DISABLED");
  assert.equal(vm.freshnessState, "stale");
  assert.equal(vm.provenance.sourceIds[0], "BR-29");
  assert.equal(vm.validationState, "partial-evidence");
});

test("UI-04 risk gate and portfolio separation stay blocked and read-only", () => {
  const vm = reducers.normalizeUi04Envelope(envelope, "portfolio");

  assert.equal(vm.riskGate.decision, "BLOCKED_BY_SAFETY_GATE");
  assert.deepEqual(vm.riskGate.blockedReasons, ["provider_validation_pending"]);
  assert.equal(vm.portfolio.mode, "PAPER_ONLY");
  assert.equal(vm.portfolio.cash.state, "unavailable");
  assert.equal(vm.portfolio.wealthEngine.state, "separate");
  assert.equal(vm.portfolio.moonshotEngine.state, "separate");
});

test("UI-04 module arrays normalize deterministic unavailable states", () => {
  const vm = reducers.normalizeUi04Envelope(envelope, "moonshot-research");

  assert.equal(vm.alerts[0].humanReviewRequired, true);
  assert.equal(vm.models[0].promotionEligibility, "blocked");
  assert.equal(vm.models[0].driftState, "unavailable");
  assert.equal(vm.performance.return_series.state, "unavailable");
  assert.equal(vm.backtests[0].insufficientTradeWarning, "trade_count_unavailable");
  assert.equal(vm.paperActivity[0].simulatedFills, "unavailable");
  assert.equal(vm.options.chain_quality_state, "no-data");
  assert.equal(vm.moonshotResearch[0].riskState, "HUMAN_REVIEW_REQUIRED");
});

test("unsafe UI-04 envelope is blocked by normalizer", () => {
  const unsafe = JSON.parse(JSON.stringify(envelope));
  unsafe.safety_state["live_trading_" + "enabled"] = Boolean(1);

  const vm = reducers.normalizeUi04Envelope(unsafe, "risk-gate");
  assert.equal(vm.status, "blocked");
  assert.equal(vm.safe, false);
});

test("UI-04 route list preserves all nine operator modules", () => {
  assert.deepEqual(reducers.UI04_ROUTES, ["risk-gate", "portfolio", "alerts", "models", "performance", "backtests", "paper-activity", "options", "moonshot-research"]);
});
