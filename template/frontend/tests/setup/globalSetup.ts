import { execSync, spawn } from "child_process";
import fs from "fs";
import { createServer } from "net";
import path from "path";
import type { Browser } from "playwright";
import { chromium } from "playwright";
import type { TestProject } from "vitest/node";
import { APP_NAME, DEPLOYED_FRONTEND_PORT_NUMBER } from "~~/tests/setup/constants";

function getRandomOpenPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();

    server.listen(0, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Failed to get port number"));
        return;
      }
      const port = address.port;

      server.close(() => {
        resolve(port);
      });
    });

    server.on("error", (err) => {
      reject(err);
    });
  });
}
const availablePort = await getRandomOpenPort();
const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
const isDockerE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E;
const isBuiltBackendE2E = process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
let browser: Browser;

const executableExtension = process.platform === "win32" ? ".exe" : "";
const repoRoot = path.resolve(__dirname, "../../../");
const executablePath = path.resolve(repoRoot, `./backend/dist/${APP_NAME}/${APP_NAME}${executableExtension}`);
if (isBuiltBackendE2E) {
  if (!fs.existsSync(executablePath) || !fs.statSync(executablePath).isFile()) {
    throw new Error(`File not found: ${executablePath}`);
  }
}
export const BASE_URL = `http://127.0.0.1:${isBuiltBackendE2E ? availablePort : DEPLOYED_FRONTEND_PORT_NUMBER}`;
const healthCheckUrl = `http://127.0.0.1:${
  isBuiltBackendE2E ? availablePort.toString() + "/api/healthcheck" : DEPLOYED_FRONTEND_PORT_NUMBER
}`; // TODO: if there is a backend, check that too, even if it's a docker-compose situation

export async function setup(project: TestProject) {
  project.provide("baseUrl", BASE_URL);
  if (isE2E) {
    if (isBuiltBackendE2E) {
      console.log(`Starting app at ${executablePath} ...`);
      const child = spawn(
        executablePath,
        [
          "--host",
          "0.0.0.0", // TODO: could this just be 127.0.0.1 ?
          // in CI, sometimes the planned port to deploy on is already in use, so we use a random open port
          "--port",
          availablePort.toString(),
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
    if (isDockerE2E) {
      console.log("Starting docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml up --detach --force-recreate --renew-anon-volumes", {
        stdio: "inherit",
      });
    }
    browser = await chromium.launch(); // headless by default
    // Wait for /api/healthcheck to become available
    const maxAttempts = 10;
    let attempts = 0;
    while (attempts < maxAttempts) {
      try {
        const res = await fetch(healthCheckUrl);
        if (res.ok) {
          break;
        }
      } catch {
        // ignore errors // TODO: make this more specific (e.g., only ignore network errors)
      }
      attempts++;
      console.log(`Waiting for ${healthCheckUrl} to become available... Attempt ${attempts}`);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (attempts === maxAttempts) {
      throw new Error(`Timeout waiting for ${healthCheckUrl}`);
    }
  }
}

function hasErrorCode(cause: unknown): cause is { code: string } {
  return typeof cause === "object" && cause !== null && "code" in cause && typeof cause.code === "string";
}

export async function teardown() {
  if (isE2E) {
    await browser.close();
    if (isBuiltBackendE2E) {
      console.log("Stopping application...");
      try {
        const res = await fetch(`${BASE_URL}/api/shutdown`, {
          signal: AbortSignal.timeout(10000), // 10 second timeout
        });
        if (!res.ok) {
          throw new Error(`Failed to stop the application: ${res.statusText}`);
        }
        // Wait a bit for graceful shutdown
        await new Promise((resolve) => setTimeout(resolve, 1000));
      } catch (error) {
        // ECONNRESET is expected when the server shuts down during the request. This happens in Windows CI frequently
        if (error instanceof Error && "cause" in error && hasErrorCode(error.cause)) {
          if (
            error.cause.code === "ECONNRESET" ||
            error.cause.code === "ENOTFOUND" ||
            error.cause.code === "UND_ERR_SOCKET"
          ) {
            console.log("Application shutdown successfully (connection closed)");
            return;
          }
        }

        const logFilePath = path.resolve(repoRoot, `./frontend/logs/${APP_NAME}-backend.log`);
        // sometimes it takes a second for the log file to be fully written to disk
        await new Promise((resolve) => setTimeout(resolve, 1000));
        if (!fs.existsSync(logFilePath) || !fs.statSync(logFilePath).isFile()) {
          throw new Error(`Log file not found: ${logFilePath}`, { cause: error });
        }
        const logData = fs.readFileSync(logFilePath, "utf-8");
        console.log("Application logs:\n", logData);
        throw error;
      }
    }
    if (isDockerE2E) {
      console.log("Stopping docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml down", { stdio: "inherit" });
    }
  }
}

declare module "vitest" {
  export interface ProvidedContext {
    baseUrl: string;
  }
}
