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

  const nodes = {};
  document.addEventListener("DOMContentLoaded", start);

  function start() {
    [
      "navList", "routeTitle", "routeKicker", "content", "statusRegion", "connectionState", "sourceMode",
      "providerStatus", "utcClock", "localClock", "refreshButton", "paletteButton", "commandPalette",
      "paletteInput", "paletteResults", "eventTimeline", "streamMeta", "collapseRail", "eventRail",
      "cliStatus", "bottomStreamState", "bottomSourceMode", "bottomUtcClock", "bottomLocalClock",
      "bottomEnvironment", "bottomPaperStatus", "providerValidationTop"
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
    nodes.bottomSourceMode.textContent = "source " + sourceMode;
    const provider = payload.provider_validation_status || "pending";
    nodes.providerStatus.textContent = "provider " + provider;
    nodes.providerValidationTop.textContent = "provider-validation " + provider;
    setConnection(reducers.deriveFreshnessState(eventState));
  }

  function renderOverview(cache) {
    nodes.content.innerHTML = "";
    nodes.content.className = "content-grid overview-grid";
    const health = cache.health || {};
    const safety = cache.safety || {};
    const dataStatus = cache["data-status"] || {};
    const research = cache.research || {};
    const riskGate = cache["risk-gate"] || {};
    const marketRegime = cache["market-regime"] || {};
    const portfolio = cache.portfolio || {};
    const alerts = cache.alerts || {};
    const paper = cache["paper-activity"] || {};
    const moonshot = cache["moonshot-research"] || {};

    nodes.content.append(
      metricPanel("Market Regime", "regime", [
        ["Regime", pick(marketRegime, "data.summary.regime", "unavailable")],
        ["Confidence", formatPercent(pick(marketRegime, "data.summary.confidence", null))],
        ["Model", pick(marketRegime, "data.summary.model_version", "ui01-fixture")],
        ["As of", formatTimestamp(pick(marketRegime, "data.summary.as_of", "unavailable"))]
      ], "No live market regime is asserted by UI-02A."),
      metricPanel("Risk Gate", "shield", [
        ["Decision", pick(riskGate, "data.summary.decision", "BLOCKED_BY_SAFETY_GATE")],
        ["Live", String(pick(riskGate, "data.is_live", false))],
        ["Provider", pick(riskGate, "provider_validation_status", "pending")],
        ["Labels", formatArray(pick(riskGate, "data.summary.required_labels", reducers.SAFETY_LABELS))]
      ], "Execution remains blocked by safety policy."),
      metricPanel("Opportunity Radar", "radar", [
        ["State", pick(cache.opportunities || {}, "data.status", "pending")],
        ["Read model", pick(cache.opportunities || {}, "data.read_model", "opportunities")],
        ["Mode", sourceMode],
        ["Detail", "UI-03 pending"]
      ], "No fake opportunities are rendered without fixture data."),
      metricPanel("Portfolio and Exposure", "portfolio", [
        ["Mode", pick(portfolio, "data.summary.mode", "PAPER_ONLY")],
        ["Positions", pick(portfolio, "data.summary.position_count", "unavailable")],
        ["Snapshot", pick(portfolio, "data.summary.snapshot_id", "unavailable")],
        ["Exposure", "no-data"]
      ], "Position values stay redacted or unavailable in this shell."),
      enginePanel("Wealth Engine", "performance", research),
      enginePanel("Moonshot Engine", "moonshot", moonshot),
      chartPanel("Market / System Data", dataStatus),
      distributionPanel("Signal-Strength Distribution", research),
      allocationPanel("Exposure Allocation", portfolio),
      metricPanel("Research State", "research", [
        ["Phase", pick(research, "data.summary.phase", "unavailable")],
        ["Module", pick(research, "data.summary.module", "unavailable")],
        ["Label", pick(research, "data.summary.label", "HUMAN_REVIEW_REQUIRED")],
        ["Readiness", pick(research, "data.summary.readiness_state", "READ_ONLY_UNAVAILABLE")]
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
        ["Alerts", pick(alerts, "data.summary.alert_count", "unavailable")],
        ["Paper activity", pick(paper, "data.status", "pending")]
      ], "Trade-relevant output requires human review."),
      streamHealthPanel(),
      safeModePanel(),
      diagnosticsPanel("Overview Diagnostics", cache, true)
    );
  }

  function renderModule(found, payload) {
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
