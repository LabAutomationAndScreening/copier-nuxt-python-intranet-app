import { execSync } from "node:child_process";

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

export function composeUp({ composeFile, services = [] }: { composeFile: string; services?: string[] }): void {
  const serviceArgs = services.length > 0 ? ` ${services.join(" ")}` : "";
  execSync(
    `docker compose --file="${composeFile}" up --detach --force-recreate --renew-anon-volumes --remove-orphans${serviceArgs}`,
    { stdio: "inherit" },
  );
}

export function composeDown({ composeFile }: { composeFile: string }): void {
  execSync(`docker compose --file="${composeFile}" down --volumes`, { stdio: "inherit" });
}

export async function waitForComposeHealthy({
  composeFile,
  maxAttempts = 30,
  retryDelayMs = 2000,
}: {
  composeFile: string;
  maxAttempts?: number;
  retryDelayMs?: number;
}): Promise<void> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const stdout = execSync(`docker compose --file="${composeFile}" ps --format json`, {
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
