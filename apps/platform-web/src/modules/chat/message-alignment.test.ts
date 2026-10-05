import { describe, expect, it } from "vitest";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import {
  extractMessageText,
  isHumanMessage,
  hasOptimisticEchoed,
  resolveDisplayedMessages,
} from "./message-alignment";

describe("message-alignment", () => {
  describe("extractMessageText and isHumanMessage", () => {
    it("extracts text from string content", () => {
      expect(extractMessageText("hello world")).toBe("hello world");
    });

    it("extracts text from array content", () => {
      expect(
        extractMessageText([
          { type: "text", text: "line 1" },
          { type: "text", text: "line 2" },
        ]),
      ).toBe("line 1\nline 2");
    });

    it("correctly identifies human and ai messages", () => {
      expect(isHumanMessage(new HumanMessage({ content: "hi" }))).toBe(true);
      expect(isHumanMessage(new AIMessage({ content: "hello" }))).toBe(false);
      expect(isHumanMessage({ role: "user", content: "hi" } as any)).toBe(true);
    });
  });

  describe("resolveDisplayedMessages - User queue and optimistic ordering", () => {
    it("places optimistic message AFTER previous round of conversation (prevents jumping to top)", () => {
      // 场景：历史已有 User 1 和 Agent 1
      const user1 = new HumanMessage({ id: "u1", content: "First question" });
      const ai1 = new AIMessage({ id: "a1", content: "First answer" });
      const history = [user1, ai1];

      // 队列弹出新消息 User 2，此时 baseline 包含历史 2 条
      const user2 = new HumanMessage({
        id: "u2-opt",
        content: "Second question from queue",
      });

      const displayed = resolveDisplayedMessages({
        baseMessages: history,
        snapshotMessages: null,
        fallbackMessages: history,
        optimisticUserMessage: user2,
        optimisticBaseCount: 2,
        isSessionRunning: true,
      });

      // 痛点 2 验证：新消息绝对不能排在第一位（页面最顶端）！必须排在 AI 1 下方
      expect(displayed.map((m) => m.content)).toEqual([
        "First question",
        "First answer",
        "Second question from queue",
      ]);
      expect(displayed[0].content).not.toBe("Second question from queue");
    });

    it("keeps optimistic user message strictly separated from previous user message during AI streaming (prevents consecutive user messages)", () => {
      // 场景：历史已有 User 1 和 Agent 1
      const user1 = new HumanMessage({ id: "u1", content: "Question 1" });
      const ai1 = new AIMessage({ id: "a1", content: "Answer 1" });
      const history = [user1, ai1];

      // 队列弹出 User 2，发送时 baseline 记录为 2
      const user2 = new HumanMessage({ id: "u2-opt", content: "Question 2" });

      // 紧接着 AI 2 开始流式生成，当前 stream messages 中多了一条 AI 2 的 partial content
      const ai2Streaming = new AIMessage({
        id: "a2",
        content: "Answer 2 partial...",
      });
      const streamMessagesWithAi2 = [...history, ai2Streaming];

      const displayed = resolveDisplayedMessages({
        baseMessages: streamMessagesWithAi2,
        snapshotMessages: null,
        fallbackMessages: history,
        optimisticUserMessage: user2,
        optimisticBaseCount: 2, // 锚定在历史 2 条之后
        isSessionRunning: true,
      });

      // 痛点 3 验证：严禁出现 User 1 -> User 2 -> Answer 1 这种两条用户消息并排在一起的时序错乱！
      // 正确顺序必须是：User 1 -> Answer 1 -> User 2 -> Answer 2 partial
      expect(displayed.map((m) => m.content)).toEqual([
        "Question 1",
        "Answer 1",
        "Question 2",
        "Answer 2 partial...",
      ]);
    });

    it("deduplicates optimistic message once it has been echoed in base messages", () => {
      const user1 = new HumanMessage({ id: "u1", content: "Question 1" });
      const optimistic = new HumanMessage({ id: "u1", content: "Question 1" });

      expect(hasOptimisticEchoed([user1], optimistic)).toBe(true);

      const displayed = resolveDisplayedMessages({
        baseMessages: [user1],
        snapshotMessages: null,
        fallbackMessages: [],
        optimisticUserMessage: optimistic,
        optimisticBaseCount: 0,
        isSessionRunning: false,
      });

      expect(displayed).toHaveLength(1);
    });

    it("handles initial session with no history correctly", () => {
      const user1 = new HumanMessage({
        id: "u1-opt",
        content: "Hello brand new",
      });

      const displayed = resolveDisplayedMessages({
        baseMessages: [],
        snapshotMessages: null,
        fallbackMessages: [],
        optimisticUserMessage: user1,
        optimisticBaseCount: 0,
        isSessionRunning: true,
      });

      expect(displayed.map((m) => m.content)).toEqual(["Hello brand new"]);
    });
  });
});
