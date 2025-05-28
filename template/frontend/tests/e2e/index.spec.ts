import { createPage, setup, url } from "@nuxt/test-utils/e2e";
import { execSync } from "child_process";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { DEPLOYED_FRONTEND_PORT_NUMBER } from "~/tests/e2e/constants";

describe("Index page", async () => {
  // we really truly only want to run this once because it takes so long to spin up, so using beforeAll
  // eslint-disable-next-line vitest/no-hooks
  beforeAll(async () => {
    console.log("Starting docker-compose...");
    execSync("docker compose --file=../docker-compose.yaml up --detach --force-recreate --renew-anon-volumes", {
      stdio: "inherit",
    });
    await setup({ host: `http://localhost:${DEPLOYED_FRONTEND_PORT_NUMBER}` });
  }, 40 * 1000); // increase timeout to allow docker compose to start
  // we really truly only want to run this once because it takes so long for the containers to spin up, so using afterAll
  // eslint-disable-next-line vitest/no-hooks
  afterAll(() => {
    console.log("Stopping docker-compose...");
    execSync("docker compose --file=../docker-compose.yaml down", { stdio: "inherit" });
  });
  test("Page displays Hello World", async () => {
    expect.assertions(1);
    const page = await createPage();

    await page.goto(url("/"), { waitUntil: "hydration" });

    const text = await page.textContent("div");

    expect(text).toContain("Hello World");
  });
});
