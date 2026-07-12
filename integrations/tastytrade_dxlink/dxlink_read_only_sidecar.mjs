const APPROVED_SYMBOLS = Object.freeze(["SPY", "QQQ"]);
const EVENT_TYPES = Object.freeze(["Quote", "Candle"]);
const MAX_STDIN_BYTES = 4096;
const MAX_EVENTS = 8;
const COMPACT_FIELDS = Object.freeze({
  Quote: ["eventSymbol", "time", "bidPrice", "askPrice"],
  Candle: ["eventSymbol", "time", "eventTime", "open", "high", "low", "close", "volume"],
});

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
  const client = new DXLinkWebSocketClient();
  const events = [];
  let closed = false;
  const timeout = setTimeout(() => safeExit("dxlink_timeout", client), request.timeoutMs);

  try {
    client.setAuthToken(request.quoteToken);
    const feed = new DXLinkFeed(client, FeedContract.AUTO);
    configureFeed(feed, FeedDataFormat);
    await openClient(client, request.dxlinkUrl);
    attachEvents(feed, (eventBatch) => {
      for (const payload of boundedEventBatch(eventBatch)) {
        const eventType = payload.eventType || payload.type;
        const normalized = normalizeEvent(eventType, payload, request.acquisitionTimestamp);
        if (normalized) {
          events.push(normalized);
        }
        if (hasCompleteSample(events) || events.length >= MAX_EVENTS) {
          closed = true;
          clearTimeout(timeout);
          closeQuietly(client);
          writeResult(events);
        }
      }
    });
    subscribe(feed, "Quote", request.symbols);
    subscribe(feed, "Candle", request.symbols.map((symbol) => `${symbol}{=1m}`));
  } catch (error) {
    clearTimeout(timeout);
    closeQuietly(client);
    throw error;
  }

  await sleep(request.timeoutMs);
  if (!closed) {
    clearTimeout(timeout);
    closeQuietly(client);
    safeExit("dxlink_timeout");
  }
}

function configureFeed(feed, FeedDataFormat) {
  if (typeof feed.configure !== "function") {
    throw new Error("subscription");
  }
  feed.configure({
    acceptAggregationPeriod: 60,
    acceptDataFormat: FeedDataFormat.COMPACT,
    acceptEventFields: COMPACT_FIELDS,
  });
}

function subscribe(feed, eventType, symbols) {
  if (!EVENT_TYPES.includes(eventType)) {
    throw new Error("subscription");
  }
  for (const symbol of symbols) {
    feed.addSubscriptions({ type: eventType, symbol });
  }
}

function attachEvents(feed, listener) {
  if (typeof feed.addEventListener === "function") {
    feed.addEventListener(listener);
    return;
  }
  throw new Error("subscription");
}

function boundedEventBatch(eventBatch) {
  if (Array.isArray(eventBatch)) {
    return eventBatch.slice(0, MAX_EVENTS);
  }
  if (eventBatch && typeof eventBatch[Symbol.iterator] === "function") {
    const bounded = [];
    for (const event of eventBatch) {
      bounded.push(event);
      if (bounded.length >= MAX_EVENTS) {
        break;
      }
    }
    return bounded;
  }
  return [eventBatch];
}

async function openClient(client, dxlinkUrl) {
  if (typeof client.connect === "function") {
    await client.connect(dxlinkUrl);
  }
}

function normalizeEvent(eventType, payload, acquisitionTimestamp) {
  if (eventType === "Quote") {
    const symbol = normalizeSymbol(payload.eventSymbol);
    return {
      event_type: "Quote",
      symbol,
      provider_timestamp: isoFromProviderTime(payload.time),
      exchange_timestamp: isoFromProviderTime(payload.time),
      acquisition_timestamp: acquisitionTimestamp,
      bidPrice: numberField(payload.bidPrice),
      askPrice: numberField(payload.askPrice),
    };
  }
  if (eventType === "Candle") {
    const symbol = normalizeSymbol(payload.eventSymbol);
    return {
      event_type: "Candle",
      symbol,
      provider_timestamp: isoFromProviderTime(payload.time),
      exchange_timestamp: isoFromProviderTime(payload.eventTime ?? payload.time),
      acquisition_timestamp: acquisitionTimestamp,
      open: numberField(payload.open),
      high: numberField(payload.high),
      low: numberField(payload.low),
      close: numberField(payload.close),
      volume: numberField(payload.volume),
    };
  }
  return null;
}

function hasCompleteSample(events) {
  return APPROVED_SYMBOLS.every((symbol) =>
    events.some((event) => event.event_type === "Quote" && event.symbol === symbol) &&
    events.some((event) => event.event_type === "Candle" && event.symbol === symbol)
  );
}

function writeResult(events) {
  const sample = [];
  for (const eventType of EVENT_TYPES) {
    for (const symbol of APPROVED_SYMBOLS) {
      const event = events.find((item) => item.event_type === eventType && item.symbol === symbol);
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
    events: sample,
  }));
  process.exit(0);
}

function parseRequest(text) {
  const payload = JSON.parse(text);
  const symbols = payload.symbols;
  if (!Array.isArray(symbols) || symbols.join("|") !== APPROVED_SYMBOLS.join("|")) {
    throw new Error("subscription");
  }
  if (
    typeof payload.quoteToken !== "string" ||
    payload.quoteToken.length < 1 ||
    typeof payload.dxlinkUrl !== "string" ||
    !payload.dxlinkUrl.startsWith("wss://") ||
    typeof payload.acquisitionTimestamp !== "string" ||
    !Number.isInteger(payload.timeoutMs) ||
    payload.timeoutMs < 1 ||
    payload.timeoutMs > 30000
  ) {
    throw new Error("input");
  }
  return payload;
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

function isoFromProviderTime(value) {
  const date = typeof value === "number" ? new Date(value) : new Date(String(value));
  if (!Number.isFinite(date.getTime())) {
    throw new Error("payload");
  }
  return date.toISOString();
}

function classifyError(error) {
  const message = String(error && error.message ? error.message : "");
  if (message.includes("auth")) {
    return "dxlink_authentication_failed";
  }
  if (message.includes("subscription")) {
    return "dxlink_subscription_failed";
  }
  if (message.includes("Cannot find package") || message.includes("module")) {
    return "dxlink_dependency_unavailable";
  }
  return "dxlink_process_failed";
}

function closeQuietly(client) {
  try {
    if (client && typeof client.close === "function") {
      client.close();
    }
  } catch {
  }
}

function safeExit(code, client = null) {
  closeQuietly(client);
  process.stderr.write(code);
  process.exit(1);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
