import type { Locator, Page } from "@playwright/test";

export function pushCopyrightYearMask({
  page: _page,
  defaultMasks: _defaultMasks,
}: {
  page: Page;
  defaultMasks: Locator[];
}): void {
  // Repo-specific: push the copyright year locator into defaultMasks, e.g.:
  // defaultMasks.push(page.getByTestId(forComponent({ selector: layout.copyrightYear })));
}

export function pushLogoMask({
  page: _page,
  defaultMasks: _defaultMasks,
}: {
  page: Page;
  defaultMasks: Locator[];
}): void {
  // Repo-specific: push the company logo locator into defaultMasks, e.g.:
  // defaultMasks.push(page.getByTestId(forComponent({ selector: layout.logo })));
}
