import { execFileSync, spawnSync } from "node:child_process";

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
  execFileSync(
    "docker",
    [
      "compose",
      "--file",
      composeFile,
      "up",
      "--detach",
      "--force-recreate",
      "--renew-anon-volumes",
      "--remove-orphans",
      ...services,
    ],
    { stdio: "inherit", timeout: 120000 },
  );
}

export function composeDown({ composeFile }: { composeFile: string }): void {
  execFileSync("docker", ["compose", "--file", composeFile, "down", "--volumes"], {
    stdio: "inherit",
    timeout: 120000,
  });
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
    const stdout = execFileSync("docker", ["compose", "--file", composeFile, "ps", "--format", "json"], {
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

export function composeServiceContainerId({ composeFile, service }: { composeFile: string; service: string }): string {
  return execFileSync("docker", ["compose", "--file", composeFile, "ps", "--quiet", service], {
    encoding: "utf-8",
    timeout: 10000,
  }).trim();
}

export function containerRestartCount({ containerId }: { containerId: string }): number {
  return Number(
    execFileSync("docker", ["inspect", "--format", "{{.RestartCount}}", containerId], {
      encoding: "utf-8",
      timeout: 10000,
    }).trim(),
  );
}

export async function waitForContainerRestart({
  containerId,
  previousRestartCount,
  maxAttempts = 60,
  retryDelayMs = 500,
}: {
  containerId: string;
  previousRestartCount: number;
  maxAttempts?: number;
  retryDelayMs?: number;
}): Promise<void> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (containerRestartCount({ containerId }) > previousRestartCount) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
  }
  throw new Error(`container ${containerId} was not restarted after ${maxAttempts} attempts`);
}

export function containerExitCodesSince({ containerId, since }: { containerId: string; since: string }): string[] {
  const stdout = execFileSync(
    "docker",
    [
      "events",
      "--since",
      since,
      "--until",
      new Date().toISOString(),
      "--filter",
      `container=${containerId}`,
      "--filter",
      "event=die",
      "--format",
      "{{.Actor.Attributes.exitCode}}",
    ],
    { encoding: "utf-8", timeout: 10000 },
  );
  return stdout.split("\n").filter((line) => line.trim().length > 0);
}

export function containerLogsSince({ containerId, since }: { containerId: string; since: string }): string {
  // docker logs replays the container's stderr (where uvicorn logs its lifecycle) on its own stderr, so capture both
  const result = spawnSync("docker", ["logs", "--since", since, containerId], { encoding: "utf-8", timeout: 10000 });
  if (result.status !== 0) {
    throw new Error(`docker logs failed for ${containerId}: ${result.stderr}`);
  }
  return `${result.stdout}${result.stderr}`;
}
