import { test, expect, describe, beforeAll, afterAll } from "vitest";
import { setup, createPage, url } from "@nuxt/test-utils/e2e";
import { execSync } from "child_process";

describe("Index page", async () => {
  if (!process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E) {
    // the `setup()` function doesn't seem to work well when trying to run tests in the same suite with different hosts, so using an envvar to run the tests either with docker-compose or without
    await setup();
  }
  beforeAll(async () => {
    if (process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E) {
      console.log("Starting docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml up --detach --force-recreate --renew-anon-volumes", {
        stdio: "inherit",
      });
      await setup({ host: "http://localhost:3000" });
    }
  }, 40 * 1000); // increase timeout to allow docker compose to start
  afterAll(() => {
    if (process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E) {
      console.log("Stopping docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml down", { stdio: "inherit" });
    }
  });
  test("Page displays Hello World", async () => {
    const page = await createPage();
    await page.goto(url("/"), { waitUntil: "hydration" });
    const text = await page.textContent("div");

    expect(text).toContain("Hello World");
  });
});
