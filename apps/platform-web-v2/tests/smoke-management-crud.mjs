import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://127.0.0.1:3103";
const username = process.env.SMOKE_USERNAME || "admin";
const password = process.env.SMOKE_PASSWORD || "admin123456";
const uniqueId = Date.now().toString(36);
const newUsername = process.env.SMOKE_NEW_USERNAME || `smoke_${uniqueId}`;
const newPassword = process.env.SMOKE_NEW_PASSWORD || `SmokeUser_${uniqueId}`;

async function login(page, account, accountPassword) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Username").fill(account);
  await page.getByLabel("Password").fill(accountPassword);
  await Promise.all([
    page.waitForURL(/\/workspace\//, { timeout: 20_000 }),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const problems = [];

  adminPage.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`console:${message.type()} ${message.text()}`);
    }
  });
  adminPage.on("pageerror", (error) => {
    problems.push(`pageerror ${String(error)}`);
  });
  adminPage.on("response", (response) => {
    const url = response.url();
    if (
      (url.startsWith(baseUrl) || url.includes(":2024/")) &&
      response.status() >= 400
    ) {
      problems.push(`http ${response.status()} ${url}`);
    }
  });

  await login(adminPage, username, password);

  await adminPage.goto(`${baseUrl}/workspace/users/new`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  await adminPage.getByLabel("Username").fill(newUsername);
  await adminPage.getByLabel("Password").fill(newPassword);
  await Promise.all([
    adminPage.waitForURL(/\/workspace\/users\/[0-9a-f-]{36}$/i, {
      timeout: 20_000,
    }),
    adminPage.getByRole("button", { name: "Create user" }).click(),
  ]);

  const userUrl = adminPage.url();
  const userIdMatch = userUrl.match(/\/workspace\/users\/([^/?]+)/);
  const userId = userIdMatch?.[1] || "";

  await adminPage.getByRole("button", { name: "Disable user" }).click();
  await adminPage.getByText("User disabled").waitFor({ timeout: 10_000 });
  await adminPage.getByRole("button", { name: "Enable user" }).click();
  await adminPage.getByText("User enabled").waitFor({ timeout: 10_000 });

  await adminPage.goto(`${baseUrl}/workspace/overview`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  const projectSelect = adminPage.getByLabel("Project").first();
  const projectId = await projectSelect.inputValue();
  const projectName = await projectSelect
    .locator("option:checked")
    .textContent();

  await adminPage.goto(`${baseUrl}/workspace/projects/${projectId}/members`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  await adminPage
    .getByLabel("Search active user by username")
    .fill(newUsername);
  await adminPage
    .getByRole("button", { name: new RegExp(newUsername) })
    .first()
    .click();
  await adminPage.getByLabel("Role").selectOption("executor");
  await adminPage.getByRole("button", { name: "Add member" }).click();
  await adminPage
    .getByText(`Saved member: ${newUsername}`)
    .waitFor({ timeout: 10_000 });

  const memberVisible = await adminPage
    .locator("table")
    .getByText(newUsername)
    .first()
    .isVisible();

  const userContext = await browser.newContext();
  const userPage = await userContext.newPage();
  const userProblems = [];
  userPage.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      userProblems.push(`console:${message.type()} ${message.text()}`);
    }
  });
  userPage.on("pageerror", (error) => {
    userProblems.push(`pageerror ${String(error)}`);
  });
  userPage.on("response", (response) => {
    const url = response.url();
    if (
      (url.startsWith(baseUrl) || url.includes(":2024/")) &&
      response.status() >= 400
    ) {
      userProblems.push(`http ${response.status()} ${url}`);
    }
  });

  await login(userPage, newUsername, newPassword);
  await userPage.goto(`${baseUrl}/workspace/overview`, {
    waitUntil: "networkidle",
    timeout: 30_000,
  });
  const userOverviewTitle = await userPage
    .getByRole("heading", { name: "Overview" })
    .textContent();
  const userRoleChip = await userPage
    .locator(".workspace-shell__chip")
    .nth(3)
    .textContent();

  console.log(
    JSON.stringify(
      {
        newUsername,
        userId,
        projectId,
        projectName: projectName?.trim() || "",
        memberVisible,
        userOverviewTitle: userOverviewTitle?.trim() || "",
        userRoleChip: userRoleChip?.trim() || "",
        problems,
        userProblems,
      },
      null,
      2,
    ),
  );

  await userContext.close();
  await adminContext.close();
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
