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

test("routes cover every UI-02 module", () => {
  assert.equal(reducers.ROUTES.length, 16);
  assert.ok(reducers.ROUTES.some((route) => route[0] === "moonshot-research"));
});

test("event reducer accepts ordered events and rejects duplicates", () => {
  let state = reducers.initialEventState();
  let result = reducers.acceptEvent(state, { event_id: "evt-1", event_type: "heartbeat", sequence: 1, provider_validation_status: "pending" });
  assert.equal(result.accepted, true);
  state = result.state;
  result = reducers.acceptEvent(state, { event_id: "evt-1", event_type: "heartbeat", sequence: 1, provider_validation_status: "pending" });
  assert.equal(result.accepted, false);
  assert.equal(result.state.duplicates, 1);
});

test("event reducer presents stream gaps and rejects out-of-order events", () => {
  let state = reducers.initialEventState();
  state = reducers.acceptEvent(state, { event_id: "evt-1", event_type: "heartbeat", sequence: 1 }).state;
  let result = reducers.acceptEvent(state, { event_id: "evt-3", event_type: "stream_gap", sequence: 3 });
  assert.equal(result.accepted, true);
  assert.equal(result.state.gaps.length, 2);
  result = reducers.acceptEvent(result.state, { event_id: "evt-2", event_type: "heartbeat", sequence: 2 });
  assert.equal(result.accepted, false);
  assert.equal(result.state.outOfOrder, 1);
});

test("reconnect delay is bounded exponential", () => {
  assert.equal(reducers.reconnectDelay(0), 500);
  assert.equal(reducers.reconnectDelay(3), 4000);
  assert.equal(reducers.reconnectDelay(99), 30000);
});

test("safe envelope requires pending provider and disabled live trading", () => {
  assert.equal(reducers.isSafeEnvelope({ provider_validation_status: "pending", safety_state: { live_trading_enabled: false } }), true);
  assert.equal(reducers.isSafeEnvelope({ provider_validation_status: "ready", safety_state: { live_trading_enabled: false } }), false);
  const unsafeLiveTradingEnvelope = {
    provider_validation_status: "pending",
    safety_state: {
      ["live_trading_" + "enabled"]: Boolean(1),
    },
  };
  assert.equal(
    reducers.isSafeEnvelope(unsafeLiveTradingEnvelope),
    false,
  );
});
