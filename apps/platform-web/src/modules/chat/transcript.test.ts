import { describe, expect, it } from "vitest";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";
import { buildTranscript, contentItems, safeContentUrl } from "./transcript";

describe("SDK transcript projection", () => {
  it("keeps all text and associates reversed results without duplicate tools", () => {
    const messages = [
      new HumanMessage({ id: "u", content: "开始" }),
      new AIMessage({ id: "a1", content: "第一段" }),
      new ToolMessage({ content: "第二个结果", tool_call_id: "t2" }),
      new AIMessage({
        id: "a2",
        content: "第二段",
        tool_calls: [
          { id: "t1", name: "read_file", args: { path: "/a" } },
          { id: "t2", name: "read_file", args: { path: "/b" } },
        ],
      }),
      new ToolMessage({ content: "第一个结果", tool_call_id: "t1" }),
      new AIMessage({
        id: "a3",
        content: [{ type: "text", text: "最终答复" }],
      }),
    ];
    const [turn] = buildTranscript(messages, [], false);
    expect(
      turn?.work.flatMap((item) => item.blocks.map((block) => block.text)),
    ).toEqual(["第一段", "第二段"]);
    expect(
      turn?.work.flatMap((item) => item.tools.map((tool) => tool.output)),
    ).toEqual(["第一个结果", "第二个结果"]);
    expect(turn?.answer[0]?.blocks[0]?.text).toBe("最终答复");
    expect(buildTranscript(messages, [], false)).toEqual(
      buildTranscript(messages, [], false),
    );
  });

  it("keeps unknown blocks and orphan errors, closes unfinished tools, isolates namespaces", () => {
    const messages = [
      new AIMessage({
        content: "",
        tool_calls: [{ id: "c", name: "custom", args: {} }],
      }),
      new ToolMessage({
        content: "失败",
        status: "error",
        tool_call_id: "orphan",
      }),
    ];
    const root = buildTranscript(messages, [], false);
    const scoped = buildTranscript(messages, [], false, [
      "task:one",
      "task:two",
    ]);
    expect(
      root[0]?.work.flatMap((item) => item.tools.map((tool) => tool.status)),
    ).toEqual(["incomplete", "error"]);
    expect(root[0]?.key).not.toBe(scoped[0]?.key);
    expect(
      contentItems([{ type: "future", value: "<script>x</script>" }], "a")[0]
        ?.kind,
    ).toBe("unknown");
    expect(safeContentUrl("javascript:alert(1)")).toBeUndefined();
    expect(
      safeContentUrl("data:image/svg+xml;base64,AAAA", true),
    ).toBeUndefined();
    expect(safeContentUrl("https://user:secret@example.com")).toBeUndefined();
    expect(safeContentUrl("data:image/png;base64,AAAA", true)).toBeDefined();
  });

  it("extracts reasoning content from additional_kwargs and splits thinking tags", () => {
    const aiWithKwargs = new AIMessage({
      content: "正式回答",
      additional_kwargs: { reasoning_content: "逐步思考第一步" },
    });
    const [turn1] = buildTranscript([aiWithKwargs], [], false);
    expect(turn1?.answer[0]?.blocks.map(b => ({ kind: b.kind, text: b.text }))).toEqual([
      { kind: "reasoning", text: "逐步思考第一步" },
      { kind: "text", text: "正式回答" },
    ]);

    const aiWithTags = new AIMessage({
      content: "<think>正在推理复杂逻辑</think>这是正文内容",
    });
    const [turn2] = buildTranscript([aiWithTags], [], false);
    expect(turn2?.answer[0]?.blocks.map(b => ({ kind: b.kind, text: b.text }))).toEqual([
      { kind: "reasoning", text: "正在推理复杂逻辑" },
      { kind: "text", text: "这是正文内容" },
    ]);
  });

  it("handles multi-turn conversations properly", () => {
    const messages = [
      new HumanMessage({ id: "h1", content: "你好" }),
      new AIMessage({ id: "a1", content: [{ type: "reasoning", reasoning: "think 1" }, { type: "text", text: "你好！" }] }),
      new HumanMessage({ id: "h2", content: "你叫什么名字呀？" }),
      new AIMessage({ id: "a2", content: [{ type: "reasoning", reasoning: "think 2" }, { type: "text", text: "我叫 Demo" }] }),
    ];
    const turns = buildTranscript(messages, [], false);
    expect(turns.length).toBe(2);
    expect(turns[0].user?.blocks[0]?.text).toBe("你好");
    expect(turns[0].answer[0]?.blocks.some(b => b.text === "你好！")).toBe(true);
    expect(turns[1].user?.blocks[0]?.text).toBe("你叫什么名字呀？");
    expect(turns[1].answer[0]?.blocks.some(b => b.text === "我叫 Demo")).toBe(true);
  });
});
