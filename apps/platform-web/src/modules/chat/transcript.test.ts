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

  it("never displays subagent internal orphan tool calls at the root transcript level, but preserves them in scoped view", () => {
    const rootAiMsg = new AIMessage({
      id: "ai-delegate",
      content: "委派 research 分析",
      tool_calls: [{ id: "task-call-1", name: "task", args: { subagent_type: "research" } }],
    });

    const calls = [
      {
        id: "task-call-1",
        callId: "task-call-1",
        name: "task",
        input: { subagent_type: "research" },
        status: "finished" as const,
      },
      // Subagent internal tool calls that reached global stream.toolCalls
      {
        id: "sub-read-call",
        callId: "sub-read-call",
        name: "read_file",
        input: { path: "/workspace/report.py" },
        status: "finished" as const,
      },
      {
        id: "sub-ls-call",
        callId: "sub-ls-call",
        name: "ls",
        input: { path: "/workspace" },
        status: "finished" as const,
      },
    ];

    // 1. Root level transcript view (namespace: [])
    const rootTurns = buildTranscript([rootAiMsg], calls, false, []);
    const rootToolNames = rootTurns.flatMap(t => t.work.flatMap(item => item.tools.map(tool => tool.name)));
    // Root level must ONLY contain the 'task' tool call, NEVER orphan sub-tools!
    expect(rootToolNames).toEqual(["task"]);

    // 2. Scoped level transcript view for subagent (namespace: ["tools:task-call-1"])
    const scopedTurns = buildTranscript([], calls, false, ["tools:task-call-1"]);
    const scopedToolNames = scopedTurns.flatMap(t => t.work.flatMap(item => item.tools.map(tool => tool.name)));
    // Scoped subagent view preserves the subagent's tool calls
    expect(scopedToolNames).toContain("read_file");
    expect(scopedToolNames).toContain("ls");
  });

  it("consolidates adjacent text blocks and cleans orphan leading line break after reasoning", () => {
    // 1. 模拟思考过程后紧跟首字符单换行
    const itemsWithOrphanBreak = contentItems(
      "<think>Let me think</think>\n已\n定位缺陷并核对了正确结果。",
      "msg-1",
    );
    expect(itemsWithOrphanBreak).toHaveLength(2);
    expect(itemsWithOrphanBreak[0]?.kind).toBe("reasoning");
    expect(itemsWithOrphanBreak[0]?.text).toBe("Let me think");
    expect(itemsWithOrphanBreak[1]?.kind).toBe("text");
    expect(itemsWithOrphanBreak[1]?.text).toBe("已定位缺陷并核对了正确结果。");

    // 2. 模拟流式推送产生的相邻连续 text blocks 被拆散的情况
    const itemsAdjacent = contentItems(
      [
        { type: "text", text: "已" },
        { type: "text", text: "定位缺陷并核对了正确结果。" },
      ],
      "msg-2",
    );
    expect(itemsAdjacent).toHaveLength(1);
    expect(itemsAdjacent[0]?.kind).toBe("text");
    expect(itemsAdjacent[0]?.text).toBe("已定位缺陷并核对了正确结果。");
  });
});
