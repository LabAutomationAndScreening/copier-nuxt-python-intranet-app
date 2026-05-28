import { execSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { APP_NAME, DEPLOYED_BACKEND_PORT_NUMBER } from "../setup/constants";
import { backendBaseUrl, isBuiltBackendE2E, isDockerComposeE2E } from "./ports";

// Brings up the app the E2E suite runs against, then waits until it is healthy. Runs once before
// the Playwright run; global-teardown.ts brings it back down. Two backends are supported, selected by
// env var (see ports.ts): a single built executable serving frontend + API, or a docker-compose stack.

const COMPOSE_FILE = fileURLToPath(new URL("../docker-compose.yaml", import.meta.url));

const executableExtension = process.platform === "win32" ? ".exe" : "";
const repoRoot = path.resolve(fileURLToPath(new URL("../../../", import.meta.url)));
const executablePath = path.resolve(repoRoot, `./backend/dist/${APP_NAME}/${APP_NAME}${executableExtension}`);

async function waitForHttpHealthcheck({
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

interface ComposePsService {
  Service: string;
  Health: string;
  State: string;
}

function isComposePsService(value: unknown): value is ComposePsService {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  if (!("Service" in value) || typeof value.Service !== "string") {
    return false;
  }
  if (!("Health" in value) || typeof value.Health !== "string") {
    return false;
  }
  if (!("State" in value) || typeof value.State !== "string") {
    return false;
  }
  return true;
}

async function waitForComposeHealthy({
  maxAttempts = 30,
  retryDelayMs = 2000,
}: { maxAttempts?: number; retryDelayMs?: number } = {}): Promise<void> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const stdout = execSync(`docker compose --file="${COMPOSE_FILE}" ps --format json`, {
      encoding: "utf-8",
      timeout: 10000,
    });
    const services: ComposePsService[] = [];
    for (const line of stdout.split("\n")) {
      if (line.trim().length === 0) {
        continue;
      }
      const parsed: unknown = JSON.parse(line);
      if (!isComposePsService(parsed)) {
        throw new Error(`Unexpected docker compose ps entry shape: ${line}`);
      }
      services.push(parsed);
    }
    // services without a healthcheck report Health as "" — treat those as ready once running
    const allReady = services.every((s) => s.State === "running" && (s.Health === "healthy" || s.Health === ""));
    if (services.length > 0 && allReady) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
  }
  throw new Error(`docker-compose containers failed to become healthy after ${maxAttempts} attempts`);
}

function startBuiltBackend(): void {
  if (!fs.existsSync(executablePath) || !fs.statSync(executablePath).isFile()) {
    throw new Error(`File not found: ${executablePath}`);
  }
  const port = new URL(backendBaseUrl()).port;
  console.log(`Starting app at ${executablePath} ...`);
  const child = spawn(
    executablePath,
    [
      "--host",
      "0.0.0.0", // TODO: could this just be 127.0.0.1 ?
      // in CI, sometimes the default port to deploy on is already in use, so we use a random open port
      "--port",
      port,
    ],
    {
      // TODO: figure out why Github CI pipelines fail without setting all allowed hosts
      stdio: "inherit",
    },
  );
  child.on("close", (code) => {
    console.log(`Process exited with code ${code}`);
  });
}

export default async function globalSetup(): Promise<void> {
  if (isBuiltBackendE2E) {
    startBuiltBackend();
    await waitForHttpHealthcheck({ url: `${backendBaseUrl()}/api/healthcheck` });
  }
  if (isDockerComposeE2E) {
    console.log("Starting docker-compose...");
    process.env.DEPLOYED_BACKEND_PORT_NUMBER = DEPLOYED_BACKEND_PORT_NUMBER.toString();
    execSync(
      `docker compose --file="${COMPOSE_FILE}" up --detach --force-recreate --renew-anon-volumes --remove-orphans`,
      {
        stdio: "inherit",
      },
    );
    await waitForComposeHealthy();
  }
}
