import { execSync } from "node:child_process";

import { DEPLOYED_BACKEND_PORT_NUMBER } from "../setup/constants";

// Brings up the docker-compose stack the E2E suite runs against, then polls until every container is
// healthy. Runs once before the Playwright run; global-teardown.ts brings it back down.

const COMPOSE_FILE = "../docker-compose.yaml";

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
    const stdout = execSync(`docker compose --file=${COMPOSE_FILE} ps --format json`, {
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

export default async function globalSetup(): Promise<void> {
  process.env.DEPLOYED_BACKEND_PORT_NUMBER = DEPLOYED_BACKEND_PORT_NUMBER.toString();
  execSync(`docker compose --file=${COMPOSE_FILE} up --detach --force-recreate --renew-anon-volumes --remove-orphans`, {
    stdio: "inherit",
  });
  await waitForComposeHealthy();
}
