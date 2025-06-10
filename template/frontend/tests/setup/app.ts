import fs from "fs";
import path from "path";
import type { Browser, Page } from "playwright";
import { chromium } from "playwright";
import { afterAll, beforeAll, beforeEach } from "vitest";

import { APP_NAME, DEPLOYED_BACKEND_PORT_NUMBER, DEPLOYED_FRONTEND_PORT_NUMBER } from "~/tests/setup/constants";

const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;

const isBuiltBackendE2E = process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
let browser: Browser;
let page: Page;
const executableExtension = process.platform === "win32" ? ".exe" : "";
const repoRoot = path.resolve(__dirname, "../../../");
const executablePath = path.resolve(repoRoot, `./backend/dist/${APP_NAME}/${APP_NAME}${executableExtension}`);
if (isBuiltBackendE2E) {
  if (!fs.existsSync(executablePath) || !fs.statSync(executablePath).isFile()) {
    throw new Error(`File not found: ${executablePath}`);
  }
}
export const BASE_URL = `http://127.0.0.1:${
  isBuiltBackendE2E ? DEPLOYED_BACKEND_PORT_NUMBER : DEPLOYED_FRONTEND_PORT_NUMBER
}`;

if (isE2E) {
  beforeAll(async () => {
    browser = await chromium.launch(); // headless by default
  }, 40 * 1000); // increase timeout to allow application to start
  beforeEach(async () => {
    page = await browser.newPage();
  });
  afterAll(async () => {
    await browser.close();
  }, 40 * 1000); // increase timeout to allow application to stop
}

export function getPage(): Page {
  if (!page) {
    throw new Error("Page is not initialized. Make sure to run the tests in E2E mode.");
  }
  return page;
}
