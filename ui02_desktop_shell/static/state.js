(function (global) {
  "use strict";

  const ROUTES = [
    ["overview", "Overview", "health", "overview"],
    ["research", "Research", "research", "research"],
    ["screener", "Screener", "screener", "screener"],
    ["opportunities", "Opportunities", "opportunities", "radar"],
    ["analyst-theses", "Analyst Theses", "analyst-theses", "review"],
    ["market-regime", "Market Regime", "market-regime", "regime"],
    ["lifecycle", "Lifecycle", "lifecycle", "lifecycle"],
    ["risk-gate", "Risk Gate", "risk-gate", "shield"],
    ["portfolio", "Portfolio", "portfolio", "portfolio"],
    ["alerts", "Alerts", "alerts", "alert"],
    ["models", "Models", "models", "models"],
    ["performance", "Performance", "performance", "performance"],
    ["backtests", "Backtests", "backtests", "backtest"],
    ["paper-activity", "Paper Activity", "paper-activity", "paper"],
    ["options", "Options", "options", "options"],
    ["moonshot-research", "Moonshot Research", "moonshot-research", "moonshot"]
  ];

  const OVERVIEW_ENDPOINTS = ["health", "safety", "data-status", "research", "screener", "opportunities", "analyst-theses", "lifecycle", "risk-gate", "market-regime", "portfolio", "alerts", "paper-activity", "moonshot-research"];
  const SAFETY_LABELS = ["RESEARCH_ONLY", "MONITOR_ONLY", "PAPER_ONLY", "HUMAN_REVIEW_REQUIRED", "BLOCKED_BY_SAFETY_GATE"];
  const UI03_ROUTES = ["research", "screener", "opportunities", "analyst-theses", "market-regime", "lifecycle"];
  const MAX_REJECT_COUNT = 25;
  const MAX_ACCEPTED_IDS = 96;
  const MAX_EVENTS = 48;
  const MAX_GAPS = 24;
  const MAX_RECONNECTS = 8;
  const FIXTURE_COMPLETE_STATES = ["fixture_complete", "idle_fixture_complete"];

  const DESIGN_TOKENS = {
    colors: {
      nearBlack: "#020611",
      deepNavy: "#07111f",
      panel: "#0a1728",
      cyan: "#2ee9ff",
      electricBlue: "#2f8cff",
      healthyGreen: "#47d18c",
      pendingAmber: "#ffb547",
      blockedRed: "#ff5b73"
    },
    zIndex: {
      base: 0,
      shell: 1,
      rail: 2,
      topStrip: 5,
      dialog: 10,
      focus: 20
    }
  };

  function initialEventState() {
    return {
      connectionState: "connecting",
      lastSequence: 0,
      acceptedIds: [],
      events: [],
      duplicates: 0,
      outOfOrder: 0,
      malformed: 0,
      rejectedRecent: [],
      gaps: [],
      connected: false,
      fixtureComplete: false,
      heartbeatAt: null,
      dataEventAt: null,
      reconnectCount: 0,
      activeConnectionId: null,
      openedAt: null,
      closedAt: null
    };
  }

  function acceptEvent(state, event) {
    const next = cloneState(state);
    if (!event || typeof event.sequence !== "number" || !event.event_id || !event.event_type) {
      boundedReject(next, "malformed");
      return { state: next, accepted: false, reason: "malformed_event" };
    }

    const isHeartbeat = event.event_type === "heartbeat";
    const repeatedFixtureHeartbeat = isHeartbeat && event.sequence === next.lastSequence && event.event_id === "evt-ui01-heartbeat";
    if (!repeatedFixtureHeartbeat && next.acceptedIds.indexOf(event.event_id) !== -1) {
      boundedReject(next, "duplicates");
      return { state: next, accepted: false, reason: "duplicate_event" };
    }
    if (event.sequence < next.lastSequence) {
      boundedReject(next, "outOfOrder");
      return { state: next, accepted: false, reason: "out_of_order_event" };
    }
    if (event.sequence > next.lastSequence + 1 && next.lastSequence !== 0) {
      next.gaps.push({ from: next.lastSequence, to: event.sequence, reason: "sequence_gap" });
      next.gaps = next.gaps.slice(-MAX_GAPS);
    }
    if (event.event_type === "stream_gap") {
      next.gaps.push({ from: next.lastSequence, to: event.sequence, reason: "upstream_stream_gap" });
      next.gaps = next.gaps.slice(-MAX_GAPS);
    }

    next.lastSequence = Math.max(next.lastSequence, event.sequence);
    next.connectionState = "connected";
    next.connected = true;
    next.fixtureComplete = false;
    if (!repeatedFixtureHeartbeat) {
      next.acceptedIds.push(event.event_id);
      next.acceptedIds = next.acceptedIds.slice(-MAX_ACCEPTED_IDS);
    }
    if (isHeartbeat) {
      next.heartbeatAt = event.occurred_at || new Date().toISOString();
    } else {
      next.dataEventAt = event.occurred_at || new Date().toISOString();
      next.events.push(event);
      next.events = next.events.slice(-MAX_EVENTS);
    }
    return { state: next, accepted: true, reason: repeatedFixtureHeartbeat ? "heartbeat_refresh" : "accepted" };
  }

  function markConnectionOpened(state, connectionId, now) {
    const next = cloneState(state);
    next.activeConnectionId = connectionId;
    next.openedAt = now || new Date().toISOString();
    next.closedAt = null;
    next.connected = true;
    next.connectionState = "connected";
    next.fixtureComplete = false;
    return next;
  }

  function markFixtureComplete(state, now) {
    const next = cloneState(state);
    next.connected = false;
    next.fixtureComplete = true;
    next.connectionState = "fixture_complete";
    next.closedAt = now || new Date().toISOString();
    return next;
  }

  function markReconnecting(state) {
    const next = cloneState(state);
    next.connected = false;
    next.fixtureComplete = false;
    next.connectionState = "reconnecting";
    next.reconnectCount = Math.min(MAX_RECONNECTS, next.reconnectCount + 1);
    return next;
  }

  function markLost(state) {
    const next = cloneState(state);
    next.connected = false;
    next.fixtureComplete = false;
    next.connectionState = "lost";
    return next;
  }

  function deriveFreshnessState(state, nowMs) {
    if (FIXTURE_COMPLETE_STATES.indexOf(state.connectionState) !== -1 || state.fixtureComplete) {
      return "fixture_complete";
    }
    if (!state.heartbeatAt) {
      return state.connectionState || "connecting";
    }
    const ageSeconds = Math.max(0, Math.floor(((nowMs || Date.now()) - Date.parse(state.heartbeatAt)) / 1000));
    if (ageSeconds > 45) {
      return "lost";
    }
    if (ageSeconds > 15) {
      return "stale";
    }
    if (state.gaps.length) {
      return "degraded";
    }
    return state.connectionState || "connected";
  }

  function reconnectDelay(attempt) {
    const bounded = Math.max(0, Math.min(Number(attempt) || 0, 6));
    return Math.min(30000, 500 * Math.pow(2, bounded));
  }

  function isSafeEnvelope(payload) {
    return Boolean(payload && payload.provider_validation_status === "pending" && payload.safety_state && payload.safety_state.live_trading_enabled === false && payload.safety_state.is_live === false);
  }

  function normalizeUi03Envelope(envelope, routeId) {
    const data = envelope && envelope.data ? envelope.data : {};
    const ui03 = data.ui03 || {};
    const provenance = ui03.provenance || {};
    const freshness = ui03.freshness || {};
    const candidates = normalizeCandidates(ui03.candidates || ui03.opportunities || []);
    const theses = Array.isArray(ui03.theses) ? ui03.theses.map(normalizeThesis) : [];
    const research = ui03.research || {};
    const lifecycle = ui03.lifecycle || {};
    const regime = ui03.market_regime || {};
    const safe = isSafeEnvelope(envelope);
    return {
      routeId: routeId || "",
      schemaVersion: ui03.schema_version || "ui03.research_workbench.view_model.v1",
      status: safe ? (ui03.status || data.status || "unavailable") : "blocked",
      sourceMode: envelope && envelope.source_mode ? envelope.source_mode : (ui03.source_mode || "fixture"),
      providerValidationStatus: envelope && envelope.provider_validation_status ? envelope.provider_validation_status : "pending",
      isLive: Boolean(data.is_live || ui03.is_live),
      liveTradingStatus: (envelope && envelope.safety_state && envelope.safety_state.live_trading_status) || ui03.live_trading_status || "LIVE TRADING: DISABLED",
      generatedAt: ui03.generated_at || (envelope && envelope.generated_at) || "unavailable",
      observationTime: ui03.observation_time || "unavailable",
      freshnessState: freshness.state || regime.freshness || "unavailable",
      freshnessReason: freshness.reason || "unavailable",
      provenance: {
        sourceIds: arrayOfText(provenance.source_ids),
        sourcePaths: arrayOfText(provenance.source_paths || data.source_artifacts),
        validationState: provenance.validation_state || "unavailable",
        providerValidation: provenance.provider_validation || "pending"
      },
      research,
      candidates,
      opportunities: normalizeCandidates(ui03.opportunities || ui03.candidates || []),
      theses,
      marketRegime: regime,
      lifecycle,
      warnings: arrayOfText((envelope && envelope.warnings) || []).concat(arrayOfText(research.warnings)),
      errors: Array.isArray(envelope && envelope.errors) ? envelope.errors : [],
      safe
    };
  }

  function filterCandidates(candidates, filters) {
    const query = lower(filters && filters.query);
    return normalizeCandidates(candidates).filter((item) => {
      if (query && [item.id, item.symbol, item.engine, item.strategyFamily, item.riskState, item.lifecycleState].join(" ").toLowerCase().indexOf(query) === -1) return false;
      return matchesFilter(item.engine, filters && filters.engine)
        && matchesFilter(item.strategyFamily, filters && filters.strategyFamily)
        && matchesFilter(item.lifecycleState, filters && filters.lifecycleState)
        && matchesFilter(item.riskState, filters && filters.riskState)
        && matchesFilter(item.validationState, filters && filters.validationState)
        && matchesFilter(item.freshness, filters && filters.freshness)
        && matchesFilter(item.sourceMode, filters && filters.sourceMode);
    });
  }

  function sortCandidates(candidates, key, direction) {
    const sortKey = key || "rank";
    const multiplier = direction === "desc" ? -1 : 1;
    return normalizeCandidates(candidates).slice().sort((a, b) => compareValues(a[sortKey], b[sortKey]) * multiplier);
  }

  function candidateOptions(candidates, key) {
    const seen = {};
    return normalizeCandidates(candidates).map((item) => item[key]).filter((value) => {
      if (!value || seen[value]) return false;
      seen[value] = true;
      return true;
    }).sort();
  }

  function selectCandidate(candidates, selectedId) {
    const items = normalizeCandidates(candidates);
    return items.find((item) => item.id === selectedId) || items[0] || null;
  }

  function normalizeCandidates(candidates) {
    if (!Array.isArray(candidates)) return [];
    return candidates.map((item, index) => ({
      id: text(item.id || item.candidate_id || item.symbol || "candidate-" + (index + 1)),
      rank: Number.isFinite(Number(item.rank)) ? Number(item.rank) : index + 1,
      symbol: text(item.symbol || item.asset_identifier || item.id || "unavailable"),
      engine: text(item.engine || "unavailable"),
      strategyFamily: text(item.strategy_family || item.strategyFamily || "unavailable"),
      signalScore: item.signal_score === null || item.signal_score === undefined ? (item.signalScore === undefined ? null : item.signalScore) : Number(item.signal_score),
      regimeCompatibility: text(item.regime_compatibility || item.regimeCompatibility || "unavailable"),
      liquidityState: text(item.liquidity_state || item.liquidityState || "unavailable"),
      dataQualityState: text(item.data_quality_state || item.dataQualityState || "unavailable"),
      lifecycleState: text(item.lifecycle_state || item.lifecycleState || "unavailable"),
      priorState: text(item.prior_state || item.priorState || "unavailable"),
      riskState: text(item.risk_state || item.riskState || item.label || "unavailable"),
      validationState: text(item.validation_state || item.validationState || "unavailable"),
      freshness: text(item.freshness || "unavailable"),
      sourceMode: text(item.source_mode || "fixture"),
      rejectionReasons: arrayOfText(item.rejection_reasons || item.rejectionReasons || item.reasons),
      evidenceRefs: arrayOfText(item.evidence_refs || item.evidenceRefs),
      opportunityLabel: text(item.opportunity_label || item.opportunityLabel || "review queue item"),
      supportingFactors: arrayOfText(item.supporting_factors || item.supportingFactors),
      contradictingFactors: arrayOfText(item.contradicting_factors || item.contradictingFactors),
      reviewHorizon: text(item.review_horizon || item.reviewHorizon || "unavailable"),
      surfacedReason: text(item.surfaced_reason || item.surfacedReason || "unavailable"),
      mayRejectReason: text(item.may_reject_reason || item.mayRejectReason || "unavailable"),
      requiredHumanAction: text(item.required_human_action || item.requiredHumanAction || "HUMAN_REVIEW_REQUIRED")
    }));
  }

  function normalizeThesis(item) {
    return {
      id: text(item.id || item.thesis_id || "thesis-unavailable"),
      candidateId: text(item.candidate_id || "unavailable"),
      summary: text(item.summary || "unavailable"),
      supportingEvidence: arrayOfText(item.supporting_evidence),
      contradictingEvidence: arrayOfText(item.contradicting_evidence),
      uncertainty: text(item.uncertainty || "unavailable"),
      invalidationConditions: arrayOfText(item.invalidation_conditions),
      validationState: text(item.validation_state || "unavailable"),
      confidence: item.confidence === null || item.confidence === undefined ? null : item.confidence,
      status: text(item.status || "HUMAN_REVIEW_REQUIRED")
    };
  }

  function matchesFilter(value, filter) {
    return !filter || filter === "all" || String(value) === String(filter);
  }

  function compareValues(a, b) {
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a || "").localeCompare(String(b || ""));
  }

  function lower(value) {
    return String(value || "").trim().toLowerCase();
  }

  function text(value) {
    if (value === undefined || value === null || value === "") return "unavailable";
    return String(value);
  }

  function arrayOfText(value) {
    if (!Array.isArray(value)) return [];
    return value.filter((item) => item !== undefined && item !== null && item !== "").map((item) => String(item));
  }

  function boundedReject(state, key) {
    state[key] = Math.min(MAX_REJECT_COUNT, (Number(state[key]) || 0) + 1);
    state.rejectedRecent.push({ type: key, at: new Date().toISOString() });
    state.rejectedRecent = state.rejectedRecent.slice(-MAX_REJECT_COUNT);
  }

  function cloneState(state) {
    return {
      connectionState: state.connectionState,
      lastSequence: state.lastSequence,
      acceptedIds: state.acceptedIds.slice(-MAX_ACCEPTED_IDS),
      events: state.events.slice(-MAX_EVENTS),
      duplicates: state.duplicates,
      outOfOrder: state.outOfOrder,
      malformed: state.malformed || 0,
      rejectedRecent: (state.rejectedRecent || []).slice(-MAX_REJECT_COUNT),
      gaps: state.gaps.slice(-MAX_GAPS),
      connected: state.connected,
      fixtureComplete: Boolean(state.fixtureComplete),
      heartbeatAt: state.heartbeatAt,
      dataEventAt: state.dataEventAt,
      reconnectCount: state.reconnectCount || 0,
      activeConnectionId: state.activeConnectionId || null,
      openedAt: state.openedAt || null,
      closedAt: state.closedAt || null
    };
  }

  const api = {
    ROUTES,
    OVERVIEW_ENDPOINTS,
    SAFETY_LABELS,
    UI03_ROUTES,
    DESIGN_TOKENS,
    MAX_REJECT_COUNT,
    MAX_RECONNECTS,
    initialEventState,
    acceptEvent,
    markConnectionOpened,
    markFixtureComplete,
    markReconnecting,
    markLost,
    deriveFreshnessState,
    reconnectDelay,
    isSafeEnvelope,
    normalizeUi03Envelope,
    filterCandidates,
    sortCandidates,
    candidateOptions,
    selectCandidate
  };
  global.JarvisUI02Reducers = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
