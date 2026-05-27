import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

import { ensureBuiltBackendPort, frontendBaseUrl } from "./tests/e2e/ports";

const e2eDir = fileURLToPath(new URL("./tests/e2e", import.meta.url));

// The built-backend executable serves frontend + API on one randomly-chosen port. Resolve it here, in
// the main process, before referencing frontendBaseUrl() — worker processes inherit the env and re-read
// the same value. No-op in docker-compose mode (fixed ports).
await ensureBuiltBackendPort();

// The E2E runner: behavioral specs (*.spec.ts) and visual-regression specs (*.vrt.spec.ts) run here
// against the docker-compose stack brought up by globalSetup. Playwright (not Vitest) gives web-first
// auto-retrying assertions, toHaveScreenshot baselines + masking, retries, traces, and reports.
export default defineConfig({
  testDir: e2eDir,
  // Baselines are committed. The {platform} token means a baseline recorded on linux CI will not
  // silently match a developer's macOS run — font hinting/antialiasing differ per OS, so a mismatch
  // there is surfaced rather than hidden. Regenerate per-platform with `--update-snapshots`.
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}-{platform}{ext}",
  fullyParallel: false, // shared docker-compose backend state across specs
  forbidOnly: process.env.CI === "true",
  retries: process.env.CI === "true" ? 1 : 0,
  workers: 1,
  reporter: process.env.CI === "true" ? [["html", { open: "never" }], ["list"]] : [["list"]],
  globalSetup: fileURLToPath(new URL("./tests/e2e/global-setup.ts", import.meta.url)),
  globalTeardown: fileURLToPath(new URL("./tests/e2e/global-teardown.ts", import.meta.url)),
  use: {
    baseURL: frontendBaseUrl(),
    trace: "retain-on-failure",
  },
  expect: {
    toHaveScreenshot: {
      // disable CSS animations/transitions and hide the text caret so neither introduces per-run noise
      animations: "disabled",
      caret: "hide",
      // tolerate sub-pixel antialiasing differences without masking real regressions
      maxDiffPixelRatio: 0.01,
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
