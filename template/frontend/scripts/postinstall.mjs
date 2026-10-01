import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Cross-platform postinstall script since E2E tests need to execute in Windows CI too, and the postinstall logic was getting complicated
const rootDir = fileURLToPath(new URL("..", import.meta.url));
const useShell = process.platform === "win32";

// INSTALL_PLAYWRIGHT_BROWSERS=1/true installs Playwright's browsers and 0/false skips them, anywhere. Left unset,
// they are installed locally, so a fresh devcontainer can run the E2E tests, and skipped in CI, because pnpm reruns
// this before every script and most jobs never open a browser; a CI job that needs one and forgets fails loudly
// when Playwright finds no browser to launch.
const shouldInstallPlaywrightBrowsers = () => {
  const setting = process.env.INSTALL_PLAYWRIGHT_BROWSERS;
  if (setting === undefined) {
    return process.env.CI !== "true";
  }
  if (setting === "") {
    return process.env.CI !== "true";
  }
  if (setting === "1") {
    return true;
  }
  if (setting === "true") {
    return true;
  }
  if (setting === "0") {
    return false;
  }
  if (setting === "false") {
    return false;
  }
  throw new Error(`INSTALL_PLAYWRIGHT_BROWSERS must be 1, true, 0 or false, or left unset, but was "${setting}"`);
};

const run = (...args) => {
  execFileSync("pnpm", args, {
    cwd: rootDir,
    env: process.env,
    shell: useShell,
    stdio: "inherit",
  });
};

run("exec", "nuxt", "prepare");

if (shouldInstallPlaywrightBrowsers()) {
  run("exec", "playwright-core", "install", "--with-deps", "chromium");
}
