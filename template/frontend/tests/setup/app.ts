import { execSync, spawn } from "child_process";
import fs from "fs";
import path from "path";
import type { Browser, Page } from "playwright";
import { chromium } from "playwright";
import { afterAll, beforeAll } from "vitest";

import { APP_NAME, DEPLOYED_BACKEND_PORT_NUMBER, DEPLOYED_FRONTEND_PORT_NUMBER } from "~/tests/setup/constants";

const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
const isDockerE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E;
const isBuiltBackendE2E = process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
let browser: Browser;
let page: Page;
const executableExtension = process.platform === "win32" ? ".exe" : "";
const executablePath = path.resolve(__dirname, `../../../backend/dist/${APP_NAME}/${APP_NAME}${executableExtension}`);
if (isBuiltBackendE2E) {
  if (!fs.existsSync(executablePath)) {
    throw new Error(`File not found: ${executablePath}`);
  }
}
export const BASE_URL = `http://localhost:${
  isBuiltBackendE2E ? DEPLOYED_BACKEND_PORT_NUMBER : DEPLOYED_FRONTEND_PORT_NUMBER
}`;
export function url(path: string): string {
  if (!path.startsWith("/")) {
    path = `/${path}`;
  }
  return `${BASE_URL}${path}`;
}
const healthCheckUrl = `http://localhost:${
  isBuiltBackendE2E ? DEPLOYED_BACKEND_PORT_NUMBER.toString() + "/api/healthcheck" : DEPLOYED_FRONTEND_PORT_NUMBER
}`; // TODO: if there is a backend, check that too, even if it's a docker-compose situation
if (isE2E) {
  beforeAll(async () => {
    if (isBuiltBackendE2E) {
      console.log(`Starting app at ${executablePath} ...`);
      const child = spawn(executablePath, [], {
        stdio: "inherit",
      });
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
    page = await browser.newPage();
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
  }, 40 * 1000); // increase timeout to allow application to start

  afterAll(async () => {
    if (isBuiltBackendE2E) {
      await browser.close();
      console.log("Stopping application...");
      const res = await fetch(`${BASE_URL}/api/shutdown`);
      if (!res.ok) {
        throw new Error(`Failed to stop the application: ${res.statusText}`);
      }
    }
    if (isDockerE2E) {
      console.log("Stopping docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml down", { stdio: "inherit" });
    }
  }, 40 * 1000); // increase timeout to allow application to stop
}

export function getPage(): Page {
  if (!page) {
    throw new Error("Page is not initialized. Make sure to run the tests in E2E mode.");
  }
  return page;
}
