import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://127.0.0.1:3102";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const problems = [];

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    problems.push(`pageerror: ${String(error)}`);
  });

  await page.goto(`${baseUrl}/auth/login`, { waitUntil: "networkidle" });
  const body = await page.locator("body").innerText();
  console.log(
    JSON.stringify(
      {
        url: page.url(),
        title: await page.title(),
        bodySnippet: body.slice(0, 1200),
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
