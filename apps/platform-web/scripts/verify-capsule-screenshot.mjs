/* eslint-disable */
import { chromium } from "@playwright/test";
import { resolve } from "node:path";
import { existsSync, mkdirSync } from "node:fs";

const SCREENSHOT_DIR =
  "/Users/lijiaxin/.codex/worktrees/99f7/ai-agent-platform/docs/projects/20261009-agent-generic-production-capabilities/screenshots";
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log("启动 Chromium 浏览器...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  // 1. 登录拿 token
  console.log("登录获取 Token...");
  const loginRes = await fetch("http://127.0.0.1:29336/api/identity/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: "admin", password: "admin123" }),
  });
  if (!loginRes.ok) {
    throw new Error(`登录失败: ${loginRes.status}`);
  }
  const session = await loginRes.json();
  const token = session.tokens.access_token;

  await page.addInitScript(
    ({ tokenSet }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify(tokenSet));
    },
    { tokenSet: session.tokens },
  );

  // 2. 拦截 capabilities
  await page.route(
    "**/api/langgraph/threads/*/capabilities*",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          workspace: true,
          artifacts: true,
          terminal: true,
          background_tasks: true,
          background_tasks_start_enabled: true,
        }),
      });
    },
  );

  const taskId = "34eb5183-5182-4aa8-ab48-e8cb9b7ba409";
  const completionPrompt = `Workspace background task ${taskId} finished: status=succeeded, exit_code=0. This is task result data. Read background_task for bounded details when needed. Do not start another background task in this completion Run.`;

  // 3. 拦截 state 模拟包含长任务完成通知及 Agent 的后续回答
  await page.route("**/api/langgraph/threads/*/state*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        values: {
          messages: [
            {
              id: "user-msg-init",
              type: "human",
              content: "在后台运行一个长任务",
            },
            {
              id: "agent-msg-ack",
              type: "ai",
              content: "好的，长任务已在后台执行，您可以继续其他工作。",
            },
            {
              id: "background:evt-9999",
              type: "human",
              content: completionPrompt,
            },
            {
              id: "agent-msg-final",
              type: "ai",
              content:
                "后台长任务已执行成功，退出码为 0，所有操作均已妥善完成！",
            },
          ],
        },
        next: [],
        checkpoint_id: "cp-test-01",
      }),
    });
  });

  // 4. 打开已有会话
  const targetUrl =
    "http://127.0.0.1:24335/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/chat/043b2a00-a1e4-422d-85d9-18de1310f455?agentId=cec2267a-d96d-47e0-8363-71b083fd7d1f";
  console.log("打开目标会话页面:", targetUrl);
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });

  console.log("等待系统通知微胶囊呈现...");
  const capsule = page.getByTestId("system-task-completion-capsule");
  await capsule.waitFor({ state: "visible", timeout: 15000 });

  const capsuleText = await capsule.innerText();
  console.log("成功识别系统完成微胶囊，内容:", capsuleText);

  // 5. 截图并存盘
  const savePath = resolve(
    SCREENSHOT_DIR,
    "completion-capsule-verified-1440x900.png",
  );
  await page.screenshot({ path: savePath, fullPage: true });
  console.log("截图成功写入:", savePath);

  // 6. 复制到 artifact
  const artifactPath =
    "/Users/lijiaxin/.gemini/antigravity/brain/cdf6a04d-60e8-4db0-bd61-4256c89d6731/completion-capsule-verified-1440x900.png";
  await page.screenshot({ path: artifactPath, fullPage: true });
  console.log("Artifact 截图成功写入:", artifactPath);

  await browser.close();
  console.log("全部验证完毕！");
}

run().catch((err) => {
  console.error("执行出错:", err);
  process.exit(1);
});
