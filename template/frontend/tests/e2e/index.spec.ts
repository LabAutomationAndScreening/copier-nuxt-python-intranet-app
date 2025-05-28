import { describe, expect, test } from "vitest";
import { getPage, url } from "~/tests/setup/app";

describe("Index page", async () => {
  test("Page displays Hello World", async () => {
    expect.assertions(1);
    const page = getPage();
    await page.goto(url("/"));

    const text = await page.textContent("div");

    expect(text).toContain("Hello World");
  });
});
