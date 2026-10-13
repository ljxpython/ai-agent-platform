import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { platformUrl, testCredentials } from "./support/platform";

test("公网沙箱已有会话的 Office、HTML 与后台回执恢复", async ({ page }) => {
  test.skip(
    process.env.RUN_SANDBOX_RECOVERY_E2E !== "1",
    "Requires owned public fixtures",
  );
  test.setTimeout(300000);
  const root = resolve(import.meta.dirname, "../../../");
  const chain = JSON.parse(
    await readFile(
      resolve(
        root,
        "docs/projects/20261012-runtime-remote-docker-sandbox/evidence/public-platform.json",
      ),
      "utf8",
    ),
  );
  const directory = resolve(
    root,
    "docs/projects/20261012-runtime-remote-docker-sandbox/evidence/public-browser-recovery",
  );
  await mkdir(directory, { recursive: true });
  const login = await fetch(`${platformUrl}/api/identity/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(testCredentials()),
  });
  expect(login.status).toBe(200);
  const { tokens } = await login.json();
  const errors: string[] = [];
  const checks: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.addInitScript((tokens) => {
    if (window !== window.top) return;
    localStorage.setItem(
      "pw:auth:token-set",
      JSON.stringify({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        tokenType: tokens.token_type,
      }),
    );
  }, tokens);
  for (const fixture of chain.fixture_threads) {
    await page.goto(
      `/workspace/projects/${fixture.project_id}/chat/${fixture.thread_id}?agentId=${fixture.agent_id}`,
    );
    await expect(page.getByTestId("transcript").first()).toContainText(
      chain.marker,
      { timeout: 60000 },
    );
    const doc = page
      .locator(".pw-tool-call")
      .filter({ hasText: "解析文档" })
      .first();
    if (!(await doc.isVisible()))
      await page
        .locator("summary")
        .filter({ hasText: "执行步骤与工具调用" })
        .first()
        .click();
    await expect(doc).toBeVisible({ timeout: 60000 });
    await doc.locator("button").first().click();
    await expect(doc).toContainText(/docx|pptx/i, { timeout: 30000 });
    await expect(doc).toContainText(chain.marker);
    checks.push(`${fixture.graph}-office-history`);
    await page.screenshot({
      path: resolve(directory, `${fixture.graph}-office.png`),
      fullPage: true,
    });
    if (fixture.graph === "dearflow_agent") {
      // Leaving the page does not stop a completed task or lose its original receipt.
      await page.goto(
        `/workspace/projects/${fixture.project_id}/dear-agent-artifacts?threadId=${fixture.thread_id}`,
      );
      await page.goto(
        `/workspace/projects/${fixture.project_id}/chat/${fixture.thread_id}?agentId=${fixture.agent_id}`,
      );
      await page.getByTestId("toggle-workspace-button").click();
      await page.getByTestId("workspace-tab-tasks").click();
      const background = chain.results.find(
        (row: { name: string }) =>
          row.name === "public-worker-background-completion",
      ).facts;
      const headers = {
        Authorization: `Bearer ${tokens.access_token}`,
        "X-Project-ID": fixture.project_id,
      };
      const restored = await fetch(
        `${platformUrl}/api/langgraph/threads/${fixture.thread_id}/background-tasks/${background.task_id}`,
        { headers },
      );
      expect(restored.status).toBe(200);
      const receipt = await restored.json();
      expect(receipt.delivery.run_id).toBe(background.delivery_run_id);
      expect(receipt.cleanup_state).toBe("confirmed");
      expect(receipt.status).toBe("succeeded");
      // The later Thread Stop suppresses notification; the original accepted Run remains.
      expect(receipt.delivery.state).toBe("suppressed");
      const originalRun = await fetch(
        `${platformUrl}/api/langgraph/threads/${fixture.thread_id}/runs/${background.delivery_run_id}`,
        { headers },
      );
      expect(originalRun.status).toBe(200);
      expect((await originalRun.json()).status).toBe("success");
      const task = page
        .getByTestId("background-task-item")
        .filter({ hasText: background.task_id.slice(0, 8) })
        .first();
      await expect(task).toBeVisible({ timeout: 60000 });
      await expect(task.getByTestId("delivery-suppressed-badge")).toBeVisible();
      await task.getByTestId("task-view-logs-btn").click();
      await expect(
        page.getByText(chain.marker, { exact: true }).last(),
      ).toBeVisible({ timeout: 30000 });
      await page.screenshot({
        path: resolve(directory, "background-receipt-log.png"),
        fullPage: true,
      });
      checks.push(
        "background-original-accepted-run-suppressed-notification-log-after-leave",
      );
    }
    const facts = chain.results.find(
      (row: { name: string }) =>
        row.name ===
        `${fixture.graph}-real-model-office-image-skills-child-artifacts`,
    ).facts;
    const artifact = facts.artifacts.find(
      (row: { mime_type: string }) => row.mime_type === "text/html",
    );
    let openPreview: () => Promise<void>;
    let downloadArtifact: () => Promise<void>;
    if (fixture.graph === "dearflow_agent") {
      await page.goto(
        `/workspace/projects/${fixture.project_id}/dear-agent-artifacts?threadId=${fixture.thread_id}`,
      );
      const card = page
        .locator("article")
        .filter({ hasText: artifact.file_name })
        .first();
      await expect(card).toBeVisible({ timeout: 60000 });
      openPreview = () =>
        card.getByRole("button", { name: "在线预览" }).click();
      downloadArtifact = async () => {
        await page.getByTitle("关闭预览 (Esc)").click();
        await card.getByRole("button", { name: "安全下载" }).click();
      };
    } else {
      await page.getByTestId("toggle-workspace-button").click();
      await page.getByRole("button", { name: /^产物库/ }).click();
      const card = page
        .locator("button")
        .filter({ hasText: artifact.file_name })
        .first();
      await expect(card).toBeVisible({ timeout: 60000 });
      openPreview = () => card.click();
      downloadArtifact = () =>
        page.getByRole("button", { name: "下载", exact: true }).last().click();
    }
    const [preview] = await Promise.all([
      page.waitForResponse((response) =>
        new URL(response.url()).pathname.endsWith("/workspace/preview"),
      ),
      openPreview(),
    ]);
    expect(preview.status()).toBe(200);
    expect(preview.headers()["content-security-policy"]).toContain(
      "script-src 'none'",
    );
    await expect(
      page.frameLocator("iframe:visible").first().getByText(chain.marker),
    ).toBeVisible({ timeout: 30000 });
    expect(
      await page.locator("iframe:visible").first().getAttribute("sandbox"),
    ).not.toContain("allow-same-origin");
    await page.screenshot({
      path: resolve(directory, `${fixture.graph}-html.png`),
      fullPage: true,
    });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      downloadArtifact(),
    ]);
    const bytes = await readFile((await download.path())!);
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(
      artifact.sha256,
    );
    checks.push(`${fixture.graph}-html-preview-authenticated-download-hash`);
  }
  expect(errors).toEqual([]);
  await writeFile(
    resolve(directory, "result.json"),
    JSON.stringify({ checks, browserErrors: errors, passed: true }, null, 2),
  );
});
