import { writeSync } from "node:fs";

export const STDOUT_MAX_BYTES = 16384;
export const STDERR_MAX_BYTES = 2048;

export class AtomicOutputFailure extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

export function quarantineConsole() {
  const suppressed = () => undefined;
  console.log = suppressed;
  console.info = suppressed;
  console.debug = suppressed;
  console.warn = suppressed;
  console.error = suppressed;
}

export function writeFinalStdoutJson(payload, write = writeSync) {
  const text = JSON.stringify(payload);
  writeBoundedFd(1, text, STDOUT_MAX_BYTES, "dxlink_stdout_oversized", write);
}

export function writeFinalStderrCode(code, write = writeSync) {
  writeBoundedFd(2, code, STDERR_MAX_BYTES, "dxlink_stderr_oversized", write);
}

export function writeBoundedFd(fd, text, maxBytes, oversizedCode, write = writeSync) {
  const bytes = Buffer.from(text, "utf8");
  if (bytes.length > maxBytes) {
    throw new AtomicOutputFailure(oversizedCode);
  }
  let offset = 0;
  while (offset < bytes.length) {
    const written = write(fd, bytes, offset, bytes.length - offset);
    if (!Number.isInteger(written) || written <= 0) {
      throw new AtomicOutputFailure("dxlink_process_failed");
    }
    offset += written;
  }
  if (offset !== bytes.length) {
    throw new AtomicOutputFailure("dxlink_process_failed");
  }
}
