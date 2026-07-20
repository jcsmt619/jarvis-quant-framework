import {
  AtomicOutputFailure,
  quarantineConsole,
  writeFinalStdoutJson,
} from "./atomic_output.mjs";

quarantineConsole();

const APPROVED_SYMBOLS = Object.freeze(["SPY", "QQQ"]);
const EVENT_TYPES = Object.freeze(["Quote", "Candle"]);
const MAX_STDIN_BYTES = 4096;
const MAX_BATCH_RECORDS = 16;
const MAX_RAW_RECORDS = 64;
const FEED_AGGREGATION_PERIOD_SECONDS = 1;
const HISTORICAL_LOOKBACK_MS = 30 * 60 * 1000;
const COMPACT_FIELDS = Object.freeze({
  Quote: ["eventSymbol", "time", "bidPrice", "askPrice"],
  Candle: ["eventSymbol", "time", "eventTime", "open", "high", "low", "close", "volume"],
});
const STAGES = Object.freeze([
  "child_started",
  "sdk_loaded",
  "client_created",
  "listeners_registered",
  "auth_token_set",
  "connect_called",
  "transport_connected",
  "authentication_authorized",
  "feed_created",
  "feed_opened",
  "quote_subscription_created",
  "candle_subscription_created",
  "subscriptions_active",
  "quote_received",
  "candle_received",
  "sample_complete",
  "cleanup_started",
  "cleanup_complete",
]);
const FAILURE_CODES = Object.freeze([
  "dxlink_dependency_unavailable",
  "dxlink_contract_mismatch",
  "dxlink_connect_timeout",
  "dxlink_auth_timeout",
  "dxlink_feed_open_timeout",
  "dxlink_subscription_timeout",
  "dxlink_quote_timeout",
  "dxlink_candle_timeout",
  "dxlink_sample_timeout",
  "dxlink_cleanup_failed",
  "dxlink_process_failed",
]);
const SAFETY_FLAGS = Object.freeze({
  real_paper_order_submitted: false,
  broker_order_call_performed: false,
  live_trading_enabled: false,
});

let outputWritten = false;

main().catch((error) => {
  const stage = error?.stage && typeof error.stage.safeFailure === "function" ? error.stage : createStageTracker();
  const counts = error?.counts && typeof error.counts === "object" ? error.counts : emptyRecordCounts();
  const terminalStage = typeof error?.terminalStage === "string" ? error.terminalStage : stage.current;
  stage.safeFailure(classifyError(error), counts, terminalStage);
});

async function main() {
  const stage = createStageTracker();
  stage.mark("child_started");
  const counts = emptyRecordCounts();
  let client = null;
  let feed = null;
  let subscriptions = [];

  try {
    const sdk = await import("@dxfeed/dxlink-api");
    stage.mark("sdk_loaded");
    const {
      DXLinkWebSocketClient,
      DXLinkFeed,
      DXLinkConnectionState,
      DXLinkAuthState,
      DXLinkChannelState,
      FeedContract,
      FeedDataFormat,
    } = sdk;
    assertSdkContract({ DXLinkConnectionState, DXLinkAuthState, DXLinkChannelState, FeedContract, FeedDataFormat });

    const inputText = await readBoundedStdin();
    const request = parseRequest(inputText);
    const latest = createLatestMap();
    client = new DXLinkWebSocketClient({ maxReconnectAttempts: 0 });
    stage.mark("client_created");

    const lifecycle = createLifecycleWaiters(client, { DXLinkConnectionState, DXLinkAuthState }, stage);
    stage.mark("listeners_registered");

    const timer = setTimeout(() => {
      const failure = timeoutCode(stage, latest);
      const terminalStage = stage.current;
      cleanup(client, feed, subscriptions, stage);
      stage.safeFailure(failure, counts, terminalStage);
    }, request.timeoutMs);

    client.setAuthToken(request.quoteToken);
    stage.mark("auth_token_set");
    client.connect(request.dxlinkUrl);
    stage.mark("connect_called");

    await lifecycle.transportConnected;
    stage.mark("transport_connected");
    await lifecycle.authAuthorized;
    stage.mark("authentication_authorized");

    feed = new DXLinkFeed(client, FeedContract.AUTO, { batchSubscriptionsTime: 0 });
    stage.mark("feed_created");
    configureFeed(feed, FeedDataFormat, request.timeoutMs);
    attachEvents(feed, (eventBatch) => {
      processBatch(eventBatch, request, latest, counts, stage);
      if (hasCompleteSample(latest)) {
        counts.logical_records = 4;
        stage.mark("sample_complete");
        clearTimeout(timer);
        const cleanupOk = cleanup(client, feed, subscriptions, stage);
        if (!cleanupOk) {
          stage.safeFailure("dxlink_cleanup_failed", counts, "sample_complete");
          return;
        }
        writeResult(latest, stage, counts);
      }
    });

    await waitForFeedOpen(feed, DXLinkChannelState, stage, counts);
    stage.mark("feed_opened");
    subscriptions = createSubscriptions(request);
    stage.mark("quote_subscription_created");
    stage.mark("candle_subscription_created");
    feed.addSubscriptions(subscriptions);
    stage.mark("subscriptions_active");
  } catch (error) {
    const terminalStage = stage.current;
    cleanup(client, feed, subscriptions, stage);
    error.stage = stage;
    error.terminalStage = terminalStage;
    error.counts = counts;
    throw error;
  }
}

