import { describe, expect, it } from "vitest";
import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import {
  buildTrajectoryRecords,
  extractReasoning,
  extractTokens,
  groupTrajectoryByTurn,
} from "./trajectory-adapter";

describe("trajectory-adapter", () => {
  it("正确将人类消息转换为 user 轨迹记录", () => {
    const messages = [
      {
        type: "human",
        content: "你好，请帮我分析一下项目代码",
      } as unknown as BaseMessage,
    ];

    const records = buildTrajectoryRecords(messages);
    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      turnIndex: 1,
      stepIndex: 1,
      kind: "user",
      name: "用户输入",
      summary: "你好，请帮我分析一下项目代码",
      status: "completed",
    });
  });

  it("正确提取思考过程 (reasoning_content 与 <think> 标签)", () => {
    const msg1 = {
      type: "ai",
      content: "我正在思考...",
      additional_kwargs: {
        reasoning_content: "首先需要检查项目规范，然后查看代码目录结构",
      },
    } as unknown as BaseMessage;

    expect(extractReasoning(msg1)).toBe("首先需要检查项目规范，然后查看代码目录结构");

    expect(extractReasoning({ additional_kwargs: { reasoning: "另一种格式" } } as BaseMessage)).toBe("另一种格式");

    const msg2 = {
      type: "ai",
      content: "<think>这是内嵌的思考过程</think>最终回复来了",
    } as unknown as BaseMessage;

    const records = buildTrajectoryRecords([
      { type: "human", content: "hi" } as unknown as BaseMessage,
      msg2,
    ]);

    expect(records).toHaveLength(3); // user, reasoning, assistant
    expect(records[1].kind).toBe("reasoning");
    expect(records[1].reasoning).toBe("这是内嵌的思考过程");
    expect(records[2].kind).toBe("assistant");
    expect(records[2].output).toBe("最终回复来了");
  });

  it("正确关联工具调用与其返回结果，并标记完成态", () => {
    const messages = [
      { type: "human", content: "搜索天气" } as unknown as BaseMessage,
      {
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "call-123",
            name: "get_weather",
            args: { city: "Beijing" },
          },
        ],
      } as unknown as BaseMessage,
      {
        type: "tool",
        tool_call_id: "call-123",
        name: "get_weather",
        content: JSON.stringify({ temp: "22C", condition: "Sunny" }),
      } as unknown as BaseMessage,
      {
        type: "ai",
        content: "北京今天晴天，气温22度",
      } as unknown as BaseMessage,
    ];

    const records = buildTrajectoryRecords(messages);
    expect(records).toHaveLength(3); // user, tool, assistant

    const toolRecord = records[1];
    expect(toolRecord.kind).toBe("tool");
    expect(toolRecord.name).toBe("get_weather");
    expect(toolRecord.input).toEqual({ city: "Beijing" });
    expect(toolRecord.status).toBe("completed");
    expect(toolRecord.summary).toContain("get_weather");
    expect(toolRecord.output).toContain("Sunny");
  });

  it("正确识别工具调用报错状态", () => {
    const messages = [
      { type: "human", content: "执行命令" } as unknown as BaseMessage,
      {
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "call-err",
            name: "execute_command",
            args: { cmd: "rm -rf /" },
          },
        ],
      } as unknown as BaseMessage,
      {
        type: "tool",
        tool_call_id: "call-err",
        name: "execute_command",
        content: "Error: Permission denied",
        status: "error",
      } as unknown as BaseMessage,
    ];

    const records = buildTrajectoryRecords(messages);
    expect(records[1].kind).toBe("tool");
    expect(records[1].status).toBe("error");
    expect(records[1].error).toBe("Error: Permission denied");
  });

  it("支持提取 token 消耗统计并在缺失时优雅降级", () => {
    const msgWithUsage = {
      type: "ai",
      content: "回复",
      usage_metadata: {
        input_tokens: 150,
        output_tokens: 45,
        total_tokens: 195,
      },
    } as unknown as BaseMessage;

    const tokens = extractTokens(msgWithUsage);
    expect(tokens).toEqual({
      input: 150,
      output: 45,
      reasoning: undefined,
    });

    const msgWithoutUsage = {
      type: "ai",
      content: "无 token 记录",
    } as unknown as BaseMessage;

    expect(extractTokens(msgWithoutUsage)).toBeUndefined();
  });

  it("正确处理正在执行的 live tool calls", () => {
    const messages = [
      { type: "human", content: "跑个测试" } as unknown as BaseMessage,
    ];
    const calls: AssembledToolCall[] = [
      {
        callId: "live-1",
        name: "run_test",
        input: { file: "test.py" },
        status: "running",
      } as unknown as AssembledToolCall,
    ];

    const records = buildTrajectoryRecords(messages, calls, true);
    expect(records).toHaveLength(2);
    expect(records[1].kind).toBe("tool");
    expect(records[1].status).toBe("running");
    expect(records[1].name).toBe("run_test");
  });

  it("正确将轨迹记录按轮次 (Turn) 分组", () => {
    const messages = [
      { type: "human", content: "第一轮问题" } as unknown as BaseMessage,
      { type: "ai", content: "第一轮回答" } as unknown as BaseMessage,
      { type: "human", content: "第二轮问题" } as unknown as BaseMessage,
      { type: "ai", content: "第二轮回答" } as unknown as BaseMessage,
    ];

    const records = buildTrajectoryRecords(messages);
    const groups = groupTrajectoryByTurn(records);

    expect(groups).toHaveLength(2);
    expect(groups[0].turnIndex).toBe(1);
    expect(groups[0].records).toHaveLength(2);
    expect(groups[1].turnIndex).toBe(2);
    expect(groups[1].records).toHaveLength(2);
  });
});
