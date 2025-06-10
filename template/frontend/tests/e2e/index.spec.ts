import { describe, expect, test } from "vitest";
import { url } from "~/tests/e2e/helpers/playwright";
import { getPage } from "~/tests/setup/app";

describe("Index page", async () => {
  test("Page displays Hello World", async () => {
    expect.assertions(1);
    const page = getPage();
    await page.goto(url("/"));

    const text = await page.textContent("div");

    expect(text).toContain("Hello World");
  });
});
