import { describe, expect, it } from "vitest";
import { stripAnsi } from "./ansi";

describe("stripAnsi", () => {
  it("应当正确处理空字符串和普通文本", () => {
    expect(stripAnsi("")).toBe("");
    expect(stripAnsi("hello world")).toBe("hello world");
  });

  it("应当正确剥除常见 ANSI 颜色控制字符", () => {
    const colored =
      "\u001b[32m10 passed\u001b[0m, \u001b[33m1 warning\u001b[0m";
    expect(stripAnsi(colored)).toBe("10 passed, 1 warning");
  });

  it("应当正确处理样式加粗、背景色与混合序列", () => {
    const boldAndBg = "\u001b[1m\u001b[41m\u001b[37mCRITICAL ERROR\u001b[0m";
    expect(stripAnsi(boldAndBg)).toBe("CRITICAL ERROR");
  });

  it("应当规范化回车符并替换 \\r\\n 为 \\n", () => {
    const carriage = "step 1\rstep 2\r\nstep 3";
    expect(stripAnsi(carriage)).toBe("step 1\nstep 2\nstep 3");
  });
});
