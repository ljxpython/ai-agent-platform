import { describe, expect, it } from "vitest";
import { AIMessage, ToolMessage } from "@langchain/core/messages";
import { buildTranscript } from "./transcript";
import type { AssembledToolCall } from "@langchain/langgraph-sdk/stream";

describe("Dear Agent transcript projection", () => {
  it("sanitizes interrupt errors and preserves running state for request_information", () => {
    const messages = [
      new AIMessage({
        id: "a1",
        content: "请补充信息",
        tool_calls: [
          {
            id: "call-info-1",
            name: "request_information",
            args: { question: "请提供背景" },
          },
        ],
      }),
    ];

    const calls: AssembledToolCall[] = [
      {
        id: "call-info-1",
        callId: "call-info-1",
        name: "request_information",
        namespace: [],
        input: { question: "请提供背景" },
        args: { question: "请提供背景" },
        status: "error" as any,
        error: "(Interrupt(value={'kind': 'clarification'}),)",
        output: Promise.resolve(null),
      } as unknown as AssembledToolCall,
    ];

    const [turn] = buildTranscript(messages, calls, false);
    const tools = turn?.work.flatMap((item) => item.tools) ?? [];
    expect(tools).toHaveLength(1);
    const tool = tools[0]!;
    expect(tool.name).toBe("request_information");
    // Interrupt error must be cleaned up
    expect(tool.error).toBeUndefined();
    // Must not be marked as error or incomplete when waiting for clarification
    expect(tool.status).toBe("running");
  });

  it("prioritizes authoritative ToolMessage success over transient call error", () => {
    const messages = [
      new AIMessage({
        id: "a1",
        content: "请补充信息",
        tool_calls: [
          {
            id: "call-info-2",
            name: "request_information",
            args: { question: "请提供背景" },
          },
        ],
      }),
      new ToolMessage({
        tool_call_id: "call-info-2",
        content: JSON.stringify({ status: "answered", values: { text: "已回复" } }),
        status: "success",
      }),
    ];

    const calls: AssembledToolCall[] = [
      {
        id: "call-info-2",
        callId: "call-info-2",
        name: "request_information",
        namespace: [],
        input: { question: "请提供背景" },
        args: { question: "请提供背景" },
        status: "error" as any,
        error: "(Interrupt(value={'kind': 'clarification'}),)",
        output: Promise.resolve(null),
      } as unknown as AssembledToolCall,
    ];

    const [turn] = buildTranscript(messages, calls, false);
    const tools = turn?.work.flatMap((item) => item.tools) ?? [];
    expect(tools).toHaveLength(1);
    const tool = tools[0]!;
    expect(tool.name).toBe("request_information");
    expect(tool.status).toBe("finished");
    expect(tool.error).toBeUndefined();
  });
});
