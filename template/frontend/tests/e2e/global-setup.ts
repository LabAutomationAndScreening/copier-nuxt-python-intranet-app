import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { DEPLOYED_BACKEND_PORT_NUMBER } from "../setup/constants";
import {
  assertBuiltBackendExecutableExists,
  builtBackendExecutablePath,
  waitForHttpHealthcheck,
} from "./built-backend";
import { composeUp, waitForComposeHealthy } from "./compose";
import { backendBaseUrl, isBuiltBackendE2E, isDockerComposeE2E } from "./ports";

// Brings up the app the E2E suite runs against, then waits until it is healthy. Runs once before
// the Playwright run; global-teardown.ts brings it back down. Two backends are supported, selected by
// env var (see ports.ts): a single built executable serving frontend + API, or a docker-compose stack.

const repoRoot = path.resolve(fileURLToPath(new URL("../../../", import.meta.url)));
const dockerComposeFile = path.resolve(repoRoot, "docker-compose.yaml");

function startBuiltBackend(): void {
  assertBuiltBackendExecutableExists();
  const port = new URL(backendBaseUrl()).port;
  console.log(`Starting app at ${builtBackendExecutablePath} ...`);
  const child = spawn(
    builtBackendExecutablePath,
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
    composeUp({ composeFile: dockerComposeFile });
    await waitForComposeHealthy({ composeFile: dockerComposeFile });
  }
}
