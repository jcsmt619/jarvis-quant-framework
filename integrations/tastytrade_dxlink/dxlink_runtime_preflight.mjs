import { readFile, lstat, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  AtomicOutputFailure,
  quarantineConsole,
  writeFinalStderrCode,
  writeFinalStdoutJson,
} from "./atomic_output.mjs";

quarantineConsole();

const SDK_PACKAGE = "@dxfeed/dxlink-api";
const SDK_VERSION = "0.3.0";
const MAX_PACKAGE_SEARCH_STEPS = 8;
const FAILURE_CODES = new Set([
  "dxlink_dependency_unavailable",
  "dxlink_package_metadata_unavailable",
  "dxlink_contract_mismatch",
  "dxlink_process_failed",
]);

class PreflightFailure extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

main().catch((error) => {
  const code = error instanceof PreflightFailure && FAILURE_CODES.has(error.code)
    ? error.code
    : "dxlink_process_failed";
  try {
    writeFinalStderrCode(code);
  } catch (writeError) {
    if (writeError instanceof AtomicOutputFailure && writeError.code !== code) {
      try {
        writeFinalStderrCode(writeError.code);
      } catch {
      }
    }
  }
  process.exit(1);
});

async function main() {
  const sdkEntryPath = await resolveSdkEntryPath();
  const packageJson = await readInstalledPackageManifest(sdkEntryPath);
  if (!packageJson || typeof packageJson !== "object" || Array.isArray(packageJson)) {
    fail("dxlink_package_metadata_unavailable");
  }
  if (packageJson.name !== SDK_PACKAGE || packageJson.version !== SDK_VERSION) {
    fail("dxlink_contract_mismatch");
  }

  let sdk;
  try {
    sdk = await import(SDK_PACKAGE);
  } catch {
    fail("dxlink_dependency_unavailable");
  }

  const {
    DXLinkWebSocketClient,
    DXLinkFeed,
    FeedContract,
    FeedDataFormat,
  } = sdk;

  if (FeedContract?.AUTO === undefined || FeedDataFormat?.COMPACT === undefined) {
    fail("dxlink_contract_mismatch");
  }

  const client = new DXLinkWebSocketClient();
  assertMethod(client, "connect");
  assertMethod(client, "setAuthToken");

  const feed = new DXLinkFeed(client, FeedContract.AUTO);
  assertMethod(feed, "configure");
  assertMethod(feed, "addSubscriptions");
  assertMethod(feed, "addEventListener");

  writeFinalStdoutJson({
    ok: true,
    sdk: SDK_PACKAGE,
    contract: SDK_VERSION,
    connection_attempted: false,
    credentials_accepted: false,
  });
}

async function resolveSdkEntryPath() {
  let resolved;
  try {
    resolved = import.meta.resolve("@dxfeed/dxlink-api");
  } catch (error) {
    if (error?.code === "ERR_INVALID_PACKAGE_CONFIG") {
      fail("dxlink_package_metadata_unavailable");
    }
    fail("dxlink_dependency_unavailable");
  }
  if (!resolved.startsWith("file:")) {
    fail("dxlink_package_metadata_unavailable");
  }
  try {
    return path.resolve(fileURLToPath(resolved));
  } catch {
    fail("dxlink_package_metadata_unavailable");
  }
}

async function readInstalledPackageManifest(sdkEntryPath) {
  const packageRoot = installedPackageRoot(sdkEntryPath);
  await rejectSymlinkOrEscape(sdkEntryPath, packageRoot);

  const manifestPath = await nearestPackageManifest(sdkEntryPath, packageRoot);
  if (manifestPath !== path.join(packageRoot, "package.json")) {
    fail("dxlink_package_metadata_unavailable");
  }

  let text;
  try {
    text = await readFile(manifestPath, "utf8");
  } catch {
    fail("dxlink_package_metadata_unavailable");
  }

  try {
    return JSON.parse(text);
  } catch {
    fail("dxlink_package_metadata_unavailable");
  }
}

function installedPackageRoot(sdkEntryPath) {
  const parts = path.resolve(sdkEntryPath).split(path.sep);
  for (let index = 0; index <= parts.length - 4; index += 1) {
    if (
      parts[index] === "node_modules" &&
      parts[index + 1] === "@dxfeed" &&
      parts[index + 2] === "dxlink-api"
    ) {
      return parts.slice(0, index + 3).join(path.sep) || path.sep;
    }
  }
  fail("dxlink_package_metadata_unavailable");
}

async function rejectSymlinkOrEscape(sdkEntryPath, packageRoot) {
  try {
    const packageRootStat = await lstat(packageRoot);
    const sdkEntryStat = await lstat(sdkEntryPath);
    if (packageRootStat.isSymbolicLink() || sdkEntryStat.isSymbolicLink()) {
      fail("dxlink_package_metadata_unavailable");
    }
    const realPackageRoot = path.resolve(await realpath(packageRoot));
    const realSdkEntry = path.resolve(await realpath(sdkEntryPath));
    if (realPackageRoot !== packageRoot || !isPathWithin(realSdkEntry, realPackageRoot)) {
      fail("dxlink_package_metadata_unavailable");
    }
  } catch (error) {
    if (error instanceof PreflightFailure) {
      throw error;
    }
    fail("dxlink_package_metadata_unavailable");
  }
}

async function nearestPackageManifest(sdkEntryPath, packageRoot) {
  let current = path.dirname(sdkEntryPath);
  const manifests = [];
  for (let step = 0; step <= MAX_PACKAGE_SEARCH_STEPS; step += 1) {
    if (!isPathWithin(current, packageRoot)) {
      fail("dxlink_package_metadata_unavailable");
    }
    const candidate = path.join(current, "package.json");
    try {
      const stat = await lstat(candidate);
      if (stat.isSymbolicLink()) {
        fail("dxlink_package_metadata_unavailable");
      }
      if (stat.isFile()) {
        manifests.push(candidate);
      }
    } catch (error) {
      if (error instanceof PreflightFailure) {
        throw error;
      }
    }
    if (current === packageRoot) {
      break;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      fail("dxlink_package_metadata_unavailable");
    }
    current = parent;
  }
  if (manifests.length !== 1) {
    fail("dxlink_package_metadata_unavailable");
  }
  return manifests[0];
}

function isPathWithin(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function assertMethod(value, methodName) {
  if (!value || typeof value[methodName] !== "function") {
    fail("dxlink_contract_mismatch");
  }
}

function fail(code) {
  throw new PreflightFailure(code);
}
