import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { APP_NAME } from "../setup/constants";

const executableExtension = process.platform === "win32" ? ".exe" : "";
const repoRoot = path.resolve(fileURLToPath(new URL("../../../", import.meta.url)));
export const builtBackendExecutablePath = path.resolve(
  repoRoot,
  `./backend/dist/${APP_NAME}/${APP_NAME}${executableExtension}`,
);

export function assertBuiltBackendExecutableExists(): void {
  if (!fs.existsSync(builtBackendExecutablePath) || !fs.statSync(builtBackendExecutablePath).isFile()) {
    throw new Error(`File not found: ${builtBackendExecutablePath}`);
  }
}

export async function waitForHttpHealthcheck({
  url,
  maxAttempts = 10,
  requestTimeoutMs = 5000,
}: {
  url: string;
  maxAttempts?: number;
  requestTimeoutMs?: number;
}): Promise<void> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(requestTimeoutMs) });
      if (res.ok) {
        return;
      }
    } catch {
      // ignore errors // TODO: make this more specific (e.g., only ignore network errors)
    }
    console.log(`Waiting for ${url} to become available... Attempt ${attempt}`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timeout waiting for ${url}`);
}

export interface SeparateBuiltBackend {
  baseUrl: string;
  exited: Promise<number | null>;
  output: () => string;
  stop: () => void;
}

// A second instance of the built executable, separate from the one global-setup starts for the rest of the
// suite, so a test can make it exit without taking the shared backend down. It logs to its own temporary
// folder so the two processes never share a log file.
export async function startSeparateBuiltBackend({ port }: { port: number }): Promise<SeparateBuiltBackend> {
  assertBuiltBackendExecutableExists();
  const logFolder = fs.mkdtempSync(path.join(os.tmpdir(), `${APP_NAME}-e2e-`));
  const child = spawn(
    builtBackendExecutablePath,
    ["--host", "127.0.0.1", "--port", port.toString(), "--log-folder", logFolder],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
  const chunks: string[] = [];
  child.stdout.on("data", (chunk: unknown) => chunks.push(String(chunk)));
  child.stderr.on("data", (chunk: unknown) => chunks.push(String(chunk)));
  const exited = new Promise<number | null>((resolve) => {
    child.on("close", (code) => {
      resolve(code);
    });
  });
  const baseUrl = `http://127.0.0.1:${port}`;
  const stop = () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill();
    }
  };
  try {
    await waitForHttpHealthcheck({ url: `${baseUrl}/api/healthcheck` });
  } catch (error) {
    stop(); // the caller never receives stop when this throws, so the process would otherwise outlive the test
    throw error;
  }
  return { baseUrl, exited, output: () => chunks.join(""), stop };
}
