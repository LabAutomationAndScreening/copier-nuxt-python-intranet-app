import { expect, test } from "~~/tests/e2e/fixtures";

test.describe("Index page", () => {
  test("Page displays Hello World", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Hello World")).toBeVisible();
  });
});
