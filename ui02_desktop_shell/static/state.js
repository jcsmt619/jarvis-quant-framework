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

  const OVERVIEW_ENDPOINTS = ["health", "safety", "data-status", "research", "risk-gate", "market-regime", "portfolio", "alerts", "paper-activity", "moonshot-research"];
  const SAFETY_LABELS = ["RESEARCH_ONLY", "MONITOR_ONLY", "PAPER_ONLY", "HUMAN_REVIEW_REQUIRED", "BLOCKED_BY_SAFETY_GATE"];
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
    isSafeEnvelope
  };
  global.JarvisUI02Reducers = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
