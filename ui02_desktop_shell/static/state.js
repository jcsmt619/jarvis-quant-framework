(function (global) {
  "use strict";

  const ROUTES = [
    ["overview", "Overview", "health"],
    ["research", "Research", "research"],
    ["screener", "Screener", "screener"],
    ["opportunities", "Opportunities", "opportunities"],
    ["analyst-theses", "Analyst Theses", "analyst-theses"],
    ["market-regime", "Market Regime", "market-regime"],
    ["lifecycle", "Lifecycle", "lifecycle"],
    ["risk-gate", "Risk Gate", "risk-gate"],
    ["portfolio", "Portfolio", "portfolio"],
    ["alerts", "Alerts", "alerts"],
    ["models", "Models", "models"],
    ["performance", "Performance", "performance"],
    ["backtests", "Backtests", "backtests"],
    ["paper-activity", "Paper Activity", "paper-activity"],
    ["options", "Options", "options"],
    ["moonshot-research", "Moonshot Research", "moonshot-research"]
  ];

  const OVERVIEW_ENDPOINTS = ["health", "safety", "data-status", "research", "risk-gate", "market-regime", "portfolio", "alerts"];

  function initialEventState() {
    return {
      lastSequence: 0,
      acceptedIds: [],
      events: [],
      duplicates: 0,
      outOfOrder: 0,
      gaps: [],
      connected: false,
      heartbeatAt: null
    };
  }

  function acceptEvent(state, event) {
    const next = {
      lastSequence: state.lastSequence,
      acceptedIds: state.acceptedIds.slice(-63),
      events: state.events.slice(-31),
      duplicates: state.duplicates,
      outOfOrder: state.outOfOrder,
      gaps: state.gaps.slice(-15),
      connected: state.connected,
      heartbeatAt: state.heartbeatAt
    };
    if (!event || typeof event.sequence !== "number" || !event.event_id) {
      next.outOfOrder += 1;
      return { state: next, accepted: false, reason: "malformed_event" };
    }
    if (next.acceptedIds.indexOf(event.event_id) !== -1) {
      next.duplicates += 1;
      return { state: next, accepted: false, reason: "duplicate_event" };
    }
    if (event.sequence < next.lastSequence) {
      next.outOfOrder += 1;
      return { state: next, accepted: false, reason: "out_of_order_event" };
    }
    if (event.sequence > next.lastSequence + 1 && next.lastSequence !== 0) {
      next.gaps.push({ from: next.lastSequence, to: event.sequence, reason: "sequence_gap" });
    }
    if (event.event_type === "stream_gap") {
      next.gaps.push({ from: next.lastSequence, to: event.sequence, reason: "upstream_stream_gap" });
    }
    next.lastSequence = Math.max(next.lastSequence, event.sequence);
    next.acceptedIds.push(event.event_id);
    next.events.push(event);
    next.connected = true;
    if (event.event_type === "heartbeat") {
      next.heartbeatAt = event.occurred_at || new Date().toISOString();
    }
    return { state: next, accepted: true, reason: "accepted" };
  }

  function reconnectDelay(attempt) {
    const bounded = Math.max(0, Math.min(Number(attempt) || 0, 6));
    return Math.min(30000, 500 * Math.pow(2, bounded));
  }

  function isSafeEnvelope(payload) {
    return Boolean(payload && payload.provider_validation_status === "pending" && payload.safety_state && payload.safety_state.live_trading_enabled === false);
  }

  const api = { ROUTES, OVERVIEW_ENDPOINTS, initialEventState, acceptEvent, reconnectDelay, isSafeEnvelope };
  global.JarvisUI02Reducers = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
