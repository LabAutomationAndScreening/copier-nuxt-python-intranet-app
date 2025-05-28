import { createPage, setup, url } from "@nuxt/test-utils/e2e";
import { describe, expect, test } from "vitest";

describe("Index page", async () => {
  await setup();
  test("Page displays Hello World", async () => {
    expect.assertions(1);
    const page = await createPage();

    await page.goto(url("/"), { waitUntil: "hydration" });

    const text = await page.textContent("div");

    expect(text).toContain("Hello World");
  });
});
