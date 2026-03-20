import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Cross-platform postinstall script since E2E tests need to execute in Windows CI too, and the postinstall logic was getting complicated
const rootDir = fileURLToPath(new URL("..", import.meta.url));
const pnpmCommand = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const shouldInstallPlaywright = process.platform === "win32" || process.env.SKIP_PLAYWRIGHT_INSTALL !== "1";

const run = (...args) => {
  execFileSync(pnpmCommand, args, {
    cwd: rootDir,
    env: process.env,
    stdio: "inherit",
  });
};

run("exec", "nuxt", "prepare");

if (shouldInstallPlaywright) {
  run("exec", "playwright-core", "install", "--with-deps", "--only-shell", "chromium-headless-shell");
}
