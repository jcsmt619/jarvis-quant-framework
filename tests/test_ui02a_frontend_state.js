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

test("UI-02A exposes design tokens and icon metadata for every route", () => {
  assert.equal(reducers.ROUTES.length, 16);
  assert.ok(reducers.DESIGN_TOKENS.colors.nearBlack);
  assert.ok(reducers.DESIGN_TOKENS.colors.cyan);
  assert.ok(reducers.ROUTES.every((route) => route.length === 4 && route[3]));
});

test("fixture heartbeat refresh does not inflate duplicate-data counters", () => {
  let state = reducers.initialEventState();
  const heartbeat = {
    event_id: "evt-ui01-heartbeat",
    event_type: "heartbeat",
    sequence: 7,
    occurred_at: "2026-07-21T19:00:00Z",
    provider_validation_status: "pending",
  };
  let result = reducers.acceptEvent(state, heartbeat);
  assert.equal(result.accepted, true);
  state = result.state;

  for (let index = 0; index < 20; index += 1) {
    result = reducers.acceptEvent(state, heartbeat);
    assert.equal(result.accepted, true);
    assert.equal(result.reason, "heartbeat_refresh");
    state = result.state;
  }

  assert.equal(state.duplicates, 0);
  assert.equal(state.events.length, 0);
  assert.equal(state.lastSequence, 7);
});

test("duplicate and malformed rejection counters are bounded", () => {
  let state = reducers.initialEventState();
  state = reducers.acceptEvent(state, { event_id: "evt-1", event_type: "research_refreshed", sequence: 1 }).state;

  for (let index = 0; index < 200; index += 1) {
    state = reducers.acceptEvent(state, { event_id: "evt-1", event_type: "research_refreshed", sequence: 1 }).state;
    state = reducers.acceptEvent(state, null).state;
  }

  assert.equal(state.duplicates, reducers.MAX_REJECT_COUNT);
  assert.equal(state.malformed, reducers.MAX_REJECT_COUNT);
  assert.equal(state.rejectedRecent.length, reducers.MAX_REJECT_COUNT);
});

test("connection lifecycle distinguishes connected, fixture complete, stale, degraded, and lost", () => {
  let state = reducers.initialEventState();
  state = reducers.markConnectionOpened(state, 1, "2026-07-21T19:00:00Z");
  assert.equal(state.connectionState, "connected");

  state = reducers.acceptEvent(state, {
    event_id: "evt-1",
    event_type: "heartbeat",
    sequence: 1,
    occurred_at: "2026-07-21T19:00:00Z",
  }).state;
  assert.equal(reducers.deriveFreshnessState(state, Date.parse("2026-07-21T19:00:10Z")), "connected");
  assert.equal(reducers.deriveFreshnessState(state, Date.parse("2026-07-21T19:00:20Z")), "stale");
  assert.equal(reducers.deriveFreshnessState(state, Date.parse("2026-07-21T19:01:00Z")), "lost");

  state = reducers.acceptEvent(state, { event_id: "evt-4", event_type: "stream_gap", sequence: 4 }).state;
  assert.equal(reducers.deriveFreshnessState(state, Date.parse("2026-07-21T19:00:11Z")), "degraded");

  state = reducers.markFixtureComplete(state, "2026-07-21T19:00:12Z");
  assert.equal(reducers.deriveFreshnessState(state, Date.parse("2026-07-21T20:00:00Z")), "fixture_complete");
});

test("reconnect attempt count and delay remain bounded", () => {
  let state = reducers.initialEventState();
  for (let index = 0; index < 20; index += 1) {
    state = reducers.markReconnecting(state);
  }
  assert.equal(state.reconnectCount, reducers.MAX_RECONNECTS);
  assert.equal(reducers.reconnectDelay(99), 30000);
});
