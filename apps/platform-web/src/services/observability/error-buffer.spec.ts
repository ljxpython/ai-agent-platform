import { describe, it, expect, beforeEach } from "vitest";
import { ErrorRingBuffer } from "./error-buffer";

describe("ErrorRingBuffer", () => {
  let ringBuffer: ErrorRingBuffer;

  beforeEach(() => {
    ringBuffer = new ErrorRingBuffer(3);
  });

  it("应当正常推入错误记录并按倒序返回", () => {
    ringBuffer.push({
      type: "http",
      status: 500,
      message: "Internal Server Error",
    });
    ringBuffer.push({
      type: "js_runtime",
      message: "TypeError: null",
    });

    expect(ringBuffer.size).toBe(2);
    const all = ringBuffer.getAll();
    expect(all[0].message).toBe("TypeError: null");
    expect(all[1].message).toBe("Internal Server Error");
  });

  it("超过容量限制时应当遵循 FIFO 自动淘汰最旧记录", () => {
    ringBuffer.push({ type: "http", message: "Error 1" });
    ringBuffer.push({ type: "http", message: "Error 2" });
    ringBuffer.push({ type: "http", message: "Error 3" });
    expect(ringBuffer.size).toBe(3);

    // 推入第 4 条，Error 1 应当被挤出
    ringBuffer.push({ type: "http", message: "Error 4" });
    expect(ringBuffer.size).toBe(3);

    const messages = ringBuffer.getAll().map((e) => e.message);
    expect(messages).toEqual(["Error 4", "Error 3", "Error 2"]);
  });

  it("应当支持按 requestId 查询最新匹配错误", () => {
    ringBuffer.push({
      type: "http",
      requestId: "req-1",
      message: "First fail",
    });
    ringBuffer.push({
      type: "http",
      requestId: "req-2",
      message: "Second fail",
    });
    ringBuffer.push({
      type: "http",
      requestId: "req-1",
      message: "First fail retry",
    });

    const match = ringBuffer.getLatestByRequestId("req-1");
    expect(match?.message).toBe("First fail retry");

    const none = ringBuffer.getLatestByRequestId("req-not-exist");
    expect(none).toBeNull();
  });

  it("clear 应当完全清空缓冲区", () => {
    ringBuffer.push({ type: "http", message: "Error 1" });
    expect(ringBuffer.size).toBe(1);
    ringBuffer.clear();
    expect(ringBuffer.size).toBe(0);
    expect(ringBuffer.getLatest()).toBeNull();
  });
});
