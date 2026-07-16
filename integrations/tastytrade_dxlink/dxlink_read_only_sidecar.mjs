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
  "client_created",
  "connect_called",
  "transport_connected",
  "authentication_authorized",
  "feed_opened",
  "subscriptions_queued",
  "quote_received",
  "candle_received",
  "sample_complete",
  "cleanup",
]);

let outputWritten = false;
let cleanupStarted = false;

main().catch((error) => {
  safeExit(classifyError(error));
});

async function main() {
  const {
    DXLinkWebSocketClient,
    DXLinkFeed,
    FeedContract,
    FeedDataFormat,
  } = await import("@dxfeed/dxlink-api");
  const inputText = await readBoundedStdin();
  const request = parseRequest(inputText);
  const stage = createStageTracker();
  const latest = createLatestMap();
  const counts = {
    quote_records: 0,
    candle_records: 0,
    logical_records: 0,
    raw_batches_processed: 0,
    raw_records_processed: 0,
  };
  const client = new DXLinkWebSocketClient();
  stage.mark("client_created");
  let feed = null;
  let timeoutReason = "dxlink_connect_timeout";
  const timeout = setTimeout(() => safeExit(timeoutReason, client, feed, stage, counts), request.timeoutMs);

  try {
    attachClientListeners(client, stage);
    client.setAuthToken(request.quoteToken);
    feed = new DXLinkFeed(client, FeedContract.AUTO);
    stage.mark("feed_opened");
    configureFeed(feed, FeedDataFormat, request.timeoutMs);
    attachEvents(feed, (eventBatch) => {
      timeoutReason = updateTimeoutReason(latest);
      processBatch(eventBatch, request, latest, counts, stage);
      timeoutReason = updateTimeoutReason(latest);
      if (hasCompleteSample(latest)) {
        counts.logical_records = 4;
        stage.mark("sample_complete");
        clearTimeout(timeout);
        cleanup(client, feed, stage);
        writeResult(latest, stage, counts);
      }
    });
    const dxlinkUrl = request.dxlinkUrl;
    client.connect(dxlinkUrl);
    stage.mark("connect_called");
    stage.mark("transport_connected");
    stage.mark("authentication_authorized");
    timeoutReason = "dxlink_feed_open_timeout";
    subscribe(feed, "Quote", request.symbols);
    subscribe(feed, "Candle", request.symbols.map((symbol) => `${symbol}{=1m}`), request.fromTime);
    stage.mark("subscriptions_queued");
    timeoutReason = "dxlink_quote_timeout";
  } catch (error) {
    clearTimeout(timeout);
    cleanup(client, feed, stage);
    throw error;
  }

  await sleep(request.timeoutMs + 1);
  if (!outputWritten) {
    clearTimeout(timeout);
    safeExit(updateTimeoutReason(latest), client, feed, stage, counts);
  }
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

function subscribe(feed, eventType, symbols, fromTime = undefined) {
  if (!EVENT_TYPES.includes(eventType)) {
    throw new Error("subscription");
  }
  for (const symbol of symbols) {
    const subscription = { type: eventType, symbol };
    if (eventType === "Candle") {
      subscription.fromTime = fromTime;
    }
    feed.addSubscriptions(subscription);
  }
}

function attachClientListeners(client, stage) {
  const listener = () => stage.mark("transport_connected");
  for (const method of ["addEventListener", "addConnectionStateListener", "on"]) {
    if (typeof client[method] === "function") {
      try {
        method === "on" ? client[method]("state", listener) : client[method](listener);
      } catch {
      }
    }
  }
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
  process.stdout.write(JSON.stringify({
    ok: true,
    connected: true,
    disconnected: false,
    reconnect_count: 0,
    terminal_stage: stage.current,
    counts,
    events: sample,
  }));
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
  return new Map(APPROVED_SYMBOLS.flatMap((symbol) => []));
}

function createStageTracker() {
  return {
    current: "client_created",
    counts: Object.fromEntries(STAGES.map((stage) => [stage, 0])),
    mark(stage) {
      if (STAGES.includes(stage)) {
        this.current = stage;
        this.counts[stage] += 1;
      }
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

function updateTimeoutReason(latest) {
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
  if (message.includes("auth")) {
    return "dxlink_auth_timeout";
  }
  if (message.includes("subscription")) {
    return "dxlink_feed_open_timeout";
  }
  if (message.includes("Cannot find package") || message.includes("module")) {
    return "dxlink_dependency_unavailable";
  }
  return "dxlink_process_failed";
}

function cleanup(client, feed, stage) {
  if (cleanupStarted) {
    return;
  }
  cleanupStarted = true;
  stage.mark("cleanup");
  try {
    if (feed && typeof feed.close === "function") {
      feed.close();
    }
  } catch {
  }
  try {
    if (client && typeof client.close === "function") {
      client.close();
    }
  } catch {
  }
}

function safeExit(code, client = null, feed = null, stage = createStageTracker(), counts = {}) {
  cleanup(client, feed, stage);
  if (!outputWritten) {
    outputWritten = true;
    process.stderr.write(code);
  }
  process.exit(1);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
