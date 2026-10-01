import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Cross-platform postinstall script since E2E tests need to execute in Windows CI too, and the postinstall logic was getting complicated
const rootDir = fileURLToPath(new URL("..", import.meta.url));
const useShell = process.platform === "win32";

// Off CI the browsers are always installed, so a fresh devcontainer can run the E2E tests. On CI a job opts in
// with INSTALL_PLAYWRIGHT=1, because pnpm reruns this before every script and most jobs never open a browser;
// a job that needs one and forgets fails loudly when Playwright finds no browser to launch.
// SKIP_PLAYWRIGHT_INSTALL=1 skips it anywhere, such as a Docker build, where CI is not set.
const shouldInstallPlaywright = () => {
  if (process.env.SKIP_PLAYWRIGHT_INSTALL === "1") {
    return false;
  }
  if (process.env.CI === "true") {
    return process.env.INSTALL_PLAYWRIGHT === "1";
  }
  return true;
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

if (shouldInstallPlaywright()) {
  run("exec", "playwright-core", "install", "--with-deps", "chromium");
}
