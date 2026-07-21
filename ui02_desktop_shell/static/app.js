(function () {
  "use strict";

  const reducers = window.JarvisUI02Reducers;
  let route = "overview";
  let sourceMode = "fixture";
  let eventState = reducers.initialEventState();
  let reconnectAttempt = 0;
  let reconnectTimer = null;

  const nodes = {};
  document.addEventListener("DOMContentLoaded", start);

  function start() {
    ["navList", "routeTitle", "routeKicker", "content", "statusRegion", "connectionState", "sourceMode", "providerStatus", "utcClock", "localClock", "refreshButton", "paletteButton", "commandPalette", "paletteInput", "paletteResults", "eventTimeline", "streamMeta", "collapseRail", "eventRail"].forEach((id) => {
      nodes[id] = document.getElementById(id);
    });
    buildNavigation();
    installKeyboard();
    tickClocks();
    setInterval(tickClocks, 1000);
    window.addEventListener("hashchange", routeFromHash);
    routeFromHash();
    connectEvents();
  }

  function buildNavigation() {
    nodes.navList.textContent = "";
    reducers.ROUTES.forEach(([id, label]) => {
      const link = document.createElement("a");
      link.href = "#/" + id;
      link.dataset.route = id;
      link.textContent = label;
      link.setAttribute("aria-label", "Open " + label);
      nodes.navList.appendChild(link);
    });
  }

  function routeFromHash() {
    const next = (location.hash || "#/overview").replace(/^#\//, "");
    route = reducers.ROUTES.some((item) => item[0] === next) ? next : "overview";
    document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route));
    const found = reducers.ROUTES.find((item) => item[0] === route);
    nodes.routeTitle.textContent = found[1];
    nodes.routeKicker.textContent = "Read-only gateway endpoint: " + found[2];
    nodes.statusRegion.textContent = found[1] + " loaded";
    loadRoute();
  }

  async function loadRoute() {
    nodes.content.innerHTML = skeletons(route === "overview" ? 8 : 1);
    try {
      if (route === "overview") {
        const entries = await Promise.all(reducers.OVERVIEW_ENDPOINTS.map((endpoint) => fetchEnvelope(endpoint)));
        renderOverview(entries);
      } else {
        const found = reducers.ROUTES.find((item) => item[0] === route);
        renderModule(found[1], await fetchEnvelope(found[2]));
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
    nodes.providerStatus.textContent = "provider_validation_status " + (payload.provider_validation_status || "pending");
    setConnection("connected");
  }

  function renderOverview(entries) {
    nodes.content.innerHTML = "";
    entries.forEach(({ endpoint, payload }) => nodes.content.appendChild(envelopeCard(endpoint, payload)));
    const stream = document.createElement("section");
    stream.className = "panel wide";
    stream.innerHTML = "<h2>Event Stream Status</h2><p>Last accepted sequence: " + eventState.lastSequence + "</p><p>Gaps: " + eventState.gaps.length + " Duplicate rejects: " + eventState.duplicates + " Out-of-order rejects: " + eventState.outOfOrder + "</p><strong>LIVE TRADING: DISABLED</strong>";
    nodes.content.appendChild(stream);
  }

  function renderModule(title, entry) {
    nodes.content.innerHTML = "";
    nodes.content.appendChild(envelopeCard(title, entry.payload));
    const table = document.createElement("section");
    table.className = "panel wide";
    table.innerHTML = "<h2>Read-only Details</h2>";
    table.appendChild(jsonTable(entry.payload.data || {}));
    nodes.content.appendChild(table);
  }

  function envelopeCard(title, payload) {
    const data = payload.data || {};
    const section = document.createElement("section");
    section.className = "panel";
    const safe = reducers.isSafeEnvelope(payload);
    section.innerHTML = "<div class=\"panel-title\"><h2></h2><span class=\"badge badge-warn\">LIVE TRADING: DISABLED</span></div><dl></dl>";
    section.querySelector("h2").textContent = title;
    const dl = section.querySelector("dl");
    addMetric(dl, "provider_validation_status", payload.provider_validation_status || data.provider_validation_status || "pending");
    addMetric(dl, "is_live", String(data.is_live === true));
    addMetric(dl, "source_mode", payload.source_mode || sourceMode);
    addMetric(dl, "status", data.status || "available");
    addMetric(dl, "safety_envelope", safe ? "disabled" : "blocked_or_unavailable");
    addMetric(dl, "timestamp", payload.generated_at || data.freshness || data.as_of || "unavailable");
    if ((payload.warnings || []).length || (payload.errors || []).length) {
      section.appendChild(warningList([...(payload.warnings || []), ...(payload.errors || []).map((item) => item.code || "error")]));
    }
    return section;
  }

  function addMetric(dl, label, value) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value === undefined || value === null || value === "" ? "unavailable" : String(value);
    dl.append(dt, dd);
  }

  function warningList(items) {
    const list = document.createElement("ul");
    list.className = "warning-list";
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = typeof item === "string" ? item : JSON.stringify(item);
      list.appendChild(li);
    });
    return list;
  }

  function jsonTable(data) {
    const table = document.createElement("table");
    table.innerHTML = "<thead><tr><th scope=\"col\">Field</th><th scope=\"col\">Value</th></tr></thead><tbody></tbody>";
    const body = table.querySelector("tbody");
    Object.keys(data).sort().forEach((key) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      const td = document.createElement("td");
      th.scope = "row";
      th.textContent = key;
      td.textContent = typeof data[key] === "object" ? JSON.stringify(data[key]) : String(data[key]);
      tr.append(th, td);
      body.appendChild(tr);
    });
    return table;
  }

  function skeletons(count) {
    return Array.from({ length: count }, () => "<section class=\"panel skeleton\" aria-label=\"Loading read model\"></section>").join("");
  }

  function errorState(title, detail) {
    const section = document.createElement("section");
    section.className = "panel error";
    section.innerHTML = "<h2></h2><p></p><strong>BLOCKED_BY_SAFETY_GATE</strong>";
    section.querySelector("h2").textContent = title;
    section.querySelector("p").textContent = detail;
    return section;
  }

  function connectEvents() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    const after = eventState.lastSequence;
    const source = new EventSource("/gateway/api/v1/events?after=" + encodeURIComponent(after));
    source.onopen = () => {
      reconnectAttempt = 0;
      setConnection("streaming");
    };
    source.onmessage = (message) => consumeEvent(message.data);
    ["heartbeat", "system_health_updated", "safety_state_updated", "data_status_updated", "research_refreshed", "screener_refreshed", "risk_gate_updated", "portfolio_snapshot_updated", "alert_created", "backtest_completed", "paper_activity_updated", "stream_gap"].forEach((type) => {
      source.addEventListener(type, (message) => consumeEvent(message.data));
    });
    source.onerror = () => {
      source.close();
      setConnection("lost");
      const delay = reducers.reconnectDelay(reconnectAttempt++);
      nodes.streamMeta.textContent = "Connection lost. Reconnect in " + delay + "ms. Last accepted sequence " + eventState.lastSequence + ".";
      reconnectTimer = setTimeout(connectEvents, delay);
    };
  }

  function consumeEvent(data) {
    try {
      const result = reducers.acceptEvent(eventState, JSON.parse(data));
      eventState = result.state;
      nodes.streamMeta.textContent = "Heartbeat " + (eventState.heartbeatAt || "pending") + " / gaps " + eventState.gaps.length + " / source " + sourceMode;
      renderTimeline();
      if (route === "overview") {
        loadRoute();
      }
    } catch (error) {
      eventState.outOfOrder += 1;
    }
  }

  function renderTimeline() {
    nodes.eventTimeline.textContent = "";
    eventState.events.slice().reverse().forEach((event) => {
      const item = document.createElement("li");
      item.innerHTML = "<span></span><strong></strong><small></small>";
      item.querySelector("span").textContent = "#" + event.sequence;
      item.querySelector("strong").textContent = event.event_type;
      item.querySelector("small").textContent = event.provider_validation_status + " / is_live false";
      nodes.eventTimeline.appendChild(item);
    });
  }

  function setConnection(value) {
    nodes.connectionState.textContent = value;
    nodes.connectionState.className = value === "streaming" || value === "connected" ? "badge badge-ok" : "badge badge-warn";
  }

  function tickClocks() {
    const now = new Date();
    nodes.utcClock.textContent = "UTC " + now.toISOString().slice(11, 19);
    nodes.localClock.textContent = "Local " + now.toLocaleTimeString();
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
})();
