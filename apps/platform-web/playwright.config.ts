import { defineConfig, devices } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, realpathSync } from "node:fs";
import { resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";

const root = realpathSync(resolve(import.meta.dirname, "../.."));
const gitPath = (...args: string[]) =>
  realpathSync(
    execFileSync("git", ["-C", root, "rev-parse", ...args], {
      encoding: "utf8",
    }).trim(),
  );
const commonDirectory = gitPath("--path-format=absolute", "--git-common-dir");
const linkedWorktree = commonDirectory !== gitPath("--absolute-git-dir");
let baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
let proxyTarget = process.env.VITE_DEV_PROXY_TARGET ?? "http://127.0.0.1:2142";
if (linkedWorktree) {
  // shortcut: legacy runners share /tmp fixtures; migrate their inputs before enabling in Worktrees.
  for (const flag of [
    "RUN_ERROR_CONTRACT_E2E",
    "RUN_SSE_CONTRACT_E2E",
    "RUN_LOCAL_GOVERNANCE_E2E",
  ]) {
    if (process.env[flag] === "1")
      throw new Error(
        `${flag} uses a shared legacy fixture; use a Worktree-scoped runner`,
      );
  }
  const path = resolve(root, ".local-stack/environment.json");
  if (!existsSync(path))
    throw new Error(
      "Initialize this Worktree with scripts/local-stack.sh init before E2E tests",
    );
  const environment = JSON.parse(readFileSync(path, "utf8"));
  const registry = JSON.parse(
    readFileSync(
      resolve(commonDirectory, "local-stacks/registry.json"),
      "utf8",
    ),
  );
  const ports = environment.ports;
  if (
    !isDeepStrictEqual(registry.environments?.[root], environment) ||
    environment.root !== root ||
    !/^wt_[0-9a-f]{12}$/.test(environment.id) ||
    ![ports?.PLATFORM_WEB_PORT, ports?.PLATFORM_API_PORT].every(
      (port) => Number.isInteger(port) && port >= 23000 && port < 30000,
    )
  ) {
    throw new Error("Invalid Worktree E2E environment");
  }
  const registeredURL = `http://127.0.0.1:${ports.PLATFORM_WEB_PORT}`;
  if (process.env.PLAYWRIGHT_BASE_URL && baseURL !== registeredURL)
    throw new Error("E2E URL must match this Worktree environment");
  baseURL = registeredURL;
  proxyTarget = `http://127.0.0.1:${ports.PLATFORM_API_PORT}`;
  if (
    process.env.PLATFORM_TEST_URL &&
    process.env.PLATFORM_TEST_URL !== proxyTarget
  )
    throw new Error("Test API URL must match this Worktree environment");
  process.env.PLATFORM_TEST_URL = proxyTarget;
  process.env.PLATFORM_TEST_ENV_FILE = resolve(
    root,
    ".local-stack/platform.env",
  );
  process.env.RUNTIME_TEST_ENV_FILE = resolve(root, ".local-stack/runtime.env");
}
const webPort = new URL(baseURL).port || "80";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: {
    command: `pnpm exec vite --port ${webPort} --host 127.0.0.1`,
    url: baseURL,
    env: { VITE_PLATFORM_API_URL: "/", VITE_DEV_PROXY_TARGET: proxyTarget },
    reuseExistingServer: true,
    timeout: 60 * 1000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
