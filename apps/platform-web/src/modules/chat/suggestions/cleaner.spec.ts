import { describe, it, expect } from "vitest";
import {
  stripThinkingText,
  extractPureMessageText,
  extractRecentSuggestionMessages,
} from "./cleaner";

describe("suggestions/cleaner", () => {
  describe("stripThinkingText", () => {
    it("剥离标准闭合的 think 标签", () => {
      const input = "<think>思考思考一大堆</think>这是真正的回答";
      expect(stripThinkingText(input)).toBe("这是真正的回答");
    });

    it("剥离未闭合的 think 标签", () => {
      const input = "前半句<thinking>正在深思熟虑中未完成";
      expect(stripThinkingText(input)).toBe("前半句");
    });
  });

  describe("extractPureMessageText", () => {
    it("处理纯文本字符串", () => {
      expect(extractPureMessageText("普通文本")).toBe("普通文本");
    });

    it("处理 content blocks 并过滤 reasoning 和 image 块", () => {
      const blocks = [
        { type: "reasoning", text: "模型思维链内容" },
        { type: "text", text: "正文第一段" },
        { type: "image", url: "https://example.com/pic.png" },
        { type: "text", text: "正文第二段" },
      ];
      expect(extractPureMessageText(blocks)).toBe("正文第一段\n\n正文第二段");
    });
  });

  describe("extractRecentSuggestionMessages", () => {
    it("过滤 tool / system 消息并保留最近 user/assistant 消息", () => {
      const messages = [
        { type: "system", content: "You are a helpful assistant" },
        { type: "human", content: "第一句问话" },
        { type: "ai", content: "第一句回答" },
        { type: "tool", content: "tool output" },
        { type: "user", content: "第二句问话" },
        { type: "assistant", content: "第二句回答" },
      ];

      const cleaned = extractRecentSuggestionMessages(messages);
      expect(cleaned).toHaveLength(4);
      expect(cleaned).toEqual([
        { role: "user", content: "第一句问话" },
        { role: "assistant", content: "第一句回答" },
        { role: "user", content: "第二句问话" },
        { role: "assistant", content: "第二句回答" },
      ]);

      // 验证 key 的纯洁性（严格只有 role 和 content）
      for (const item of cleaned) {
        expect(Object.keys(item).sort()).toEqual(["content", "role"]);
      }
    });

    it("截取至多最近 6 条消息", () => {
      const messages = Array.from({ length: 10 }, (_, i) => ({
        type: i % 2 === 0 ? "human" : "ai",
        content: `消息 ${i + 1}`,
      }));

      const cleaned = extractRecentSuggestionMessages(messages);
      expect(cleaned).toHaveLength(6);
      expect(cleaned[0]!.content).toBe("消息 5");
      expect(cleaned[5]!.content).toBe("消息 10");
    });

    it("单条超过 4000 字符时自动截断", () => {
      const longText = "a".repeat(4500);
      const messages = [{ type: "human", content: longText }];

      const cleaned = extractRecentSuggestionMessages(messages);
      expect(cleaned[0]!.content.length).toBe(4000);
    });

    it("总字符数超过 12000 时自动安全截断", () => {
      const messages = [
        { type: "human", content: "b".repeat(3500) },
        { type: "ai", content: "c".repeat(3500) },
        { type: "human", content: "d".repeat(3500) },
        { type: "ai", content: "e".repeat(3500) },
      ]; // 总共 14000 字符

      const cleaned = extractRecentSuggestionMessages(messages);
      const totalLen = cleaned.reduce(
        (acc, cur) => acc + cur.content.length,
        0,
      );
      expect(totalLen).toBeLessThanOrEqual(12000);
      // 最近的一条必须保留完整
      expect(cleaned[cleaned.length - 1]!.content).toBe("e".repeat(3500));
    });
  });
});
