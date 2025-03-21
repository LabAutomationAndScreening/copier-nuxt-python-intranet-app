import { test, expect, describe, beforeAll, afterAll } from "vitest";
import { setup, $fetch, createPage, url } from "@nuxt/test-utils/e2e";
import { execSync } from "child_process";
describe("Index page", async () => {
  describe("regular nuxt build", async () => {
    await setup();
    describe("Static tests of rendered page", async () => {
      test("component renders Hello world properly", async () => {
        const html = await $fetch("/");
        expect(html).toContain("Hello World");
      });
    });
    describe("Full Browser tests", async () => {
      // TODO: figure out away to display the chromium version so it will show up in logs
      test("component renders Hello world properly", async () => {
        const page = await createPage();
        await page.goto(url("/"), { waitUntil: "hydration" });
        const text = await page.textContent("div");

        expect(text).toContain("Hello World");
      });
    });
  });
  describe("docker build", async () => {
    beforeAll(async () => {
      console.log("Starting docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml up --detach --force-recreate --renew-anon-volumes", {
        stdio: "inherit",
      });
      await setup({ host: "http://localhost:3000" });
    }, 240 * 1000); // increase timeout in case image needs to be built
    afterAll(() => {
      console.log("Stopping docker-compose...");
      execSync("docker compose --file=../docker-compose.yaml down", { stdio: "inherit" });
    });

    describe("Full Browser tests", async () => {
      // TODO: figure out away to display the chromium version so it will show up in logs
      test("component renders Hello world properly", async () => {
        const page = await createPage();
        await page.goto(url("/"), { waitUntil: "hydration" });
        const text = await page.textContent("div");

        expect(text).toContain("Hello World");
      });
    });
  });
});
