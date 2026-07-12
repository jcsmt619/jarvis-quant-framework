import { createRequire } from "node:module";

main().catch((error) => {
  const message = String(error && error.message ? error.message : "");
  if (message.includes("Cannot find package") || message.includes("module")) {
    process.stderr.write("dxlink_dependency_unavailable");
  } else {
    process.stderr.write("dxlink_process_failed");
  }
  process.exit(1);
});

async function main() {
  const {
    DXLinkWebSocketClient,
    DXLinkFeed,
    FeedContract,
    FeedDataFormat,
  } = await import("@dxfeed/dxlink-api");
  const require = createRequire(import.meta.url);
  const packageJson = require("@dxfeed/dxlink-api/package.json");

  if (packageJson.version !== "0.3.0") {
    throw new Error("contract");
  }

  if (FeedContract.AUTO === undefined || FeedDataFormat.COMPACT === undefined) {
    throw new Error("contract");
  }

  const client = new DXLinkWebSocketClient();
  assertMethod(client, "connect");
  assertMethod(client, "setAuthToken");

  const feed = new DXLinkFeed(client, FeedContract.AUTO);
  assertMethod(feed, "configure");
  assertMethod(feed, "addSubscriptions");
  assertMethod(feed, "addEventListener");

  process.stdout.write(JSON.stringify({
    ok: true,
    sdk: "@dxfeed/dxlink-api",
    contract: "0.3.0",
    connection_attempted: false,
    credentials_accepted: false,
  }));
}

function assertMethod(value, methodName) {
  if (!value || typeof value[methodName] !== "function") {
    throw new Error("contract");
  }
}
