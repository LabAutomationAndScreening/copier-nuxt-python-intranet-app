import type { Browser, Page } from "playwright";
import { chromium } from "playwright";
import { afterAll, beforeAll, beforeEach } from "vitest";

const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
let browser: Browser;
let page: Page;

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