function assertSdkContract({ DXLinkConnectionState, DXLinkAuthState, DXLinkChannelState, FeedContract, FeedDataFormat }) {
  if (
    DXLinkConnectionState?.CONNECTED !== "CONNECTED" ||
    DXLinkAuthState?.AUTHORIZED !== "AUTHORIZED" ||
    DXLinkChannelState?.OPENED !== "OPENED" ||
    FeedContract?.AUTO === undefined ||
    FeedDataFormat?.COMPACT === undefined
  ) {
    throw new Error("contract");
  }
}

function createLifecycleWaiters(client, { DXLinkConnectionState, DXLinkAuthState }) {
  if (
    typeof client.addConnectionStateChangeListener !== "function" ||
    typeof client.addAuthStateChangeListener !== "function" ||
    typeof client.addErrorListener !== "function"
  ) {
    throw new Error("contract");
  }
  let rejectAll = () => undefined;
  const transportConnected = new Promise((resolve, reject) => {
    rejectAll = reject;
    client.addConnectionStateChangeListener((state) => {
      if (state === DXLinkConnectionState.CONNECTED || state === "CONNECTED") {
        resolve();
      }
    });
  });
  const authAuthorized = new Promise((resolve, reject) => {
    const previousReject = rejectAll;
    rejectAll = (error) => {
      previousReject(error);
      reject(error);
    };
    client.addAuthStateChangeListener((state) => {
      if (state === DXLinkAuthState.AUTHORIZED || state === "AUTHORIZED") {
        resolve();
      }
    });
  });
  client.addErrorListener(() => rejectAll(new Error("process")));
  return { transportConnected, authAuthorized };
}

function waitForFeedOpen(feed, DXLinkChannelState, stage, counts) {
  if (typeof feed.addStateChangeListener !== "function" || typeof feed.getState !== "function") {
    throw new Error("contract");
  }
  return new Promise((resolve, reject) => {
    const onState = (state) => {
      if (state === DXLinkChannelState.OPENED || state === "OPENED") {
        resolve();
      }
      if (state === DXLinkChannelState.CLOSED || state === "CLOSED") {
        reject(Object.assign(new Error("subscription"), { stage, counts }));
      }
    };
    feed.addStateChangeListener(onState);
    onState(feed.getState());
  });
}

function configureFeed(feed, FeedDataFormat, timeoutMs) {
  if (typeof feed.configure !== "function") {
    throw new Error("subscription");
  }
  if (FEED_AGGREGATION_PERIOD_SECONDS <= 0 || FEED_AGGREGATION_PERIOD_SECONDS * 1000 >= timeoutMs) {
    throw new Error("timing");
  }
  feed.configure({
    acceptAggregationPeriod: FEED_AGGREGATION_PERIOD_SECONDS,
    acceptDataFormat: FeedDataFormat.COMPACT,
    acceptEventFields: COMPACT_FIELDS,
  });
}

function createSubscriptions(request) {
  const subscriptions = [];
  for (const symbol of request.symbols) {
    subscriptions.push({ type: "Quote", symbol });
  }
  for (const symbol of request.symbols) {
    subscriptions.push({ type: "Candle", symbol: `${symbol}{=1m}`, fromTime: request.fromTime });
  }
  return subscriptions;
}

function attachEvents(feed, listener) {
  if (typeof feed.addEventListener === "function") {
    feed.addEventListener(listener);
    return;
  }
  throw new Error("subscription");
}

function processBatch(eventBatch, request, latest, counts, stage) {
  counts.raw_batches_processed += 1;
  for (const payload of boundedEventBatch(eventBatch)) {
    counts.raw_records_processed += 1;
    if (counts.raw_records_processed > MAX_RAW_RECORDS) {
      throw new Error("payload");
    }
    const eventType = payload.eventType || payload.type;
    const normalized = normalizeEvent(eventType, payload, request.acquisitionTimestampMs, request.acquisitionTimestamp);
    if (!normalized) {
      continue;
    }
    const key = `${normalized.event_type}:${normalized.symbol}`;
    const previous = latest.get(key);
    if (!previous || Date.parse(normalized.exchange_timestamp) >= Date.parse(previous.exchange_timestamp)) {
      latest.set(key, normalized);
    }
    if (normalized.event_type === "Quote") {
      stage.mark("quote_received");
    }
    if (normalized.event_type === "Candle") {
      stage.mark("candle_received");
    }
  }
  counts.quote_records = countType(latest, "Quote");
  counts.candle_records = countType(latest, "Candle");
  counts.logical_records = counts.quote_records + counts.candle_records;
}

