import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://127.0.0.1:3102";
const username = process.env.SMOKE_USERNAME || "admin";
const password = process.env.SMOKE_PASSWORD || "admin123456";

const routes = [
  "/workspace/overview",
  "/workspace/me",
  "/workspace/security",
  "/workspace/assistants",
  "/workspace/chat",
  "/workspace/sql-agent",
  "/workspace/threads",
  "/workspace/testcase/generate",
  "/workspace/testcase/cases",
  "/workspace/testcase/documents",
  "/workspace/audit",
];

function isIgnorableHttpError(url) {
  return url.includes("/favicon.ico");
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const problems = [];
  page.on("pageerror", (error) => {
    problems.push({ type: "pageerror", message: String(error) });
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push({
        type: `console:${message.type()}`,
        message: message.text(),
      });
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    const status = response.status();
    if (
      status >= 400 &&
      url.startsWith(baseUrl) &&
      !isIgnorableHttpError(url)
    ) {
      problems.push({ type: "http", message: `${status} ${url}` });
    }
  });

  await page.goto(`${baseUrl}/auth/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/workspace\//, { timeout: 20_000 }),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  const results = [];
  for (const route of routes) {
    try {
      await page.goto(`${baseUrl}${route}`, {
        waitUntil: "networkidle",
        timeout: 30_000,
      });
      await page.waitForTimeout(1_000);
      const title = await page
        .locator("h1, h2")
        .first()
        .textContent()
        .catch(() => "");
      results.push({ route, ok: true, title: title?.trim() || "" });
    } catch (error) {
      results.push({
        route,
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  console.log(JSON.stringify({ results, problems }, null, 2));
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
