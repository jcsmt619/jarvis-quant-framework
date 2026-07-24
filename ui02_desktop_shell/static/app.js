(function () {
  "use strict";

  const reducers = window.JarvisUI02Reducers;
  let route = "overview";
  let sourceMode = "fixture";
  let eventState = reducers.initialEventState();
  let reconnectAttempt = 0;
  let reconnectTimer = null;
  let activeEventSource = null;
  let activeConnectionId = 0;
  let routeCache = {};
  let selectedCandidateId = null;
  let ui03Filters = { query: "", sort: "rank", direction: "asc", engine: "all", strategyFamily: "all", lifecycleState: "all", riskState: "all", validationState: "all", freshness: "all", sourceMode: "all" };
  let visibleColumns = { rank: true, symbol: true, engine: true, strategyFamily: true, signalScore: true, regimeCompatibility: true, liquidityState: true, lifecycleState: true, riskState: true, freshness: true };

  const nodes = {};
  document.addEventListener("DOMContentLoaded", start);

  function start() {
    [
      "navList", "routeTitle", "routeKicker", "content", "statusRegion", "connectionState", "sourceMode",
      "providerStatus", "utcClock", "localClock", "refreshButton", "paletteButton", "commandPalette",
      "paletteInput", "paletteResults", "eventTimeline", "streamMeta", "collapseRail", "eventRail",
      "cliStatus", "bottomStreamState", "bottomSourceMode", "bottomUtcClock", "bottomLocalClock",
      "bottomEnvironment", "bottomPaperStatus", "providerValidationTop", "aboutButton", "aboutPanel",
      "desktopLocalService", "desktopGateway", "desktopEventStream", "desktopSourceMode",
      "desktopProviderValidation", "desktopVersion", "desktopRestartCount"
    ].forEach((id) => {
      nodes[id] = document.getElementById(id);
    });
    buildNavigation();
    installKeyboard();
    tickClocks();
    setInterval(tickClocks, 1000);
    setInterval(refreshStreamHealth, 5000);
    window.addEventListener("hashchange", routeFromHash);
    routeFromHash();
    connectEvents();
  }

  function buildNavigation() {
    nodes.navList.textContent = "";
    reducers.ROUTES.forEach(([id, label, endpoint, icon]) => {
      const link = document.createElement("a");
      link.href = "#/" + id;
      link.dataset.route = id;
      link.innerHTML = iconMarkup(icon, true) + "<span></span>";
      link.querySelector("span").textContent = label;
      link.setAttribute("aria-label", "Open " + label);
      nodes.navList.appendChild(link);
    });
  }

  function routeFromHash() {
    const next = (location.hash || "#/overview").replace(/^#\//, "");
    route = reducers.ROUTES.some((item) => item[0] === next) ? next : "overview";
    document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route));
    const found = routeInfo(route);
    nodes.routeTitle.textContent = found[1];
    nodes.routeKicker.textContent = route === "overview" ? "Command center / local read-only fixture shell" : "Read-only gateway endpoint: " + found[2];
    nodes.statusRegion.textContent = found[1] + " loaded";
    loadRoute();
  }

  async function loadRoute() {
    nodes.content.innerHTML = skeletons(route === "overview" ? 10 : 3);
    try {
      if (route === "overview") {
        const entries = await Promise.all(reducers.OVERVIEW_ENDPOINTS.map((endpoint) => fetchEnvelope(endpoint)));
        routeCache = Object.fromEntries(entries.map((entry) => [entry.endpoint, entry.payload]));
        renderOverview(routeCache);
      } else {
        const found = routeInfo(route);
        const entry = await fetchEnvelope(found[2]);
        routeCache[found[2]] = entry.payload;
        renderModule(found, entry.payload);
      }
    } catch (error) {
      nodes.content.innerHTML = "";
      nodes.content.appendChild(errorState("Gateway read failed", error.message || "unavailable"));
      setConnection("lost");
    }
  }

  async function fetchEnvelope(endpoint) {
    const response = await fetch("/gateway/api/v1/" + endpoint, { cache: "no-store", credentials: "omit" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.code || "read_rejected");
    }
    updateTopStatus(payload);
    return { endpoint, payload };
  }

  function updateTopStatus(payload) {
    sourceMode = payload.source_mode || sourceMode;
    nodes.sourceMode.textContent = "source: " + sourceMode;
    nodes.desktopSourceMode.textContent = "source " + sourceMode;
    nodes.bottomSourceMode.textContent = "source " + sourceMode;
    const provider = payload.provider_validation_status || "pending";
    nodes.providerStatus.textContent = "provider " + provider;
    nodes.providerValidationTop.textContent = "provider-validation " + provider;
    nodes.desktopProviderValidation.textContent = "provider " + provider;
    nodes.desktopLocalService.textContent = "local-service running";
    nodes.desktopGateway.textContent = "gateway running";
    setConnection(reducers.deriveFreshnessState(eventState));
  }

  function renderOverview(cache) {
    nodes.content.innerHTML = "";
    nodes.content.className = "content-grid overview-grid";
    const health = cache.health || {};
    const safety = cache.safety || {};
    const dataStatus = cache["data-status"] || {};
    const research = cache.research || {};
    const researchVm = reducers.normalizeUi03Envelope(research, "research");
    const screenerVm = reducers.normalizeUi03Envelope(cache.screener || {}, "screener");
    const opportunitiesVm = reducers.normalizeUi03Envelope(cache.opportunities || {}, "opportunities");
    const riskGate = cache["risk-gate"] || {};
    const riskGateVm = reducers.normalizeUi04Envelope(riskGate, "risk-gate");
    const marketRegime = cache["market-regime"] || {};
    const marketRegimeVm = reducers.normalizeUi03Envelope(marketRegime, "market-regime");
    const portfolio = cache.portfolio || {};
    const portfolioVm = reducers.normalizeUi04Envelope(portfolio, "portfolio");
    const alerts = cache.alerts || {};
    const alertsVm = reducers.normalizeUi04Envelope(alerts, "alerts");
    const paper = cache["paper-activity"] || {};
    const moonshot = cache["moonshot-research"] || {};
    const moonshotVm = reducers.normalizeUi04Envelope(moonshot, "moonshot-research");
    const modelsVm = reducers.normalizeUi04Envelope(cache.models || {}, "models");

    nodes.content.append(
      metricPanel("Market Regime", "regime", [
        ["Regime", marketRegimeVm.marketRegime.label || "unavailable"],
        ["Confidence", formatPercent(marketRegimeVm.marketRegime.confidence)],
        ["Model", marketRegimeVm.marketRegime.model_version || "unavailable"],
        ["As of", formatTimestamp(marketRegimeVm.marketRegime.as_of || "unavailable")]
      ], "No live market regime is asserted by UI-03."),
      metricPanel("Risk Gate", "shield", [
        ["Decision", riskGateVm.riskGate.decision],
        ["Live", String(riskGateVm.isLive)],
        ["Provider", riskGateVm.providerValidationStatus],
        ["Blocked", formatArray(riskGateVm.riskGate.blockedReasons)]
      ], "Execution remains blocked by safety policy."),
      metricPanel("Opportunity Radar", "radar", [
        ["State", opportunitiesVm.status],
        ["Candidates", opportunitiesVm.opportunities.length],
        ["Mode", sourceMode],
        ["Review", "HUMAN_REVIEW_REQUIRED"]
      ], "Opportunity Radar is a read-only review queue, not a trade-signal screen."),
      metricPanel("Portfolio and Exposure", "portfolio", [
        ["Mode", portfolioVm.portfolio.mode],
        ["Positions", portfolioVm.portfolio.positionCount],
        ["Snapshot", portfolioVm.portfolio.snapshotId],
        ["Exposure", stateReason(portfolioVm.portfolio.grossExposure)]
      ], "Position values stay redacted or unavailable unless committed evidence supports them."),
      enginePanel("Wealth Engine", "performance", research),
      metricPanel("Moonshot Engine", "moonshot", [
        ["State", moonshotVm.status],
        ["Candidates", moonshotVm.moonshotResearch.length],
        ["Safety", "HUMAN_REVIEW_REQUIRED"],
        ["Exposure", stateReason(portfolioVm.portfolio.moonshotEngine)]
      ], "Moonshot research is visually separate from Wealth Engine exposure."),
      chartPanel("Market / System Data", dataStatus),
      distributionPanel("Signal-Strength Distribution", research),
      allocationPanel("Exposure Allocation", portfolio),
      metricPanel("Research State", "research", [
        ["Run", researchVm.research.run_id || "unavailable"],
        ["Status", researchVm.research.status || "HUMAN_REVIEW_REQUIRED"],
        ["Freshness", researchVm.freshnessState],
        ["Candidates", screenerVm.candidates.length]
      ], "Research output is informational only."),
      metricPanel("Data Source", "data", [
        ["Source mode", pick(dataStatus, "source_mode", sourceMode)],
        ["Freshness", formatTimestamp(pick(dataStatus, "data.freshness", "unavailable"))],
        ["Quality", pick(dataStatus, "data.provenance.quality_state", "pending")],
        ["Artifacts", formatArray(pick(dataStatus, "data.source_artifacts", []))]
      ], "Provider validation remains pending."),
      metricPanel("Provider Validation", "review", [
        ["Status", pick(dataStatus, "provider_validation_status", "pending")],
        ["Provider", pick(dataStatus, "data.provenance.provider_name", "pending")],
        ["is_live", String(pick(dataStatus, "data.is_live", false))],
        ["Network", "external calls blocked"]
      ], "Provider readiness is not promoted in UI-02A."),
      metricPanel("Local Service Health", "health", [
        ["Status", pick(health, "data.status", "unavailable")],
        ["Audit", pick(health, "data.audit_ledger_status", "unavailable")],
        ["CLI independence", String(pick(health, "data.ui_required_for_engine_operation", true) === false)],
        ["Live trading", pick(health, "data.safety_status", "LIVE TRADING: DISABLED")]
      ], "Local loopback service only."),
      metricPanel("Human Review", "review", [
        ["State", "HUMAN_REVIEW_REQUIRED"],
        ["Analyst path", "research-only"],
        ["Alerts", alertsVm.alerts.length],
        ["Paper activity", pick(paper, "data.status", "pending")]
      ], "Trade-relevant output requires human review."),
      metricPanel("Model Health", "models", [
        ["Models", modelsVm.models.length],
        ["Validation", modelsVm.validationState],
        ["Drift", modelsVm.models.map((item) => item.driftState).join(", ") || "unavailable"],
        ["Promotion", modelsVm.models.map((item) => item.promotionEligibility).join(", ") || "blocked"]
      ], "Model promotion remains blocked unless evidence is complete."),
      streamHealthPanel(),
      safeModePanel(),
      diagnosticsPanel("Overview Diagnostics", cache, true)
    );
  }

  function renderModule(found, payload) {
    if (reducers.UI03_ROUTES.indexOf(found[0]) !== -1) {
      renderUi03Route(found, payload);
      return;
    }
    if (reducers.UI04_ROUTES.indexOf(found[0]) !== -1) {
      renderUi04Route(found, payload);
      return;
    }
    nodes.content.innerHTML = "";
    nodes.content.className = "content-grid module-grid";
    const title = found[1];
    nodes.content.append(
      metricPanel(title + " Summary", found[3], [
        ["Read model", pick(payload, "data.read_model", found[2])],
        ["Status", pick(payload, "data.status", "unavailable")],
        ["Source", pick(payload, "source_mode", sourceMode)],
        ["Provider", pick(payload, "provider_validation_status", "pending")]
      ], "UI-03 and UI-04 will add deeper module workflows."),
      warningPanel(payload),
      emptyPanel(title, payload),
      diagnosticsPanel(title + " Diagnostics", payload, false)
    );
  }

  function renderUi04Route(found, payload) {
    const vm = reducers.normalizeUi04Envelope(payload, found[0]);
    if (!selectedCandidateId && vm.moonshotResearch.length) {
      selectedCandidateId = vm.moonshotResearch[0].candidateId;
    }
    nodes.content.innerHTML = "";
    nodes.content.className = "content-grid ui03-grid ui04-grid";
    nodes.content.append(ui04StatusPanel(found[1], vm), ui04ProvenancePanel(vm));
    if (found[0] === "risk-gate") renderRiskGate(vm);
    if (found[0] === "portfolio") renderPortfolio(vm);
    if (found[0] === "alerts") renderAlerts(vm);
    if (found[0] === "models") renderModels(vm);
    if (found[0] === "performance") renderPerformance(vm);
    if (found[0] === "backtests") renderBacktests(vm);
    if (found[0] === "paper-activity") renderPaperActivity(vm);
    if (found[0] === "options") renderOptions(vm);
    if (found[0] === "moonshot-research") renderMoonshotResearch(vm);
    nodes.content.append(diagnosticsPanel(found[1] + " Diagnostics", payload, true));
  }

  function ui04StatusPanel(title, vm) {
    return metricPanel(title + " Status", "shield", [
      ["Status", vm.status],
      ["Validation", vm.validationState],
      ["Freshness", vm.freshnessState],
      ["Observed", formatTimestamp(vm.observationTime)],
      ["Generated", formatTimestamp(vm.generatedAt)],
      ["Provider", vm.providerValidationStatus],
      ["is_live", String(vm.isLive)],
      ["Safety", vm.liveTradingStatus]
    ], vm.safe ? "Canonical UI-04 operator view-model boundary." : "Envelope failed safety normalization.");
  }

  function ui04ProvenancePanel(vm) {
    return listPanel("Provenance", "data", [
      "Source identifier: " + vm.sourceIdentifier,
      "Source ids: " + formatArray(vm.provenance.sourceIds),
      "Source mode: " + vm.sourceMode,
      "Provider validation: " + vm.provenance.providerValidation
    ].concat(vm.provenance.sourcePaths), "Provenance and local evidence links are preserved.");
  }

  function renderRiskGate(vm) {
    const gate = vm.riskGate;
    const section = metricPanel("Execution Availability", "shield", [
      ["Decision", gate.decision],
      ["Provider gate", gate.providerGate],
      ["Freshness gate", gate.dataFreshnessGate],
      ["Model gate", gate.modelValidationGate],
      ["Portfolio gate", gate.portfolioRiskGate],
      ["Human review", gate.humanReviewRequirement],
      ["Execution", "unavailable"]
    ], gate.executionUnavailableReason);
    section.classList.add("wide", "risk-gate-panel");
    nodes.content.append(section, listPanel("Blocked Reasons", "alert", gate.blockedReasons, "No override controls are exposed."), listPanel("Required Labels", "shield", gate.requiredLabels, "Labels are safety classifications only."), listPanel("Evidence References", "data", gate.evidenceRefs, "Committed repository evidence only."));
  }

  function renderPortfolio(vm) {
    const p = vm.portfolio;
    nodes.content.append(
      metricPanel("Paper Snapshot", "portfolio", [["Snapshot", p.snapshotId], ["Mode", p.mode], ["Freshness", p.freshness], ["Positions", p.positionCount], ["Cash", stateReason(p.cash)], ["Gross exposure", stateReason(p.grossExposure)], ["Net exposure", stateReason(p.netExposure)], ["Concentration", p.concentration], ["Drawdown", p.drawdown]], "Portfolio values remain unavailable unless fixture evidence supports them."),
      tablePanel("Position Summaries", "portfolio", ["Candidate", "Engine", "Summary", "Risk", "Evidence"], p.positions.map((item) => [item.candidate_id, item.engine, item.summary, item.risk_state, formatArray(item.evidence_refs)])),
      tablePanel("Engine Separation", "allocation", ["Bucket", "State", "Count"], p.allocation.map((item) => [item.bucket, item.state, item.count])),
      listPanel("Portfolio Warnings", "alert", p.warnings, "Wealth Engine and Moonshot Engine remain separated.")
    );
  }

  function renderAlerts(vm) {
    nodes.content.append(tablePanel("Read-Only Alert Console", "alert", ["Identifier", "Severity", "Category", "State", "Created", "Freshness", "Source", "Related", "Review", "Evidence"], vm.alerts.map((item) => [item.id, item.severity, item.category, item.state, formatTimestamp(item.createdAt), item.freshness, item.source, item.related, item.humanReviewRequired ? "HUMAN_REVIEW_REQUIRED" : "unavailable", formatArray(item.evidenceDetails)]), "Acknowledgement and dismissal mutations are intentionally absent."));
  }

  function renderModels(vm) {
    nodes.content.append(tablePanel("Model Registry", "models", ["Identifier", "Family", "Version", "Validation", "Drift", "Strategies", "Last Validated", "Freshness", "Promotion", "Warnings", "Evidence"], vm.models.map((item) => [item.id, item.family, item.version, item.validationState, item.driftState, formatArray(item.supportedStrategyFamilies), formatTimestamp(item.lastValidatedAt), item.freshness, item.promotionEligibility, formatArray(item.warnings), formatArray(item.evidenceRefs)]), "No training, tuning, deployment, or configuration controls are exposed."));
  }

  function renderPerformance(vm) {
    const p = vm.performance;
    nodes.content.append(
      metricPanel("Performance Evidence", "performance", [["Metric set", p.metric_set_id], ["Benchmark", p.benchmark], ["Period", p.period], ["Equity series", stateReason(p.equity_series)], ["Return series", stateReason(p.return_series)], ["Drawdown", p.drawdown], ["Sharpe", p.sharpe], ["Win rate", p.win_rate], ["Trade count", p.trade_count]], "Performance is not inferred from missing outcome evidence."),
      metricPanel("Engine Separation", "allocation", [["Wealth Engine", stateReason(p.wealth_engine)], ["Moonshot Engine", stateReason(p.moonshot_engine)], ["Rolling metrics", (p.rolling_metrics || []).length], ["Regime slices", (p.regime_slices || []).length]], "No unsupported return or equity series is fabricated."),
      listPanel("Performance Warnings", "alert", p.warnings || [], "Unavailable metrics stay unavailable.")
    );
  }

  function renderBacktests(vm) {
    nodes.content.append(tablePanel("Backtest Run Registry", "backtest", ["Run", "Strategy", "Symbols", "Range", "IS", "OOS", "Walk Forward", "Slippage", "Benchmark", "Drawdown", "Result", "Overfit", "Trades", "Promotion", "Evidence"], vm.backtests.map((item) => [item.runId, item.strategyFamily, formatArray(item.symbols), item.dateRange, item.inSampleState, item.outOfSampleState, item.walkForwardState, item.slippageAssumptions, item.benchmark, item.drawdown, item.resultLabel, item.overfitWarning, item.insufficientTradeWarning, item.promotionGateState, formatArray(item.evidenceRefs)]), "Browser launch of backtest processes is not available."));
  }

  function renderPaperActivity(vm) {
    nodes.content.append(tablePanel("Paper Activity Ledger", "paper", ["Run", "Review State", "Ledger", "Proposed Actions", "Simulated Fills", "Rejected Actions", "Gate Reasons", "Timestamps", "Freshness"], vm.paperActivity.map((item) => [item.paperRunId, item.approvalOrReviewState, formatArray(item.ledgerRefs), formatArray(item.proposedActions), item.simulatedFills, formatArray(item.rejectedActions), formatArray(item.safetyGateReasons), formatArray(item.timestamps), item.freshness]), "No create, modify, approve, submit, cancel, or route controls are exposed."));
  }

  function renderOptions(vm) {
    const o = vm.options || {};
    nodes.content.append(
      metricPanel("Option Chain Quality", "options", [["Chain quality", o.chain_quality_state], ["Underlying", o.underlying_identifier], ["Expiration", o.expiration], ["DTE", o.dte], ["Strike", o.strike], ["Type", o.call_or_put], ["Bid", o.bid], ["Ask", o.ask], ["Freshness", o.freshness]], "Missing option-chain data remains unavailable."),
      metricPanel("Greeks and IV", "options", [["Delta", o.delta], ["Gamma", o.gamma], ["Theta", o.theta], ["Vega", o.vega], ["Implied volatility", o.implied_volatility], ["Open interest", o.open_interest], ["Scenario", o.scenario_context]], "Greeks, IV, bid, and ask are shown only when supported."),
      listPanel("Options Risk Warnings", "alert", o.risk_warnings || [], "No option orders can be routed."),
      listPanel("Evidence References", "data", o.evidence_refs || [], "Committed local evidence only.")
    );
  }

  function renderMoonshotResearch(vm) {
    const selected = vm.moonshotResearch.find((item) => item.candidateId === selectedCandidateId) || vm.moonshotResearch[0];
    nodes.content.append(tablePanel("Moonshot Research Workbench", "moonshot", ["Candidate", "Underlying", "Strategy", "Lifecycle", "Risk", "Uncertainty", "Evidence", "Detail"], vm.moonshotResearch.map((item) => [item.candidateId, item.underlying, item.strategyFamily, item.lifecycleState, item.riskState, item.uncertainty, formatArray(item.evidenceRefs), item.candidateId]), "Research-only LEAPS and asymmetric-opportunity review. HUMAN_REVIEW_REQUIRED."));
    if (selected) {
      nodes.content.append(
        metricPanel("Selected Moonshot Candidate", "moonshot", [["Candidate", selected.candidateId], ["Underlying", selected.underlying], ["Engine", selected.engine], ["Horizon", selected.expirationOrHorizon], ["Premium or max loss", selected.premiumOrMaxLoss], ["Scenario outcomes", selected.scenarioOutcomes], ["Convexity", selected.convexityOrPayoffEvidence], ["IV context", selected.impliedVolatilityContext], ["Theta context", selected.thetaTimeDecayContext], ["Risk", selected.riskState]], selected.thesis),
        listPanel("Catalyst Evidence", "data", selected.catalystEvidence, "Catalysts require committed evidence."),
        listPanel("Contradicting Evidence", "alert", selected.contradictingEvidence, "Contradictions stay visible."),
        listPanel("Invalidation Conditions", "review", selected.invalidationConditions, "Human review remains required.")
      );
    }
  }

  function renderUi03Route(found, payload) {
    const vm = reducers.normalizeUi03Envelope(payload, found[0]);
    const allCandidates = candidatesForRoute(vm);
    if (!selectedCandidateId && allCandidates.length) {
      selectedCandidateId = allCandidates[0].id;
    }
    const selected = reducers.selectCandidate(allCandidates, selectedCandidateId);
    nodes.content.innerHTML = "";
    nodes.content.className = "content-grid ui03-grid";
    nodes.content.append(
      ui03StatusPanel(found[1], vm),
      ui03ProvenancePanel(vm)
    );
    if (found[0] === "research") renderResearchWorkbench(vm, selected);
    if (found[0] === "screener") renderScreener(vm, allCandidates, selected);
    if (found[0] === "opportunities") renderOpportunities(vm, allCandidates, selected);
    if (found[0] === "analyst-theses") renderTheses(vm, selected);
    if (found[0] === "market-regime") renderMarketRegime(vm);
    if (found[0] === "lifecycle") renderLifecycle(vm, allCandidates, selected);
    if (selected) nodes.content.append(candidateDetailPanel(selected));
    nodes.content.append(diagnosticsPanel(found[1] + " Diagnostics", payload, true));
  }

  function renderResearchWorkbench(vm, selected) {
    const research = vm.research || {};
    nodes.content.append(
      listPanel("Research Workbench", "research", [
        "Run: " + (research.run_id || "unavailable"),
        "Context: " + (research.strategy_context || "unavailable"),
        "Status: " + (research.status || "HUMAN_REVIEW_REQUIRED"),
        "Selected candidate: " + (selected ? selected.symbol + " / " + selected.id : "unavailable")
      ], "Selected run and evidence-pack summary."),
      listPanel("Supporting Evidence", "data", research.supporting_evidence || [], "Committed local evidence only."),
      listPanel("Contradicting Evidence", "alert", research.contradicting_evidence || [], "Contradictions stay visible."),
      listPanel("Unresolved Questions", "review", research.unresolved_questions || [], "Human review remains required."),
      listPanel("Human Review Requirements", "shield", research.human_review_requirements || [], "HUMAN_REVIEW_REQUIRED")
    );
  }

  function renderScreener(vm, candidates, selected) {
    nodes.content.append(filterPanel(candidates));
    const filtered = reducers.sortCandidates(reducers.filterCandidates(candidates, ui03Filters), ui03Filters.sort, ui03Filters.direction);
    nodes.content.append(candidateTable(filtered, selected));
  }

  function renderOpportunities(vm, candidates, selected) {
    const filtered = reducers.sortCandidates(reducers.filterCandidates(candidates, ui03Filters), ui03Filters.sort, ui03Filters.direction);
    nodes.content.append(filterPanel(candidates));
    const queue = document.createElement("section");
    queue.className = "panel wide queue-grid";
    queue.innerHTML = "<div class=\"panel-title\">" + iconMarkup("radar", true) + "<h2>Opportunity Review Queue</h2><span class=\"status-chip pending\">HUMAN_REVIEW_REQUIRED</span></div><div class=\"card-grid\"></div>";
    const grid = queue.querySelector(".card-grid");
    filtered.forEach((item) => grid.appendChild(candidateCard(item)));
    if (!filtered.length) grid.appendChild(noDataBlock("No candidates match the in-memory filters."));
    nodes.content.append(queue);
  }

  function renderTheses(vm, selected) {
    const theses = selected ? vm.theses.filter((item) => item.candidateId === selected.id) : vm.theses;
    const panel = document.createElement("section");
    panel.className = "panel wide thesis-grid";
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup("review", true) + "<h2>Analyst Theses</h2><span class=\"status-chip pending\">HUMAN_REVIEW_REQUIRED</span></div><div class=\"card-grid\"></div>";
    const grid = panel.querySelector(".card-grid");
    theses.forEach((item) => grid.appendChild(thesisCard(item)));
    if (!theses.length) grid.appendChild(noDataBlock("No thesis evidence is available for the selected candidate."));
    nodes.content.append(panel);
  }

  function renderMarketRegime(vm) {
    const regime = vm.marketRegime || {};
    nodes.content.append(
      metricPanel("Regime Evidence", "regime", [
        ["Regime", regime.label || "unavailable"],
        ["Confidence", formatPercent(regime.confidence)],
        ["Model", regime.model_version || "unavailable"],
        ["As of", formatTimestamp(regime.as_of || "unavailable")],
        ["Freshness", regime.freshness || "no-data"],
        ["Volatility", regime.volatility_state || "unavailable"],
        ["Breadth", regime.breadth_state || "unavailable"],
        ["Trend", regime.trend_state || "unavailable"],
        ["Transition", regime.transition_state || "unavailable"]
      ], "Market regime is unavailable unless committed evidence supports it."),
      listPanel("Supporting Factors", "data", regime.supporting_factors || [], "No support is fabricated."),
      listPanel("Contradicting Factors", "alert", regime.contradicting_factors || [], "Unavailable state remains explicit."),
      listPanel("Affected Strategy Families", "models", regime.affected_strategy_families || [], "Research-only context.")
    );
  }

  function renderLifecycle(vm, candidates, selected) {
    const lifecycle = vm.lifecycle || {};
    nodes.content.append(
      lifecycleFunnel(lifecycle.stage_counts || {}, selected),
      listPanel("Allowed Transitions", "lifecycle", (lifecycle.allowed_transitions || []).map((item) => item.from + " -> " + item.to + " / " + item.gate + " / " + item.label), "Read-only transition table."),
      listPanel("Evidence Requirements", "data", lifecycle.evidence_requirements || [], "Required before any future lifecycle change."),
      listPanel("Unresolved Blockers", "alert", lifecycle.unresolved_blockers || [], "Promotion gate remains blocked."),
      metricPanel("Lifecycle Safety", "shield", [
        ["Promotion gate", lifecycle.promotion_gate_state || "blocked"],
        ["Human review", lifecycle.human_review_state || "HUMAN_REVIEW_REQUIRED"],
        ["Duplicate", lifecycle.duplicate_state || "unavailable"],
        ["Stale", lifecycle.stale_state || "unavailable"]
      ], "Timeline is interactive only for candidate selection.")
    );
  }

  function ui03StatusPanel(title, vm) {
    return metricPanel(title + " Status", "shield", [
      ["Status", vm.status],
      ["Validation", vm.provenance.validationState],
      ["Freshness", vm.freshnessState],
      ["Observed", formatTimestamp(vm.observationTime)],
      ["Generated", formatTimestamp(vm.generatedAt)],
      ["Provider", vm.providerValidationStatus],
      ["is_live", String(vm.isLive)],
      ["Safety", vm.liveTradingStatus]
    ], vm.safe ? "Canonical UI-03 view model boundary." : "Envelope failed safety normalization.");
  }

  function ui03ProvenancePanel(vm) {
    return listPanel("Provenance", "data", [
      "Source ids: " + formatArray(vm.provenance.sourceIds),
      "Source mode: " + vm.sourceMode,
      "Provider validation: " + vm.provenance.providerValidation
    ].concat(vm.provenance.sourcePaths), "Source identifiers and local evidence paths are preserved.");
  }

  function filterPanel(candidates) {
    const panel = document.createElement("section");
    panel.className = "panel wide filter-panel";
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup("screener", true) + "<h2>In-Memory Controls</h2><span class=\"status-chip pending\">not persisted</span></div><div class=\"filter-grid\"></div><div class=\"column-controls\" aria-label=\"Column controls\"></div>";
    const grid = panel.querySelector(".filter-grid");
    grid.appendChild(controlInput("Search", "query", ui03Filters.query));
    grid.appendChild(controlSelect("Sort", "sort", ["rank", "symbol", "engine", "strategyFamily", "lifecycleState", "riskState", "freshness"], ui03Filters.sort));
    grid.appendChild(controlSelect("Direction", "direction", ["asc", "desc"], ui03Filters.direction));
    [
      ["Engine", "engine", "engine"],
      ["Strategy", "strategyFamily", "strategyFamily"],
      ["Lifecycle", "lifecycleState", "lifecycleState"],
      ["Risk", "riskState", "riskState"],
      ["Validation", "validationState", "validationState"],
      ["Freshness", "freshness", "freshness"],
      ["Source", "sourceMode", "sourceMode"]
    ].forEach(([label, filterKey, candidateKey]) => {
      grid.appendChild(controlSelect(label, filterKey, ["all"].concat(reducers.candidateOptions(candidates, candidateKey)), ui03Filters[filterKey]));
    });
    Object.keys(visibleColumns).forEach((key) => {
      const label = document.createElement("label");
      label.innerHTML = "<input type=\"checkbox\"> <span></span>";
      const input = label.querySelector("input");
      input.checked = visibleColumns[key];
      input.addEventListener("change", () => {
        visibleColumns[key] = input.checked;
        renderUi03Route(routeInfo(route), routeCache[routeInfo(route)[2]]);
      });
      label.querySelector("span").textContent = key;
      panel.querySelector(".column-controls").appendChild(label);
    });
    return panel;
  }

  function controlInput(labelText, key, value) {
    const label = document.createElement("label");
    label.innerHTML = "<span></span><input type=\"search\" autocomplete=\"off\">";
    label.querySelector("span").textContent = labelText;
    const input = label.querySelector("input");
    input.value = value || "";
    input.addEventListener("input", () => {
      ui03Filters[key] = input.value;
      renderUi03Route(routeInfo(route), routeCache[routeInfo(route)[2]]);
    });
    return label;
  }

  function controlSelect(labelText, key, options, value) {
    const label = document.createElement("label");
    label.innerHTML = "<span></span><select></select>";
    label.querySelector("span").textContent = labelText;
    const select = label.querySelector("select");
    options.forEach((option) => {
      const item = document.createElement("option");
      item.value = option;
      item.textContent = option;
      select.appendChild(item);
    });
    select.value = value || options[0];
    select.addEventListener("change", () => {
      ui03Filters[key] = select.value;
      renderUi03Route(routeInfo(route), routeCache[routeInfo(route)[2]]);
    });
    return label;
  }

  function candidateTable(candidates, selected) {
    const panel = document.createElement("section");
    panel.className = "panel wide table-panel";
    panel.setAttribute("data-responsive-table", "screener");
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup("screener", true) + "<h2>Candidate Screener</h2><span class=\"status-chip pending\">read-only</span></div><div class=\"table-scroll\" tabindex=\"0\" aria-label=\"Scrollable Candidate Screener table\"><table><thead><tr></tr></thead><tbody></tbody></table></div><div class=\"table-card-grid compact-card-mode\" aria-label=\"Compact Candidate Screener cards\"></div>";
    const columns = [
      ["rank", "Rank"], ["symbol", "Identifier"], ["engine", "Engine"], ["strategyFamily", "Strategy"], ["signalScore", "Score"], ["regimeCompatibility", "Regime"], ["liquidityState", "Quality"], ["lifecycleState", "Lifecycle"], ["riskState", "Risk"], ["freshness", "Freshness"]
    ].filter(([key]) => visibleColumns[key]);
    columns.concat([["detail", "Detail"]]).forEach(([_key, label]) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      panel.querySelector("thead tr").appendChild(th);
    });
    const tbody = panel.querySelector("tbody");
    candidates.forEach((item) => {
      const tr = document.createElement("tr");
      if (selected && selected.id === item.id) tr.className = "selected-row";
      columns.forEach(([key]) => {
        const td = document.createElement("td");
        td.dataset.label = columns.find((item) => item[0] === key)[1];
        const value = key === "signalScore" ? formatNullable(item[key]) : item[key];
        if (key === "rank" || key === "signalScore") td.className = "tabular-nums";
        if (key !== "signalScore" && isStateLabel(value)) {
          td.appendChild(chip(readableLabel(value), toneForLabel(value)));
        } else {
          td.textContent = formatValue(value);
        }
        tr.appendChild(td);
      });
      const action = document.createElement("td");
      action.dataset.label = "Detail";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Open details";
      button.addEventListener("click", () => selectCandidateAndRender(item.id));
      action.appendChild(button);
      tr.appendChild(action);
      tbody.appendChild(tr);
      panel.querySelector(".table-card-grid").appendChild(compactTableCard("Candidate", columns.concat([["detail", "Detail"]]).map(([key, label]) => [label, key === "detail" ? item.id : item[key]]), item.id));
    });
    if (!candidates.length) tbody.appendChild(emptyTableRow(columns.length + 1, "No candidates match the in-memory filters."));
    return panel;
  }

  function candidateCard(item) {
    const card = document.createElement("article");
    card.className = "candidate-card";
    card.innerHTML = "<h3></h3><p></p><dl></dl><button type=\"button\">Open details</button>";
    card.querySelector("h3").textContent = item.symbol + " / " + item.opportunityLabel;
    card.querySelector("p").textContent = item.requiredHumanAction;
    const dl = card.querySelector("dl");
    [["Risk", item.riskState], ["Lifecycle", item.lifecycleState], ["Data quality", item.dataQualityState], ["Review horizon", item.reviewHorizon], ["Why surfaced", item.surfacedReason], ["Why may be withheld", item.mayRejectReason]].forEach((row) => addMetric(dl, row[0], row[1]));
    card.querySelector("button").addEventListener("click", () => selectCandidateAndRender(item.id));
    return card;
  }

  function thesisCard(item) {
    const card = document.createElement("article");
    card.className = "candidate-card";
    card.innerHTML = "<h3></h3><p></p><dl></dl>";
    card.querySelector("h3").textContent = item.id;
    card.querySelector("p").textContent = item.summary;
    const dl = card.querySelector("dl");
    [["Candidate", item.candidateId], ["Confidence", item.confidence === null ? "unavailable" : item.confidence], ["Validation", item.validationState], ["Status", item.status], ["Uncertainty", item.uncertainty], ["Invalidation", formatArray(item.invalidationConditions)]].forEach((row) => addMetric(dl, row[0], row[1]));
    return card;
  }

  function lifecycleFunnel(counts, selected) {
    const panel = document.createElement("section");
    panel.className = "panel wide lifecycle-funnel";
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup("lifecycle", true) + "<h2>Lifecycle Funnel</h2><span class=\"status-chip pending\">read-only</span></div><div class=\"funnel-steps\"></div>";
    Object.keys(counts).forEach((state) => {
      const button = document.createElement("button");
      button.type = "button";
      button.innerHTML = "<strong></strong><span></span>";
      button.querySelector("strong").textContent = state;
      button.querySelector("span").textContent = String(counts[state]);
      button.disabled = true;
      if (selected && selected.lifecycleState === state) button.className = "active-step";
      panel.querySelector(".funnel-steps").appendChild(button);
    });
    return panel;
  }

  function candidateDetailPanel(item) {
    const panel = document.createElement("aside");
    panel.className = "panel wide detail-panel";
    panel.setAttribute("aria-label", "Selected candidate detail");
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup("review", true) + "<h2>Candidate Detail</h2><span class=\"status-chip pending\">HUMAN_REVIEW_REQUIRED</span></div><dl></dl><div class=\"route-links\"></div>";
    const dl = panel.querySelector("dl");
    [["Identifier", item.id], ["Symbol", item.symbol], ["Engine", item.engine], ["Strategy", item.strategyFamily], ["Score", formatNullable(item.signalScore)], ["Regime", item.regimeCompatibility], ["Liquidity", item.liquidityState], ["Data quality", item.dataQualityState], ["Current state", item.lifecycleState], ["Prior state", item.priorState], ["Risk", item.riskState], ["Validation", item.validationState], ["Freshness", item.freshness], ["Evidence", formatArray(item.evidenceRefs)], ["Supporting", formatArray(item.supportingFactors)], ["Contradicting", formatArray(item.contradictingFactors)], ["Rejection reasons", formatArray(item.rejectionReasons)], ["Required human action", item.requiredHumanAction]].forEach((row) => addMetric(dl, row[0], row[1]));
    [["#/screener", "Screener"], ["#/opportunities", "Opportunities"], ["#/analyst-theses", "Theses"], ["#/lifecycle", "Lifecycle"]].forEach(([href, label]) => {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      panel.querySelector(".route-links").appendChild(link);
    });
    return panel;
  }

  function selectCandidateAndRender(id) {
    selectedCandidateId = id;
    nodes.statusRegion.textContent = "Candidate " + id + " selected in memory";
    if (reducers.UI04_ROUTES.indexOf(route) !== -1) {
      renderUi04Route(routeInfo(route), routeCache[routeInfo(route)[2]]);
    } else {
      renderUi03Route(routeInfo(route), routeCache[routeInfo(route)[2]]);
    }
  }

  function candidatesForRoute(vm) {
    return vm.opportunities.length ? vm.opportunities : vm.candidates;
  }

  function tablePanel(title, icon, headers, rows, note) {
    const panel = document.createElement("section");
    panel.className = "panel wide table-panel";
    panel.setAttribute("data-responsive-table", title.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
    panel.innerHTML = "<div class=\"panel-title\">" + iconMarkup(icon, true) + "<h2></h2><span class=\"status-chip pending\">read-only</span></div><div class=\"table-scroll\" tabindex=\"0\" aria-label=\"Scrollable " + title + " table\"><table><thead><tr></tr></thead><tbody></tbody></table></div><div class=\"table-card-grid compact-card-mode\" aria-label=\"Compact " + title + " cards\"></div><p class=\"panel-note\"></p>";
    panel.querySelector("h2").textContent = title;
    headers.forEach((label) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      panel.querySelector("thead tr").appendChild(th);
    });
    const tbody = panel.querySelector("tbody");
    (rows || []).forEach((row) => {
      const tr = document.createElement("tr");
      row.forEach((value, index) => {
        const td = document.createElement("td");
        td.dataset.label = headers[index] || "Value";
        if (isNumericLike(value)) td.className = "tabular-nums";
        if (headers[index] === "Detail") {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = "Open details";
          button.addEventListener("click", () => selectCandidateAndRender(String(value)));
          td.appendChild(button);
        } else if (isStateLabel(value)) {
          td.appendChild(chip(readableLabel(value), toneForLabel(value)));
        } else {
          td.textContent = formatValue(value);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
      panel.querySelector(".table-card-grid").appendChild(compactTableCard(title, headers.map((label, index) => [label, row[index]]), row[0]));
    });
    if (!tbody.children.length) tbody.appendChild(emptyTableRow(headers.length, "No committed evidence is available for this table."));
    panel.querySelector(".panel-note").textContent = note || "Read-only local evidence.";
    return panel;
  }

  function compactTableCard(title, pairs, detailValue) {
    const card = document.createElement("article");
    card.className = "table-card";
    card.innerHTML = "<h3></h3><dl></dl>";
    card.querySelector("h3").textContent = title + " / " + formatValue(detailValue);
    const dl = card.querySelector("dl");
    pairs.forEach(([label, value]) => addMetric(dl, label, isStateLabel(value) ? readableLabel(value) : formatValue(value)));
    return card;
  }

  function listPanel(title, icon, items, note) {
    const section = document.createElement("section");
    section.className = "panel list-panel";
    section.innerHTML = "<div class=\"panel-title\">" + iconMarkup(icon, true) + "<h2></h2></div><ul></ul><p class=\"panel-note\"></p>";
    section.querySelector("h2").textContent = title;
    const ul = section.querySelector("ul");
    (items || []).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = String(item);
      ul.appendChild(li);
    });
    if (!ul.children.length) {
      const li = document.createElement("li");
      li.textContent = "unavailable";
      ul.appendChild(li);
    }
    section.querySelector(".panel-note").textContent = note || "";
    return section;
  }

  function noDataBlock(text) {
    const block = document.createElement("p");
    block.className = "no-data";
    block.textContent = text;
    return block;
  }

  function emptyTableRow(span, text) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = span;
    td.appendChild(noDataBlock(text));
    tr.appendChild(td);
    return tr;
  }

  function metricPanel(title, icon, rows, note) {
    const section = document.createElement("section");
    section.className = "panel metric-card";
    section.innerHTML = "<div class=\"panel-title\">" + iconMarkup(icon, true) + "<h2></h2></div><dl></dl><p class=\"panel-note\"></p>";
    section.querySelector("h2").textContent = title;
    const dl = section.querySelector("dl");
    rows.forEach(([label, value]) => addMetric(dl, label, value));
    section.querySelector(".panel-note").textContent = note;
    return section;
  }

  function enginePanel(title, icon, payload) {
    return metricPanel(title, icon, [
      ["State", pick(payload, "data.status", "pending")],
      ["Classification", pick(payload, "data.classification", "read_only")],
      ["Readiness", pick(payload, "data.summary.readiness_state", "READ_ONLY_UNAVAILABLE")],
      ["Safety", "RESEARCH_ONLY"]
    ], "Engine controls are monitor-only in UI-02A.");
  }

  function chartPanel(title, payload) {
    const section = metricPanel(title, "chart", [
      ["Freshness", formatTimestamp(pick(payload, "data.freshness", "unavailable"))],
      ["Gaps", formatArray(pick(payload, "data.gaps", []))],
      ["Stale flags", formatArray(pick(payload, "data.stale_flags", []))]
    ], "Chart frame intentionally shows unavailable states unless fixture data exists.");
    section.classList.add("wide", "chart-frame");
    const plot = document.createElement("div");
    plot.className = "holo-chart";
    plot.setAttribute("role", "img");
    plot.setAttribute("aria-label", "No live chart data available; fixture source pending provider validation.");
    plot.innerHTML = "<span>NO LIVE DATA</span><i></i><i></i><i></i>";
    section.appendChild(plot);
    return section;
  }

  function distributionPanel(title, payload) {
    const section = metricPanel(title, "signal", [
      ["Signal source", pick(payload, "data.read_model", "research")],
      ["Values", "no-data"],
      ["Confidence", "unavailable"],
      ["Fixture mode", sourceMode === "fixture" ? "deterministic fixture" : sourceMode]
    ], "Signal distributions are withheld when the read model has no explicit values.");
    section.classList.add("distribution-panel");
    section.appendChild(bars(["Blocked", "Pending", "No data"], [35, 45, 20]));
    return section;
  }

  function allocationPanel(title, payload) {
    const section = metricPanel(title, "allocation", [
      ["Allocation", "no-data"],
      ["Exposure", "unavailable"],
      ["Paper", pick(payload, "data.summary.mode", "PAPER_ONLY")]
    ], "No account values or live positions are exposed.");
    section.classList.add("allocation-panel");
    section.appendChild(bars(["Cash", "Paper", "Live"], [0, 0, 0]));
    return section;
  }

  function streamHealthPanel() {
    return metricPanel("Event Stream", "events", [
      ["State", reducers.deriveFreshnessState(eventState)],
      ["Last sequence", eventState.lastSequence],
      ["Last heartbeat", formatTimestamp(eventState.heartbeatAt || "pending")],
      ["Gaps", eventState.gaps.length],
      ["Reconnects", eventState.reconnectCount],
      ["Rejects", "dup " + eventState.duplicates + " / order " + eventState.outOfOrder + " / malformed " + eventState.malformed]
    ], "Fixture completion is idle, not a network failure.");
  }

  function safeModePanel() {
    const section = document.createElement("section");
    section.className = "panel safe-mode-panel wide";
    section.innerHTML = "<div class=\"panel-title\">" + iconMarkup("shield", true) + "<h2>Safe Mode</h2><span class=\"status-chip blocked\">Safety gate active</span></div><p></p><div class=\"chip-row\"></div>";
    section.querySelector("p").textContent = "Jarvis UI-02A is a local read-only command center. It does not route orders, enable broker execution, load secrets, or override deterministic safety gates.";
    const row = section.querySelector(".chip-row");
    reducers.SAFETY_LABELS.forEach((label) => row.appendChild(chip(label, "pending")));
    return section;
  }

  function diagnosticsPanel(title, payload, wide) {
    const details = document.createElement("details");
    details.className = "panel diagnostics" + (wide ? " wide" : "");
    details.innerHTML = "<summary></summary><pre></pre>";
    details.querySelector("summary").textContent = title;
    details.querySelector("pre").textContent = JSON.stringify(payload, null, 2);
    return details;
  }

  function warningPanel(payload) {
    const warnings = (payload.warnings || []).concat((payload.errors || []).map((item) => item.code || "error"));
    if (!warnings.length) {
      return emptyPanel("Warnings", { data: { status: "no warnings", reason: "none" } });
    }
    const section = document.createElement("section");
    section.className = "panel warning-panel";
    section.innerHTML = "<div class=\"panel-title\">" + iconMarkup("alert", true) + "<h2>Warnings</h2></div><ul class=\"warning-list\"></ul>";
    warnings.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = typeof item === "string" ? item : JSON.stringify(item);
      section.querySelector("ul").appendChild(li);
    });
    return section;
  }

  function emptyPanel(title, payload) {
    const section = document.createElement("section");
    section.className = "panel empty-state";
    section.innerHTML = "<div class=\"panel-title\">" + iconMarkup("pending", true) + "<h2></h2></div><p></p><span class=\"status-chip pending\"></span>";
    section.querySelector("h2").textContent = title;
    section.querySelector("p").textContent = pick(payload, "data.reason", "No expanded route workflow is available in UI-02A.");
    section.querySelector("span").textContent = pick(payload, "data.status", "pending");
    return section;
  }

  function bars(labels, values) {
    const wrap = document.createElement("div");
    wrap.className = "bars";
    labels.forEach((label, index) => {
      const row = document.createElement("div");
      row.innerHTML = "<span></span><b><i></i></b><small></small>";
      row.querySelector("span").textContent = label;
      row.querySelector("i").style.width = Math.max(0, Math.min(values[index], 100)) + "%";
      row.querySelector("small").textContent = values[index] ? values[index] + "%" : "no-data";
      wrap.appendChild(row);
    });
    return wrap;
  }

  function addMetric(dl, label, value) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = formatValue(value);
    dl.append(dt, dd);
  }

  function chip(label, tone) {
    const span = document.createElement("span");
    span.className = "status-chip " + tone;
    span.textContent = label;
    return span;
  }

  function iconMarkup(icon, decorative) {
    const aria = decorative ? " aria-hidden=\"true\" focusable=\"false\"" : " role=\"img\" aria-label=\"" + icon + "\"";
    return "<svg class=\"icon icon-" + icon + "\"" + aria + "><use href=\"/assets/icons.svg#icon-" + icon + "\"></use></svg>";
  }

  function connectEvents() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }
    const connectionId = ++activeConnectionId;
    let acceptedThisConnection = false;
    const source = new EventSource("/gateway/api/v1/events?after=" + encodeURIComponent(eventState.lastSequence));
    activeEventSource = source;
    eventState = reducers.markConnectionOpened(eventState, connectionId);
    renderStreamChrome();
    source.onopen = () => {
      reconnectAttempt = 0;
      eventState = reducers.markConnectionOpened(eventState, connectionId);
      setConnection("connected");
    };
    source.onmessage = (message) => {
      acceptedThisConnection = consumeEvent(message.data) || acceptedThisConnection;
    };
    eventTypes().forEach((type) => {
      source.addEventListener(type, (message) => {
        acceptedThisConnection = consumeEvent(message.data) || acceptedThisConnection;
      });
    });
    source.onerror = () => {
      source.close();
      if (activeEventSource === source) {
        activeEventSource = null;
      }
      if (sourceMode === "fixture" && acceptedThisConnection) {
        eventState = reducers.markFixtureComplete(eventState);
        renderStreamChrome();
        if (route === "overview") {
          renderOverview(routeCache);
        }
        return;
      }
      eventState = reducers.markReconnecting(eventState);
      setConnection("reconnecting");
      const delay = reducers.reconnectDelay(reconnectAttempt++);
      nodes.streamMeta.textContent = "Reconnecting in " + delay + "ms. Last accepted sequence " + eventState.lastSequence + ".";
      reconnectTimer = setTimeout(connectEvents, delay);
    };
  }

  function consumeEvent(data) {
    try {
      const result = reducers.acceptEvent(eventState, JSON.parse(data));
      eventState = result.state;
      renderStreamChrome();
      return result.accepted;
    } catch (error) {
      eventState = reducers.acceptEvent(eventState, null).state;
      renderStreamChrome();
      return false;
    }
  }

  function renderStreamChrome() {
    refreshStreamHealth();
    renderTimeline();
  }

  function refreshStreamHealth() {
    const state = reducers.deriveFreshnessState(eventState);
    setConnection(state);
    nodes.streamMeta.textContent = "state " + state + " / seq " + eventState.lastSequence + " / heartbeat " + formatTimestamp(eventState.heartbeatAt || "pending") + " / gaps " + eventState.gaps.length;
    nodes.bottomStreamState.textContent = "stream " + state;
    if (route === "overview" && Object.keys(routeCache).length) {
      const panel = document.querySelector(".metric-card:nth-last-of-type(2)");
      if (panel) {
        panel.replaceWith(streamHealthPanel());
      }
    }
  }

  function renderTimeline() {
    nodes.eventTimeline.textContent = "";
    eventState.events.slice().reverse().forEach((event) => {
      const item = document.createElement("li");
      item.innerHTML = iconMarkup(iconForEvent(event.event_type), true) + "<div><strong></strong><small></small><p></p></div>";
      item.querySelector("strong").textContent = "#" + event.sequence + " " + event.event_type;
      item.querySelector("small").textContent = formatTimestamp(event.occurred_at) + " / " + (event.source_mode || sourceMode);
      item.querySelector("p").textContent = safeEventDetail(event);
      nodes.eventTimeline.appendChild(item);
    });
  }

  function setConnection(value) {
    const state = value || "connecting";
    nodes.connectionState.textContent = state;
    nodes.desktopEventStream.textContent = "event-stream " + state;
    nodes.connectionState.className = state === "connected" || state === "fixture_complete" ? "badge badge-ok" : state === "stale" || state === "degraded" || state === "reconnecting" ? "badge badge-warn" : "badge badge-blocked";
  }

  function tickClocks() {
    const now = new Date();
    const utc = "UTC " + now.toISOString().slice(11, 19);
    const local = "Local " + now.toLocaleTimeString();
    nodes.utcClock.textContent = utc;
    nodes.localClock.textContent = local;
    nodes.bottomUtcClock.textContent = utc;
    nodes.bottomLocalClock.textContent = local;
  }

  function installKeyboard() {
    nodes.refreshButton.addEventListener("click", loadRoute);
    nodes.paletteButton.addEventListener("click", openPalette);
    nodes.aboutButton.addEventListener("click", () => nodes.aboutPanel.showModal());
    nodes.collapseRail.addEventListener("click", () => nodes.eventRail.classList.toggle("collapsed"));
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openPalette();
      }
      if (event.key.toLowerCase() === "r" && !event.ctrlKey && !event.metaKey && document.activeElement === document.body) {
        loadRoute();
      }
    });
    nodes.paletteInput.addEventListener("input", renderPalette);
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        document.querySelector(".shell").dataset.theme = button.dataset.themeChoice;
      });
    });
  }

  function openPalette() {
    renderPalette();
    nodes.commandPalette.showModal();
    nodes.paletteInput.focus();
  }

  function renderPalette() {
    const query = nodes.paletteInput.value.toLowerCase();
    nodes.paletteResults.textContent = "";
    reducers.ROUTES.filter((item) => item[1].toLowerCase().indexOf(query) !== -1).forEach(([id, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.role = "option";
      button.textContent = label;
      button.addEventListener("click", () => {
        location.hash = "#/" + id;
        nodes.commandPalette.close();
      });
      nodes.paletteResults.appendChild(button);
    });
  }

  function skeletons(count) {
    return Array.from({ length: count }, (_, index) => "<section class=\"panel skeleton\" aria-label=\"Loading read model\"><span>loading " + (index + 1) + "</span></section>").join("");
  }

  function errorState(title, detail) {
    const section = document.createElement("section");
    section.className = "panel error wide";
    section.innerHTML = "<h2></h2><p></p><strong>BLOCKED_BY_SAFETY_GATE</strong>";
    section.querySelector("h2").textContent = title;
    section.querySelector("p").textContent = detail;
    return section;
  }

  function routeInfo(id) {
    return reducers.ROUTES.find((item) => item[0] === id) || reducers.ROUTES[0];
  }

  function eventTypes() {
    return ["heartbeat", "system_health_updated", "safety_state_updated", "data_status_updated", "research_refreshed", "screener_refreshed", "risk_gate_updated", "portfolio_snapshot_updated", "alert_created", "backtest_completed", "paper_activity_updated", "stream_gap"];
  }

  function iconForEvent(type) {
    if (type.indexOf("risk") !== -1 || type.indexOf("safety") !== -1) return "shield";
    if (type.indexOf("alert") !== -1) return "alert";
    if (type.indexOf("portfolio") !== -1) return "portfolio";
    if (type.indexOf("paper") !== -1) return "paper";
    if (type.indexOf("backtest") !== -1) return "backtest";
    return "events";
  }

  function safeEventDetail(event) {
    const payload = event.payload || {};
    return "status " + (payload.status || "available") + " / provider " + (event.provider_validation_status || "pending") + " / is_live false";
  }

  function pick(payload, path, fallback) {
    return path.split(".").reduce((value, key) => value && value[key] !== undefined ? value[key] : undefined, payload) ?? fallback;
  }

  function formatValue(value) {
    if (value === undefined || value === null || value === "") return "unavailable";
    if (Array.isArray(value)) return formatArray(value);
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function stateReason(value) {
    if (!value || typeof value !== "object") return formatValue(value);
    const state = value.state || "unavailable";
    const reason = value.reason ? " / " + value.reason : "";
    const exposure = value.exposure ? " / " + value.exposure : "";
    return state + reason + exposure;
  }

  function readableLabel(value) {
    return String(value || "unavailable").replace(/_/g, " ");
  }

  function isStateLabel(value) {
    return typeof value === "string" && (value.indexOf("_") !== -1 || /^(blocked|pending|stale|no-data|unavailable|partial-evidence|critical|warning|open-read-only)$/i.test(value));
  }

  function isNumericLike(value) {
    return typeof value === "number" || (/^-?\d+(\.\d+)?%?$/.test(String(value || "").trim()));
  }

  function toneForLabel(value) {
    const lowerValue = String(value || "").toLowerCase();
    if (lowerValue.indexOf("blocked") !== -1 || lowerValue.indexOf("critical") !== -1) return "blocked";
    if (lowerValue.indexOf("paper") !== -1 || lowerValue.indexOf("research") !== -1) return "ok";
    return "pending";
  }

  function formatNullable(value) {
    return value === undefined || value === null || value === "" || Number.isNaN(value) ? "unavailable" : String(value);
  }

  function formatArray(value) {
    return Array.isArray(value) && value.length ? value.join(", ") : "none";
  }

  function formatPercent(value) {
    return typeof value === "number" ? Math.round(value * 1000) / 10 + "%" : "unavailable";
  }

  function formatTimestamp(value) {
    if (!value || value === "unavailable" || value === "pending") return String(value || "unavailable");
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toISOString().replace(".000", "");
  }
})();
