import { expect, test } from "@playwright/test";
import path from "node:path";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { platformUrl, testCredentials } from "./support/platform";

const projectId =
  process.env.PLATFORM_TEST_PROJECT_ID ??
  "5a5b7239-43e3-40e6-bba3-e64d96057607";
const screenshotDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/projects/20261107-session-hydration-and-artifact-offloading/screenshots",
);

test("xiaok DeepSeek reads an image reference and restores it after reload", async ({
  page,
}) => {
  test.setTimeout(180000);
  await mkdir(screenshotDir, { recursive: true });
  const login = await fetch(`${platformUrl}/api/identity/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(testCredentials()),
  });
  expect(login.ok).toBe(true);
  const session = (await login.json()) as {
    tokens: {
      access_token: string;
      refresh_token: string;
      token_type: string;
    };
  };
  const headers = {
    authorization: `Bearer ${session.tokens.access_token}`,
    "x-project-id": projectId,
  };
  const modelsResponse = await fetch(
    `${platformUrl}/api/runtime/platform-models`,
    { headers },
  );
  expect(modelsResponse.ok).toBe(true);
  const { models } = await modelsResponse.json();
  const model = models.find(
    (item: any) => item.display_name === "xiaok DeepSeek E2E",
  );
  expect(new URL(model.base_url).hostname).toBe("xiaok.lol");
  expect(model.model).toBe("deepseek-v4.1-flash");

  await page.addInitScript(
    ({ tokens, activeProjectId }) => {
      localStorage.setItem(
        "pw:auth:token-set",
        JSON.stringify({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          tokenType: tokens.token_type,
        }),
      );
      localStorage.setItem("pw:workspace:project-id", activeProjectId);
    },
    { tokens: session.tokens, activeProjectId: projectId },
  );

  const threadIds = new Set<string>();
  page.on("request", (req) => {
    const match = req.url().match(/\/api\/langgraph\/threads\/([^/?]+)/);
    if (match && /^[0-9a-f-]{36}$/i.test(match[1])) threadIds.add(match[1]);
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/workspace/projects/${projectId}/chat`);
  await page.getByRole("button", { name: "对话目标" }).click();
  await page
    .getByRole("button")
    .filter({ hasText: "dearflow_agent" })
    .first()
    .click();
  const newThread = page.getByRole("button", { name: "新建会话" }).first();
  await expect(newThread).toBeEnabled();
  await newThread.click();
  await page.waitForTimeout(500);

  const composer = page.getByRole("textbox", { name: "消息草稿" });
  await expect(composer).toBeVisible({ timeout: 30000 });
  const modelSelector = page.getByRole("button", { name: "选择对话运行模型" });
  await modelSelector.click();
  const xiaokModel = page
    .locator('[role="button"]')
    .filter({ hasText: "xiaok DeepSeek E2E" })
    .first();
  await expect(xiaokModel).toBeVisible({ timeout: 10000 });
  await xiaokModel.click();
  // 确保模型选择弹层关闭，避免遮挡发送操作
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  const imageBuffer = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 160;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas is unavailable");
    context.fillStyle = "#0757d8";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#ffffff";
    context.font = "bold 48px sans-serif";
    context.fillText("BLUE", 85, 100);
    return canvas.toDataURL("image/png").split(",")[1];
  });
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "visual-test.png",
      mimeType: "image/png",
      buffer: Buffer.from(imageBuffer, "base64"),
    });
  await expect(
    page.locator(".pw-panel").filter({ hasText: "visual-test.png" }),
  ).toBeVisible();

  await page.screenshot({
    path: path.join(screenshotDir, "xiaok-image-before.png"),
    fullPage: true,
  });
  await composer.focus();
  await composer.fill(
    "请使用 read_file 读取本条消息中的图片附件，然后告诉我图片中央的英文单词是什么。必须先读取图片，不要猜。",
  );
  await expect(composer).toHaveValue(/请使用 read_file/);

  const sendBtn = page
    .locator('button[aria-label="发送"], button:has-text("发送")')
    .last();
  await expect(sendBtn).toBeEnabled({ timeout: 15000 });
  await sendBtn.click();
  if ((await composer.inputValue()) !== "") {
    await composer.press("Enter");
  }
  await expect(composer).toHaveValue("", { timeout: 15000 });

  const readTool = page
    .locator(".pw-tool-call")
    .filter({ hasText: /read_file/ })
    .first();
  await expect(readTool).toBeVisible({ timeout: 90000 });
  await expect(readTool).toContainText("已返回", { timeout: 90000 });
  await expect(
    page.locator(".pw-markdown").filter({ hasText: /BLUE/i }).last(),
  ).toBeVisible({ timeout: 90000 });
  const stopButton = page
    .locator('button[aria-label="停止生成"], button[title="停止生成"]')
    .first();
  await expect(stopButton).toBeHidden({ timeout: 90000 });

  await page.waitForURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 30000 });
  const urlMatch = page.url().match(/\/chat\/([0-9a-f-]{36})/);
  const threadId = urlMatch
    ? urlMatch[1]
    : [...threadIds].find((id) => id !== "threads");
  expect(threadId).toBeTruthy();

  const stateResponse = await fetch(
    `${platformUrl}/api/langgraph/threads/${encodeURIComponent(threadId!)}/state`,
    {
      headers: {
        authorization: `Bearer ${session.tokens.access_token}`,
        "x-project-id": projectId,
      },
    },
  );
  if (!stateResponse.ok) {
    throw new Error(
      `State request failed: ${stateResponse.status} ${await stateResponse.text()} (thread=${threadId})`,
    );
  }
  const state = await stateResponse.json();
  const toolMessages = state.values.messages.filter(
    (m: any) => m.type === "tool" && m.name === "read_file",
  );
  expect(toolMessages.length).toBeGreaterThan(0);
  const imageBlock = toolMessages
    .flatMap((m: any) => m.content)
    .find((b: any) => b?.extras?.runtime_image);
  expect(imageBlock).toBeTruthy();
  expect(Buffer.byteLength(JSON.stringify(imageBlock))).toBeLessThanOrEqual(
    1024,
  );
  const ref = imageBlock.extras.runtime_image;
  const final = state.values.messages
    .filter((m: any) => m.type === "ai" && !m.tool_calls?.length)
    .at(-1);
  expect(JSON.stringify(final.content)).toMatch(/BLUE/);
  const runsResponse = await fetch(
    `${platformUrl}/api/langgraph/threads/${threadId}/runs`,
    { headers },
  );
  const runs = await runsResponse.json();
  expect(runs[0].status).toBe("success");
  const media = await fetch(
    `${platformUrl}/api/langgraph/threads/${threadId}/images/content?path=${encodeURIComponent(ref.path)}`,
    { headers },
  );
  expect(media.ok).toBe(true);
  const mediaBytes = Buffer.from(await media.arrayBuffer());
  expect(createHash("sha256").update(mediaBytes).digest("hex")).toBe(
    ref.sha256,
  );
  expect(mediaBytes.length).toBe(ref.size_bytes);
  const historyResponse = await fetch(
    `${platformUrl}/api/langgraph/threads/${threadId}/history`,
    {
      method: "POST",
      headers: { ...headers, "content-type": "application/json" },
      body: JSON.stringify({ limit: 3 }),
    },
  );
  expect(historyResponse.ok).toBe(true);
  expect(await historyResponse.text()).not.toMatch(
    /data:image\/[^;]+;base64,|"base64"\s*:/i,
  );
  const serializedState = JSON.stringify(state);
  expect(serializedState).toContain('"runtime_image"');
  expect(serializedState).not.toMatch(/data:image\/(png|jpeg|webp);base64,/i);
  expect(serializedState).not.toMatch(/"base64"\s*:/i);
  await expect(
    page.locator(".thread-image-container img").first(),
  ).toBeVisible();

  await page.screenshot({
    path: path.join(screenshotDir, "xiaok-image-after.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByRole("textbox", { name: "消息草稿" })).toBeVisible({
    timeout: 30000,
  });
  await expect(
    page.locator(".pw-markdown").filter({ hasText: /BLUE/i }).last(),
  ).toBeVisible({ timeout: 30000 });
  await expect(page.locator(".thread-image-container img").first()).toBeVisible(
    {
      timeout: 30000,
    },
  );
  await page.screenshot({
    path: path.join(screenshotDir, "xiaok-image-reloaded.png"),
    fullPage: true,
  });
  await composer.fill("继续上一轮：只回复图片中央的英文单词，不要调用工具。");
  await composer.press("Enter");
  await expect(composer).toHaveValue("", { timeout: 15000 });
  await expect
    .poll(
      async () => {
        const response = await fetch(
          `${platformUrl}/api/langgraph/threads/${threadId}/runs`,
          { headers },
        );
        const list = await response.json();
        return list.length > runs.length && list[0].status === "success";
      },
      { timeout: 90000 },
    )
    .toBe(true);
  const followup = await (
    await fetch(`${platformUrl}/api/langgraph/threads/${threadId}/state`, {
      headers,
    })
  ).json();
  expect(JSON.stringify(followup.values.messages.at(-1).content)).toMatch(
    /BLUE/,
  );
  expect(JSON.stringify(followup)).not.toMatch(
    /data:image\/[^;]+;base64,|"base64"\s*:/i,
  );
  await page.screenshot({
    path: path.join(screenshotDir, "xiaok-image-followup.png"),
    fullPage: true,
  });
  await writeFile(
    path.join(screenshotDir, "../image-e2e-evidence.json"),
    JSON.stringify(
      {
        threadId,
        projectId,
        modelId: model.id,
        model: model.model,
        providerHost: "xiaok.lol",
        status: "success",
        toolReference: ref,
        stateBytes: Buffer.byteLength(serializedState),
        finalAnswer: final.content,
        followupAnswer: followup.values.messages.at(-1).content,
        mediaHashVerified: true,
        historyInlineMedia: false,
      },
      null,
      2,
    ),
  );
});
