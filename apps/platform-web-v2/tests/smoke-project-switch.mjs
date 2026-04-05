import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://127.0.0.1:3103";
const username = process.env.SMOKE_USERNAME || "admin";
const password = process.env.SMOKE_PASSWORD || "admin123456";

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/workspace\//, { timeout: 20_000 }),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);
}

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
    if (response.status() >= 400) {
      problems.push(`http ${response.status()} ${response.url()}`);
    }
  });

  await login(page);
  await page.goto(`${baseUrl}/workspace/overview`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });

  const projectSelect = page.getByLabel("Project").first();
  const projectOptions = await projectSelect
    .locator("option")
    .evaluateAll((options) =>
      options.map((option) => ({
        text: option.textContent?.trim() || "",
        value: option.getAttribute("value") || "",
      })),
    );
  const selectedBefore = await projectSelect.inputValue();

  if (projectOptions.length < 2) {
    console.log(
      JSON.stringify(
        {
          skipped: true,
          reason: "Less than two projects available",
          selectedBefore,
          projectOptions,
          problems,
        },
        null,
        2,
      ),
    );
    await browser.close();
    return;
  }

  const nextProject =
    projectOptions.find(
      (option) => option.value && option.value !== selectedBefore,
    ) || projectOptions[0];
  await projectSelect.selectOption(nextProject.value);
  await page.waitForFunction(
    (expectedProjectId) =>
      new URL(window.location.href).searchParams.get("projectId") ===
      expectedProjectId,
    nextProject.value,
  );
  await page.waitForTimeout(500);

  const projectChip = await page
    .locator(".workspace-shell__chip")
    .nth(2)
    .textContent();
  await page.goto(`${baseUrl}/workspace/assistants`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  const selectedAfter = await page.getByLabel("Project").first().inputValue();
  const roleChip = await page
    .locator(".workspace-shell__chip")
    .nth(3)
    .textContent();

  console.log(
    JSON.stringify(
      {
        skipped: false,
        previousProjectId: selectedBefore,
        nextProject,
        selectedAfter,
        projectChip: projectChip?.trim() || "",
        roleChip: roleChip?.trim() || "",
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
