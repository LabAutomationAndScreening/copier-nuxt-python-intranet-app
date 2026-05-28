import { faker } from "@faker-js/faker";
import { AnonymousAuthenticationProvider } from "@microsoft/kiota-abstractions";
import { FetchRequestAdapter } from "@microsoft/kiota-http-fetchlibrary";
import { test as base } from "@playwright/test";

import { type BackendClient, createBackendClient } from "~/generated/open-api/backend/backendClient";
import { backendBaseUrl } from "./ports";

// Mirrors tests/setup/faker.ts (used by the vitest unit/compiled projects). Seed once per worker so a
// failing run can be reproduced with TEST_FAKER_SEED=<logged value>. Playwright runs files in a stable
// order (no vitest-style shuffle), so seed + order reproduce the sequence.
const fakerSeed = Number(process.env.TEST_FAKER_SEED) || Math.floor(Math.random() * 1e9);

// Build the kiota client directly (rather than via nuxt-common's useKiotaClient) with an explicit
// baseUrl — keeps this test harness free of a nuxt-common dependency. This is the same adapter
// useKiotaClient constructs internally.
function buildBackendClient(): BackendClient {
  const adapter = new FetchRequestAdapter(new AnonymousAuthenticationProvider());
  adapter.baseUrl = backendBaseUrl();
  return createBackendClient(adapter);
}

// eslint-disable-next-line @typescript-eslint/no-invalid-void-type -- `void` is Playwright's idiom for a worker fixture that provides no value (auto-run side effect only)
export const test = base.extend<{ backendClient: BackendClient }, { seedFaker: void }>({
  seedFaker: [
    // eslint-disable-next-line no-empty-pattern -- Playwright requires the first fixture arg to be object-destructured; `{}` is the zero-dependency form
    async ({}, use) => {
      console.log("[seed passed to faker]", fakerSeed);
      faker.seed(fakerSeed);
      await use();
    },
    { scope: "worker", auto: true },
  ],
  // The kiota client is built directly (FetchRequestAdapter + AnonymousAuthenticationProvider with an
  // explicit baseUrl) rather than via nuxt-common's useBackendClient, to keep nuxt-common not as a required dependency (for now).
  // eslint-disable-next-line no-empty-pattern -- Playwright requires the first fixture arg to be object-destructured; `{}` is the zero-dependency form
  backendClient: async ({}, use) => {
    await use(buildBackendClient());
  },
});

// Use this in *.vrt.spec.ts files (anything calling toHaveScreenshot). It inherits backendClient and
// auto-skips on Windows, where we have no easy way to record platform-matching baselines. Behavioral
// specs keep using `test` so they still run on Windows. The skip is wired as an auto-fixture (rather
// than `vrtTest.skip()` inside a beforeEach) so the running test's TestInfo is threaded in explicitly —
// the static `test.skip(cond, msg)` form was a no-op for tests defined on an extended test instance.
// eslint-disable-next-line @typescript-eslint/no-invalid-void-type -- `void` is Playwright's idiom for an auto-run fixture that provides no value
export const vrtTest = test.extend<{ skipOnWindows: void }>({
  skipOnWindows: [
    // eslint-disable-next-line no-empty-pattern -- Playwright requires the first fixture arg to be object-destructured; `{}` is the zero-dependency form
    async ({}, use, testInfo) => {
      testInfo.skip(process.platform === "win32", "VRT baselines are generated on Linux only");
      await use();
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
