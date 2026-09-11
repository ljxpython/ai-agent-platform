import { expect, test } from "@playwright/test";

test("rendering security, error semantics, keyboard and stable long transcript", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto("/e2e/render-fixture.html");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.getByText("工具前正文", { exact: true })).toBeVisible();
  await expect(page.getByText("工具后正文", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: /edit_file/ }).click();
  await expect(page.getByText("拟修改，尚未确认执行", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: /execute/ }).click();
  await expect(page.getByText("非交互命令", { exact: false })).toBeVisible();
  await expect(page.getByText("非交互命令", { exact: false })).toContainText("退出码 7");
  await expect(page.getByText("非交互命令", { exact: false })).toContainText("输出已截断");
  await page.getByRole("button", { name: /unrecognized_tool/ }).click();
  await expect(page.getByText("unknown tool result", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { xss?: number }).xss)).toBeUndefined();
  expect(await page.locator('a[href^="javascript:"], img[src^="data:image/svg"]').count()).toBe(0);
  await expect(page.getByText("文档产物可读", { exact: true })).toBeVisible();
  await expect(page.getByText("Markdown 产物可读", { exact: true })).toBeVisible();
  await expect(page.getByText("未公开下载文件", { exact: false })).toBeVisible();
  await page.getByText("公开推理", { exact: true }).click();
  await expect(page.getByText("公开推理说明")).toBeVisible();
  await expect(page.getByRole("button", { name: /展开全文/ })).toBeVisible();
  await page.getByRole("button", { name: "打开测试弹窗" }).click();
  await expect(page.getByRole("dialog", { name: "测试弹窗" })).toBeVisible();
  await page.getByRole("button", { name: "末尾按钮" }).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("dialog").getByRole("button").first()).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "打开测试弹窗" })).toBeFocused();
  const metrics = await page.evaluate(async () => {
    const api = (window as unknown as { renderFixture: { setLong(): Promise<void>; tick(i: number): Promise<void> } }).renderFixture;
    await api.setLong();
    const original = document.querySelector('[data-testid="transcript"] article');
    const input = document.querySelector("input")!;
    input.focus();
    const latencies: number[] = [];
    const longTasks: number[] = [];
    const observer = new PerformanceObserver(list => longTasks.push(...list.getEntries().map(item => item.duration)));
    observer.observe({ type: "longtask", buffered: false });
    const start = performance.now();
    // Requested 20 updates/sec for 60 seconds, real rendering in Chromium.
    for (let i = 0; i < 1200; i++) {
      const before = performance.now();
      input.value = String(i);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      await api.tick(i);
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      latencies.push(performance.now() - before);
      await new Promise(resolve => setTimeout(resolve, Math.max(0, start + (i + 1) * 50 - performance.now())));
    }
    observer.disconnect();
    latencies.sort((a, b) => a - b);
    return { inputPaintP95: latencies[Math.floor(latencies.length * .95)], duration: performance.now() - start, updates: latencies.length, longTasks: longTasks.length, maxLongTask: Math.max(0, ...longTasks), stableNode: original === document.querySelector('[data-testid="transcript"] article'), focused: document.activeElement === input };
  });
  await test.info().attach("render-performance", { body: JSON.stringify(metrics), contentType: "application/json" });
  console.log("render-performance", JSON.stringify(metrics));
  expect(metrics.stableNode).toBe(true);
  expect(metrics.focused).toBe(true);
  expect(metrics.inputPaintP95).toBeLessThanOrEqual(100);
  expect(errors).toEqual([]);
});
