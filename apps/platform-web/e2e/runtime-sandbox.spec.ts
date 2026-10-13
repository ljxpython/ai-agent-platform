import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

test("沙箱上传、真实执行、产物下载与同 Thread 恢复", async ({ page }) => {
  test.skip(
    process.env.RUN_RUNTIME_SANDBOX_E2E !== "1",
    "Requires this Worktree sandbox runner",
  );
  test.setTimeout(1200000);
  const mode = process.env.SANDBOX_TEST_MODE ?? "local";
  const fixture = await createPlatformFixture("dearflow_agent");
  const marker = `sandbox-${mode}-${crypto.randomUUID().slice(0, 8)}`;
  let threadId = "";
  let testFailed = false;
  let cleanupFailure: string | undefined;
  const errors: string[] = [];
  const transientQueryFailures: string[] = [];
  let approvalReloads = 0;
  const failedRequests: Array<{ path: string; status: number }> = [];
  const directory = resolve(
    import.meta.dirname,
    "../../../docs/projects/20261012-runtime-remote-docker-sandbox/evidence",
    mode,
  );
  await mkdir(directory, { recursive: true });
  page.on("framenavigated", (frame) => {
    if (frame !== page.mainFrame()) return;
    const path = new URL(frame.url()).pathname;
    if (path.startsWith(`/workspace/projects/${fixture.projectId}/chat/`))
      threadId = path.split("/").pop()!;
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400)
      failedRequests.push({
        path: new URL(response.url()).pathname,
        status: response.status(),
      });
  });
  try {
    await page.addInitScript(
      ({ tokens, projectId }) => {
        localStorage.setItem(
          "pw:auth:token-set",
          JSON.stringify({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
            tokenType: tokens.token_type,
          }),
        );
        localStorage.setItem("pw:workspace:project-id", projectId);
      },
      { tokens: fixture.tokens, projectId: fixture.projectId },
    );
    const modelBundle = Promise.all(
      [
        "/api/runtime/models",
        `/api/projects/${fixture.projectId}/runtime-policies/models`,
      ].map((path) =>
        page.waitForResponse(
          (response) => new URL(response.url()).pathname === path,
          { timeout: 180000 },
        ),
      ),
    );
    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
    );
    for (const response of await modelBundle) {
      expect(response.status()).toBe(200);
      await response.finished();
    }
    const composer = page.getByRole("textbox", { name: "消息草稿" });
    await expect(composer, JSON.stringify(errors)).toBeVisible({
      timeout: 180000,
    });
    await page.locator('input[type="file"]').setInputFiles({
      name: "sandbox-proof.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(marker),
    });
    await expect(
      page.getByText("sandbox-proof.txt", { exact: true }),
    ).toBeVisible();
    const prompt = `请真实完成这些操作：用 parse_document 读取上传的 sandbox-proof.txt，随后只调用一次 execute，原样执行命令 printf '${marker}' > "$RUNTIME_WORKSPACE_ROOT/work/proof.md"; cat "$RUNTIME_WORKSPACE_ROOT/work/proof.md"，再用 read_file 读取 /workspace/work/proof.md，最后用 present_artifacts 发布这个 Markdown 文件。shell 使用 RUNTIME_WORKSPACE_ROOT 环境变量，文件工具使用虚拟路径；不要修改命令、不要重复 execute、不要委派、不要搜索，必须遵守审批。`;
    await composer.focus();
    await composer.fill(prompt);
    await expect(composer).toHaveValue(prompt);
    await expect(
      page.getByRole("button", { name: "发送", exact: true }),
    ).toBeEnabled({ timeout: 180000 });
    const [upload] = await Promise.all([
      page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname.includes("/files/uploads/") &&
          response.request().method() === "PUT",
        { timeout: 120000 },
      ),
      page.waitForRequest(
        (request) =>
          new URL(request.url()).pathname.endsWith("/commands") &&
          request.method() === "POST",
        { timeout: 60000 },
      ),
      composer.press("Enter"),
    ]);
    expect(upload.status()).toBe(200);
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
    threadId = new URL(page.url()).pathname.split("/").pop()!;
    await expect(composer).toHaveValue("", { timeout: 30000 });
    const review = page.getByRole("region", { name: "待审批操作" });
    for (let attempt = 0; attempt < 15; attempt++) {
      let phase = "active";
      await expect
        .poll(
          async () => {
            if (await review.isVisible()) return (phase = "review");
            const runs = await fixture
              .request<
                Array<{ status: string }>
              >(`/api/langgraph/threads/${threadId}/runs`)
              .catch((error: Error) => {
                if (!/HTTP 50[234]/.test(error.message)) throw error;
                transientQueryFailures.push(error.message);
                return [];
              });
            if (runs[0]?.status === "interrupted") {
              await page.reload();
              approvalReloads++;
              await expect(review).toBeVisible({ timeout: 180000 });
              return (phase = "review");
            }
            return (phase =
              runs[0] &&
              !["pending", "running", "interrupted"].includes(runs[0].status)
                ? runs[0].status
                : "active");
          },
          { timeout: 600000 },
        )
        .not.toBe("active");
      if (phase !== "review") {
        expect(phase).toBe("success");
        break;
      }
      for (const button of await review
        .getByRole("button", { name: "批准 (Approve)" })
        .all())
        await button.click();
      const [approval] = await Promise.all([
        page.waitForResponse(
          (response) =>
            new URL(response.url()).pathname ===
              `/api/langgraph/threads/${threadId}/commands` &&
            response.request().method() === "POST",
          { timeout: 180000 },
        ),
        review.getByRole("button", { name: "确认批准所选操作" }).click(),
      ]);
      expect(approval.status()).toBe(200);
      await expect(review).not.toBeVisible({ timeout: 180000 });
    }
    const state = await fixture.request<{
      values: {
        messages: Array<{
          type: string;
          name?: string;
          status?: string;
          artifact?: { exit_code?: number };
          content: unknown;
        }>;
      };
    }>(`/api/langgraph/threads/${threadId}/state`);
    const tools = state.values.messages.filter(
      (message) => message.type === "tool",
    );
    for (const name of [
      "parse_document",
      "execute",
      "read_file",
      "present_artifacts",
    ])
      expect(
        tools.some(
          (message) => message.name === name && message.status !== "error",
        ),
        JSON.stringify(tools),
      ).toBe(true);
    expect(tools.filter((message) => message.name === "execute")).toHaveLength(
      1,
    );
    expect(
      tools.find((message) => message.name === "execute")?.artifact?.exit_code,
    ).toBe(0);
    expect(
      tools.some(
        (message) =>
          message.name === "read_file" &&
          JSON.stringify(message.content).includes(marker),
      ),
    ).toBe(true);
    const artifacts = await fixture.request<{
      items: Array<{ file_name: string; path: string; sha256: string }>;
    }>(`/api/langgraph/threads/${threadId}/artifacts`);
    const artifact = artifacts.items.find((item) =>
      item.file_name.endsWith(".md"),
    );
    expect(artifact).toBeDefined();
    await page.reload();
    await expect(page.getByTestId("transcript").first()).toContainText(marker, {
      timeout: 30000,
    });
    await page.screenshot({
      path: resolve(directory, "chat.png"),
      fullPage: true,
      animations: "disabled",
    });
    await page.goto(
      `/workspace/projects/${fixture.projectId}/dear-agent-artifacts?threadId=${threadId}`,
    );
    const card = page
      .locator("article")
      .filter({ hasText: artifact!.file_name })
      .first();
    await expect(card).toBeVisible({ timeout: 60000 });
    await card.getByRole("button", { name: "在线预览" }).click();
    await expect(page.getByText(marker, { exact: true })).toBeVisible({
      timeout: 60000,
    });
    await page.screenshot({
      path: resolve(directory, "preview.png"),
      fullPage: true,
      animations: "disabled",
    });
    await page.getByTitle("关闭预览 (Esc)").click();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      card.getByRole("button", { name: "安全下载" }).click(),
    ]);
    const downloaded = await readFile((await download.path())!);
    expect(downloaded.toString("utf8").trim()).toBe(marker);
    expect(createHash("sha256").update(downloaded).digest("hex")).toBe(
      artifact!.sha256,
    );
    expect(errors).toEqual([]);
    await writeFile(
      resolve(directory, "result.json"),
      JSON.stringify(
        {
          mode,
          graph: fixture.graphId,
          threadId,
          marker,
          tools: tools.map((message) => ({
            name: message.name,
            status: message.status,
          })),
          artifact,
          browserErrors: errors,
          transientQueryFailures,
          approvalReloads,
          failedRequests,
        },
        null,
        2,
      ),
    );
  } catch (error) {
    testFailed = true;
    await writeFile(
      resolve(directory, "failure.json"),
      JSON.stringify(
        {
          mode,
          threadId,
          errors,
          error: error instanceof Error ? error.message : String(error),
          transientQueryFailures,
          approvalReloads,
          failedRequests,
          url: page.url(),
          body: await page
            .locator("body")
            .innerText()
            .catch(() => ""),
        },
        null,
        2,
      ),
    );
    await page
      .screenshot({ path: resolve(directory, "failure.png"), fullPage: true })
      .catch(() => {});
    throw error;
  } finally {
    await page.close();
    try {
      if (threadId) {
        const runs = await fixture.request<
          Array<{ run_id: string; status: string }>
        >(`/api/langgraph/threads/${threadId}/runs`);
        for (const run of runs.filter((item) =>
          ["pending", "running"].includes(item.status),
        )) {
          await fixture.request(
            `/api/langgraph/threads/${threadId}/runs/${run.run_id}/cancel?wait=true`,
            "POST",
            { action: "interrupt" },
          );
          await expect
            .poll(
              async () => {
                const current = await fixture.request<{ status: string }>(
                  `/api/langgraph/threads/${threadId}/runs/${run.run_id}`,
                );
                return current.status;
              },
              { timeout: 60000 },
            )
            .not.toMatch(/^(pending|running)$/);
        }
        await fixture.request(`/api/langgraph/threads/${threadId}`, "DELETE");
      }
      await fixture.cleanup();
    } catch (error) {
      await writeFile(
        resolve(directory, "cleanup-failure.json"),
        JSON.stringify({
          threadId,
          projectId: fixture.projectId,
          error: error instanceof Error ? error.message : String(error),
        }),
      );
      if (!testFailed)
        cleanupFailure = error instanceof Error ? error.message : String(error);
    }
  }
  expect(cleanupFailure, "fixture cleanup failed").toBeUndefined();
});