function boundedEventBatch(eventBatch) {
  if (Array.isArray(eventBatch)) {
    return eventBatch.slice(0, MAX_BATCH_RECORDS);
  }
  if (eventBatch && typeof eventBatch[Symbol.iterator] === "function") {
    const bounded = [];
    for (const event of eventBatch) {
      bounded.push(event);
      if (bounded.length >= MAX_BATCH_RECORDS) {
        break;
      }
    }
    return bounded;
  }
  return [eventBatch];
}

function normalizeEvent(eventType, payload, acquisitionTimestampMs, acquisitionTimestamp) {
  if (eventType === "Quote") {
    const symbol = normalizeSymbol(payload.eventSymbol);
    return {
      event_type: "Quote",
      symbol,
      provider_timestamp: isoFromProviderTime(payload.time, acquisitionTimestampMs),
      exchange_timestamp: isoFromProviderTime(payload.time, acquisitionTimestampMs),
      acquisition_timestamp: acquisitionTimestamp,
      bidPrice: numberField(payload.bidPrice),
      askPrice: numberField(payload.askPrice),
    };
  }
  if (eventType === "Candle") {
    const symbol = normalizeSymbol(payload.eventSymbol);
    const providerTime = isoFromProviderTime(payload.time, acquisitionTimestampMs);
    const exchangeTime = isoFromProviderTime(payload.eventTime ?? payload.time, acquisitionTimestampMs);
    return {
      event_type: "Candle",
      symbol,
      provider_timestamp: providerTime,
      exchange_timestamp: exchangeTime,
      acquisition_timestamp: acquisitionTimestamp,
      open: numberField(payload.open),
      high: numberField(payload.high),
      low: numberField(payload.low),
      close: numberField(payload.close),
      volume: integerField(payload.volume),
    };
  }
  return null;
}

function hasCompleteSample(latest) {
  return APPROVED_SYMBOLS.every((symbol) =>
    latest.has(`Quote:${symbol}`) && latest.has(`Candle:${symbol}`)
  );
}

function writeResult(latest, stage, counts) {
  if (outputWritten) {
    return;
  }
  outputWritten = true;
  const sample = [];
  for (const eventType of EVENT_TYPES) {
    for (const symbol of APPROVED_SYMBOLS) {
      const event = latest.get(`${eventType}:${symbol}`);
      if (event) {
        sample.push(event);
      }
    }
  }
  writeFinalStdoutJson({
    ok: true,
    connected: true,
    disconnected: false,
    reconnect_count: 0,
    terminal_stage: stage.current,
    stage_counts: stage.counts,
    counts,
    events: sample,
  });
  process.exit(0);
}

function parseRequest(text) {
  const payload = JSON.parse(text);
  const symbols = payload.symbols;
  const acquisitionTimestampMs = Date.parse(payload.acquisitionTimestamp);
  const fromTime = acquisitionTimestampMs - HISTORICAL_LOOKBACK_MS;
  if (!Array.isArray(symbols) || symbols.join("|") !== APPROVED_SYMBOLS.join("|")) {
    throw new Error("subscription");
  }
  if (
    typeof payload.quoteToken !== "string" ||
    payload.quoteToken.length < 1 ||
    typeof payload.dxlinkUrl !== "string" ||
    !payload.dxlinkUrl.startsWith("wss://") ||
    typeof payload.acquisitionTimestamp !== "string" ||
    !Number.isFinite(acquisitionTimestampMs) ||
    !Number.isFinite(fromTime) ||
    fromTime >= acquisitionTimestampMs ||
    acquisitionTimestampMs - fromTime !== HISTORICAL_LOOKBACK_MS ||
    !Number.isInteger(payload.timeoutMs) ||
    payload.timeoutMs < 2_000 ||
    payload.timeoutMs > 30_000 ||
    FEED_AGGREGATION_PERIOD_SECONDS * 1000 >= payload.timeoutMs
  ) {
    throw new Error("input");
  }
  return {
    quoteToken: payload.quoteToken,
    dxlinkUrl: payload.dxlinkUrl,
    symbols,
    acquisitionTimestamp: new Date(acquisitionTimestampMs).toISOString(),
    acquisitionTimestampMs,
    fromTime,
    timeoutMs: payload.timeoutMs,
  };
}

