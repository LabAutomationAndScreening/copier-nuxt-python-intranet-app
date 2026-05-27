import { expect, type Locator, type Page } from "@playwright/test";

type ColorScheme = "light" | "dark";

// Full-page visual snapshot taken in both light and dark mode by default. The app's color mode keys
// off prefers-color-scheme (@nuxtjs/color-mode preference defaults to "system"), so emulateMedia
// drives it programmatically — no UI toggle needed. Each scheme writes its own baseline (the scheme
// is appended to the filename). Override `colorSchemes` (e.g. ["light"]) to limit it.
//
// The footer year (`new Date().getFullYear()`) and the logo are masked by default. Playwright masks
// are z-unaware — they paint a flat rect at the element's bounding box over the final image — so
// anything stacked above (e.g. a slideover/popover over the logo) gets covered; pass
// `maskLogo: false` / `maskFooterYear: false` for those tests. Pass `mask` to add further regions.
export async function expectFullPageScreenshot(
  page: Page,
  name: string,
  {
    mask = [],
    maskLogo = true,
    maskFooterYear = true,
    colorSchemes = ["light", "dark"],
  }: { mask?: Locator[]; maskLogo?: boolean; maskFooterYear?: boolean; colorSchemes?: ColorScheme[] } = {},
): Promise<void> {
  for (const colorScheme of colorSchemes) {
    await page.emulateMedia({ colorScheme });
    await expectFullPageScreenshotInCurrentColorMode(page, name.replace(/\.png$/, `-${colorScheme}.png`), {
      mask,
      maskLogo,
      maskFooterYear,
    });
  }
}

// A single full-page snapshot in whatever color mode is currently active — does not touch
// emulateMedia. Use this when the color mode is driven another way (e.g. clicking the color-mode
// switch), so the snapshot reflects that state rather than a re-emulated one.
export async function expectFullPageScreenshotInCurrentColorMode(
  page: Page,
  name: string,
  {
    mask = [],
    maskLogo = true,
    maskFooterYear = true,
  }: { mask?: Locator[]; maskLogo?: boolean; maskFooterYear?: boolean } = {},
): Promise<void> {
  const defaultMasks: Locator[] = [];
  if (maskFooterYear) {
    // Repo needs to implement its own masking of the footer year. Example below:
    // defaultMasks.push(page.getByTestId(forComponent({ selector: layout.footerYear })));
  }
  if (maskLogo) {
    // Repo needs to implement its own masking of the company logo on the page. Example below:
    // defaultMasks.push(page.getByTestId(forComponent({ selector: layout.logo })));
  }
  await expect(page).toHaveScreenshot(name, {
    fullPage: true,
    mask: [...defaultMasks, ...mask],
  });
}
