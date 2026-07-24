const assert = require("node:assert");
const fs = require("node:fs");
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

const html = fs.readFileSync("ui02_desktop_shell/static/index.html", "utf8");
const css = fs.readFileSync("ui02_desktop_shell/static/theme.css", "utf8");
const app = fs.readFileSync("ui02_desktop_shell/static/app.js", "utf8");

test("UI-05 status overlay and about panel expose local safety state", () => {
  assert.match(html, /app-status-overlay/);
  assert.match(html, /desktopLocalService/);
  assert.match(html, /desktopGateway/);
  assert.match(html, /desktopEventStream/);
  assert.match(html, /UI-05\.0/);
  assert.match(html, /LIVE TRADING: DISABLED/);
  assert.match(html, /Jarvis Desktop Help/);
  assert.match(html, /Provider validation remains pending/);
});

test("UI-05 responsive tables use contained scroll and compact cards", () => {
  assert.match(app, /data-responsive-table/);
  assert.match(app, /compact-card-mode/);
  assert.match(app, /table-card-grid/);
  assert.match(app, /compactTableCard/);
  assert.match(css, /\.table-scroll[\s\S]*overflow-x: auto/);
  assert.match(css, /word-break: normal/);
  assert.match(css, /white-space: nowrap/);
  assert.match(css, /\.tabular-nums/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.table-card-grid/);
});

test("UI-05 event reconnect remains bounded with one SSE connection", () => {
  assert.equal(app.match(/new EventSource\(/g).length, 1);
  assert.equal(reducers.MAX_RECONNECTS, 8);
  let state = reducers.initialEventState();
  for (let index = 0; index < 20; index += 1) {
    state = reducers.markReconnecting(state);
  }
  assert.equal(state.reconnectCount, reducers.MAX_RECONNECTS);
  assert.equal(reducers.reconnectDelay(99), 30000);
});

test("UI-05 safety constants remain disabled and pending", () => {
  const envelope = {
    provider_validation_status: "pending",
    source_mode: "fixture",
    safety_state: { live_trading_enabled: false, is_live: false, live_trading_status: "LIVE TRADING: DISABLED" },
    data: { is_live: false, ui04: { is_live: false, risk_gate: { decision: "BLOCKED_BY_SAFETY_GATE" } } },
  };
  const vm = reducers.normalizeUi04Envelope(envelope, "risk-gate");
  assert.equal(vm.providerValidationStatus, "pending");
  assert.equal(vm.isLive, false);
  assert.equal(vm.liveTradingStatus, "LIVE TRADING: DISABLED");
  assert.equal(vm.riskGate.decision, "BLOCKED_BY_SAFETY_GATE");
});