async function readBoundedStdin() {
  let text = "";
  for await (const chunk of process.stdin) {
    text += chunk;
    if (Buffer.byteLength(text, "utf8") > MAX_STDIN_BYTES) {
      throw new Error("input");
    }
  }
  return text;
}

function normalizeSymbol(value) {
  if (typeof value !== "string") {
    throw new Error("payload");
  }
  const upper = value.toUpperCase();
  const symbol = APPROVED_SYMBOLS.find((candidate) =>
    upper === candidate || upper.startsWith(`${candidate}{`) || upper.startsWith(`${candidate}:`)
  );
  if (!symbol) {
    throw new Error("payload");
  }
  return symbol;
}

function numberField(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error("payload");
  }
  return number;
}

function integerField(value) {
  const number = numberField(value);
  if (!Number.isInteger(number)) {
    throw new Error("payload");
  }
  return number;
}

function isoFromProviderTime(value, acquisitionTimestampMs) {
  const date = typeof value === "number" ? new Date(value) : new Date(String(value));
  if (!Number.isFinite(date.getTime()) || date.getTime() > acquisitionTimestampMs) {
    throw new Error("payload");
  }
  return date.toISOString();
}

function createLatestMap() {
  return new Map(APPROVED_SYMBOLS.flatMap(() => []));
}

function emptyRecordCounts() {
  return {
    quote_records: 0,
    candle_records: 0,
    logical_records: 0,
    raw_batches_processed: 0,
    raw_records_processed: 0,
  };
}

function createStageTracker() {
  return {
    current: "child_started",
    counts: Object.fromEntries(STAGES.map((stage) => [stage, 0])),
    mark(stage) {
      if (STAGES.includes(stage)) {
        this.current = stage;
        this.counts[stage] += 1;
      }
    },
    safeFailure(code, counts, terminalStage = this.current) {
      if (outputWritten) {
        return;
      }
      outputWritten = true;
      try {
        writeFinalStdoutJson({
          ok: false,
          failure_code: FAILURE_CODES.includes(code) ? code : "dxlink_process_failed",
          terminal_stage: terminalStage,
          stage_counts: this.counts,
          counts,
          approved_symbols: APPROVED_SYMBOLS,
          approved_event_types: EVENT_TYPES,
          child_timeout_ms: 30000,
          cleanup_status: this.counts.cleanup_complete > 0 ? "complete" : "failed",
          ...SAFETY_FLAGS,
        });
      } catch (error) {
        if (error instanceof AtomicOutputFailure) {
          return;
        }
      }
      process.exit(1);
    },
  };
}

function countType(latest, eventType) {
  let count = 0;
  for (const symbol of APPROVED_SYMBOLS) {
    if (latest.has(`${eventType}:${symbol}`)) {
      count += 1;
    }
  }
  return count;
}

function timeoutCode(stage, latest) {
  if (stage.counts.transport_connected === 0) {
    return "dxlink_connect_timeout";
  }
  if (stage.counts.authentication_authorized === 0) {
    return "dxlink_auth_timeout";
  }
  if (stage.counts.feed_opened === 0) {
    return "dxlink_feed_open_timeout";
  }
  if (stage.counts.subscriptions_active === 0) {
    return "dxlink_subscription_timeout";
  }
  const quotes = countType(latest, "Quote");
  const candles = countType(latest, "Candle");
  if (quotes < APPROVED_SYMBOLS.length) {
    return "dxlink_quote_timeout";
  }
  if (candles < APPROVED_SYMBOLS.length) {
    return "dxlink_candle_timeout";
  }
  return "dxlink_sample_timeout";
}

function classifyError(error) {
  const message = String(error && error.message ? error.message : "");
  if (message.includes("contract")) {
    return "dxlink_contract_mismatch";
  }
  if (message.includes("auth")) {
    return "dxlink_auth_timeout";
  }
  if (message.includes("subscription")) {
    return "dxlink_subscription_timeout";
  }
  if (message.includes("Cannot find package") || message.includes("module")) {
    return "dxlink_dependency_unavailable";
  }
  return "dxlink_process_failed";
}

function cleanup(client, feed, subscriptions, stage) {
  if (stage.counts.cleanup_started > 0) {
    return stage.counts.cleanup_complete > 0;
  }
  stage.mark("cleanup_started");
  let ok = true;
  try {
    if (feed && typeof feed.removeSubscriptions === "function" && subscriptions.length > 0) {
      feed.removeSubscriptions(subscriptions);
    }
  } catch {
    ok = false;
  }
  try {
    if (feed && typeof feed.close === "function") {
      feed.close();
    }
  } catch {
    ok = false;
  }
  try {
    if (client && typeof client.close === "function") {
      client.close();
    }
  } catch {
    ok = false;
  }
  if (ok) {
    stage.mark("cleanup_complete");
  }
  return ok;
}
