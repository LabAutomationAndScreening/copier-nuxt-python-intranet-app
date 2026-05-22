import fs from "node:fs";
import path from "node:path";
import type { Browser, Page } from "playwright";
import { chromium } from "playwright";
import { afterAll, beforeAll, beforeEach, onTestFailed } from "vitest";

const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;
let browser: Browser;
let page: Page;

if (isE2E) {
  beforeAll(async () => {
    browser = await chromium.launch(); // headless by default
  }, 40 * 1000); // increase timeout to allow application to start
  beforeEach(async (ctx) => {
    page = await browser.newPage();

    page.on("console", (msg) => {
      console.log(`[browser:${msg.type()}]`, msg.text());
    });
    page.on("pageerror", (err) => {
      console.error("[browser:pageerror]", err.message);
    });
    page.on("requestfailed", (req) => {
      console.error("[browser:requestfailed]", req.url(), req.failure()?.errorText);
    });

    onTestFailed(async () => {
      const screenshotDir = path.resolve("./test-screenshots");
      fs.mkdirSync(screenshotDir, { recursive: true });
      const safeName = ctx.task.name.replace(/[^\w-]/g, "_");
      const screenshotPath = path.join(screenshotDir, `${safeName}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`[debug] screenshot saved: ${screenshotPath}`);
    });
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
