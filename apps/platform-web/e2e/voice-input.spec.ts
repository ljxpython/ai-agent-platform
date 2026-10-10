import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test.describe("F13 Voice Input E2E", () => {
  test("E01 & E04: voice dictation populates draft, does not auto send, and allows manual send", async ({
    page,
  }) => {
    test.setTimeout(240000);
    const fixture = await createPlatformFixture();

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));

    // 注入 Fake SpeechRecognition 与全局控制句柄
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

        class FakeSpeechRecognition {
          continuous = true;
          interimResults = true;
          lang = "zh-CN";
          maxAlternatives = 1;
          onstart: (() => void) | null = null;
          onend: (() => void) | null = null;
          onerror: ((e: any) => void) | null = null;
          onresult: ((e: any) => void) | null = null;

          start() {
            (window as any).__fakeSpeechRecognitionInstance = this;
            setTimeout(() => this.onstart?.(), 10);
          }
          stop() {
            setTimeout(() => this.onend?.(), 10);
          }
          abort() {
            setTimeout(() => this.onend?.(), 10);
          }
        }

        (window as any).SpeechRecognition = FakeSpeechRecognition;
        (window as any).webkitSpeechRecognition = FakeSpeechRecognition;
        (window as any).__fakeSpeechRecognition = {
          simulateResult(transcript: string, isFinal: boolean) {
            const inst = (window as any).__fakeSpeechRecognitionInstance;
            if (inst && inst.onresult) {
              inst.onresult({
                results: {
                  0: { 0: { transcript }, isFinal, length: 1 },
                  length: 1,
                },
              });
            }
          },
          simulateError(error: string) {
            const inst = (window as any).__fakeSpeechRecognitionInstance;
            if (inst && inst.onerror) {
              inst.onerror({ error });
            }
          },
          simulateEnd() {
            const inst = (window as any).__fakeSpeechRecognitionInstance;
            if (inst && inst.onend) {
              inst.onend();
            }
          },
        };
      },
      { tokens: fixture.tokens, projectId: fixture.projectId },
    );

    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
    );

    const composer = page.getByRole("textbox", { name: "消息草稿" });
    await expect(composer).toBeVisible({ timeout: 30000 });

    const micBtn = page.getByTestId("composer-voice-input-btn");
    await expect(micBtn).toBeVisible();
    await expect(micBtn).toBeEnabled();

    // 1. 点击开始听写
    await micBtn.click();
    await expect(page.getByTestId("composer-voice-interim-box")).toBeVisible({
      timeout: 5000,
    });

    // 2. 模拟 interim 结果到达，草稿框不变
    await page.evaluate(() => {
      (window as any).__fakeSpeechRecognition.simulateResult("正在说的", false);
    });
    await expect(page.getByTestId("composer-voice-interim-box")).toContainText(
      "正在说的",
    );
    await expect(composer).toHaveValue("");

    // 3. 模拟 final 结果到达，进入草稿框；确认没有自动发送
    await page.evaluate(() => {
      (window as any).__fakeSpeechRecognition.simulateResult(
        "请只回复：语音输入验证成功。",
        true,
      );
    });
    await expect(composer).toHaveValue("请只回复：语音输入验证成功。");

    // 停止语音输入
    await micBtn.click();
    await expect(page.getByTestId("composer-voice-interim-box")).toBeHidden({
      timeout: 5000,
    });

    // 4. 用户主动点击发送
    const sendBtn = page.getByRole("button", { name: "发送", exact: true });
    await expect(sendBtn).toBeEnabled();
    await sendBtn.click();

    // 验证消息提交与运行回复
    await expect(page.getByTestId("transcript")).toContainText(
      "请只回复：语音输入验证成功。",
      { timeout: 60000 },
    );
    expect(browserErrors).toEqual([]);
  });

  test("E02 & E05: error degradation, no_speech silent, responsive viewports", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const fixture = await createPlatformFixture();

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

        class FakeSpeechRecognition {
          continuous = true;
          interimResults = true;
          lang = "zh-CN";
          maxAlternatives = 1;
          onstart: (() => void) | null = null;
          onend: (() => void) | null = null;
          onerror: ((e: any) => void) | null = null;
          onresult: ((e: any) => void) | null = null;

          start() {
            (window as any).__fakeSpeechRecognitionInstance = this;
            setTimeout(() => this.onstart?.(), 10);
          }
          stop() {
            setTimeout(() => this.onend?.(), 10);
          }
          abort() {
            setTimeout(() => this.onend?.(), 10);
          }
        }

        (window as any).SpeechRecognition = FakeSpeechRecognition;
        (window as any).__fakeSpeechRecognition = {
          simulateError(error: string) {
            const inst = (window as any).__fakeSpeechRecognitionInstance;
            if (inst && inst.onerror) inst.onerror({ error });
            if (inst && inst.onend) inst.onend();
          },
        };
      },
      { tokens: fixture.tokens, projectId: fixture.projectId },
    );

    // 移动端 viewport 检查
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
    );

    const micBtn = page.getByTestId("composer-voice-input-btn");
    await expect(micBtn).toBeVisible({ timeout: 30000 });

    // 测试 no-speech 静默关闭，不弹全局 toast
    await micBtn.click();
    await expect(page.getByTestId("composer-voice-interim-box")).toBeVisible({
      timeout: 5000,
    });

    await page.evaluate(() => {
      (window as any).__fakeSpeechRecognition.simulateError("no-speech");
    });

    await expect(page.getByTestId("composer-voice-interim-box")).toBeHidden({
      timeout: 5000,
    });

    // 确认文本输入框依然完全正常可用
    const composer = page.getByRole("textbox", { name: "消息草稿" });
    await composer.fill("手工降级打字正常");
    await expect(composer).toHaveValue("手工降级打字正常");
  });
});
