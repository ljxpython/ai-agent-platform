import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://127.0.0.1:3102";
const username = process.env.SMOKE_USERNAME || "admin";
const password = process.env.SMOKE_PASSWORD || "admin123456";
const prompt = process.env.SMOKE_PROMPT || "hello";
const failurePatterns = [
  /failed to (load|send|fetch)/i,
  /something went wrong/i,
  /unauthorized/i,
  /forbidden/i,
  /access denied/i,
];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const problems = [];

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`console:${message.type()} ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    problems.push(`pageerror ${String(error)}`);
  });
  page.on("response", (response) => {
    const url = response.url();
    const status = response.status();
    if (
      (url.includes("/api/") || url.includes("/_management/")) &&
      status >= 400
    ) {
      problems.push(`http ${status} ${url}`);
    }
  });

  await page.goto(`${baseUrl}/auth/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/workspace\//, { timeout: 20_000 }),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  await page.goto(`${baseUrl}/workspace/sql-agent`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  const input = page.getByPlaceholder("Type your message...");
  await input.fill(prompt);
  await input.press("Enter");
  await page.waitForTimeout(12_000);

  const body = await page.locator("body").innerText();
  console.log(
    JSON.stringify(
      {
        url: page.url(),
        hasPrompt: body.includes(prompt),
        hasFailureSignal: failurePatterns.some((pattern) => pattern.test(body)),
        bodySnippet: body.slice(0, 2_500),
        problems,
      },
      null,
      2,
    ),
  );

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
