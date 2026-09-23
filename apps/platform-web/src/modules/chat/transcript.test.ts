import { describe, expect, it } from "vitest";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";
import {
  buildTranscript,
  contentItems,
  extractChartWeakImageRefs,
  extractRuntimeImages,
  safeContentUrl,
} from "./transcript";

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

  it("renders alternate provider reasoning fields separately from the answer", () => {
    for (const additional_kwargs of [
      { reasoning: "DeepSeek thought" },
      { reasoning_details: [{ type: "reasoning.text", text: "DeepSeek thought" }] },
    ]) {
      const [turn] = buildTranscript([
        new AIMessage({ content: "OK", additional_kwargs }),
      ], [], false);
      expect(turn?.answer[0]?.blocks.map(({ kind, text }) => ({ kind, text }))).toEqual([
        { kind: "reasoning", text: "DeepSeek thought" },
        { kind: "text", text: "OK" },
      ]);
    }
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

  it("extracts runtime images from artifacts and extracts weak refs from text", () => {
    const validRef = {
      version: 1 as const,
      path: "/workspace/generated/generated.png",
      mime_type: "image/png" as const,
      size_bytes: 1024,
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    };
    // 1. Direct artifact
    expect(extractRuntimeImages(validRef)).toEqual([validRef]);
    expect(extractRuntimeImages({ runtime_images: [validRef] })).toEqual([validRef]);
    expect(extractRuntimeImages(null)).toEqual([]);

    // 2. Weak refs from text (charts, generated, uploads)
    const textChart = "图表保存在 /workspace/charts/0123456789abcdef0123456789abcdef.png，请查收。";
    const weakRefsChart = extractChartWeakImageRefs(textChart);
    expect(weakRefsChart).toHaveLength(1);
    expect(weakRefsChart[0]?.path).toBe("/workspace/charts/0123456789abcdef0123456789abcdef.png");
    expect(weakRefsChart[0]?.mime_type).toBe("image/png");

    const textGenerated = "成品路径：/workspace/generated/a03f0e9d6cdf49c4b1189865fefde01b.png";
    const weakRefsGen = extractChartWeakImageRefs(textGenerated);
    expect(weakRefsGen).toHaveLength(1);
    expect(weakRefsGen[0]?.path).toBe("/workspace/generated/a03f0e9d6cdf49c4b1189865fefde01b.png");
    expect(weakRefsGen[0]?.mime_type).toBe("image/png");

    // 3. contentItems splits text inline: [text-before] → [image block] when text contains workspace image path
    const items = contentItems(textGenerated, "msg-generated");
    // 原地切块：路径前的文本 + 图片块（路径从文本中移除）
    expect(items).toHaveLength(2);
    expect(items[0]?.kind).toBe("text");
    expect(items[0]?.text).toBe("成品路径：");
    expect(items[1]?.kind).toBe("image");
    expect(items[1]?.imageRef?.path).toBe("/workspace/generated/a03f0e9d6cdf49c4b1189865fefde01b.png");
  });

  it("renders images beneath inline code paths while keeping text intact, and protects code blocks and links", () => {
    // 1. 行内代码反引号包裹的路径：保留完整代码文本并在下方插入图片卡片
    const codeSpanText = [
      "已再次发布 ✅",
      "",
      "图片地址：`/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png`",
      "",
      "就是上面的预览图——那只暖色夕阳下的白鹈鹕。还需要别的调整尽管说！",
    ].join("\n");

    const weakRefs = extractChartWeakImageRefs(codeSpanText);
    expect(weakRefs).toHaveLength(1);
    expect(weakRefs[0]?.path).toBe(
      "/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png",
    );

    const items = contentItems(codeSpanText, "msg-code-spans");
    expect(items).toHaveLength(3);
    // 第 1 块：包含反引号在内的前段文本，完整保留代码展示
    expect(items[0]?.kind).toBe("text");
    expect(items[0]?.text).toContain("图片地址：`/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png`");
    // 第 2 块：紧随其后放在该路径下方的图片卡片
    expect(items[1]?.kind).toBe("image");
    expect(items[1]?.imageRef?.path).toBe(
      "/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png",
    );
    // 第 3 块：图片下方的后续说明文字
    expect(items[2]?.kind).toBe("text");
    expect(items[2]?.text).toContain("就是上面的预览图");

    // 2. 多行围栏代码块中的路径不得触发图片生成
    const blockCodeText = [
      "```bash",
      "cp /workspace/generated/test.png /workspace/outputs/dest.png",
      "```",
    ].join("\n");
    expect(extractChartWeakImageRefs(blockCodeText)).toEqual([]);
    const blockItems = contentItems(blockCodeText, "msg-block");
    expect(blockItems).toHaveLength(1);
    expect(blockItems[0]?.kind).toBe("text");

    // 3. 普通 Markdown 链接不得作为内嵌图片提取或切碎
    const linkText = "点击查看原图：[查看原图](/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png)。";
    expect(extractChartWeakImageRefs(linkText)).toEqual([]);
    const linkItems = contentItems(linkText, "msg-link");
    expect(linkItems).toHaveLength(1);
    expect(linkItems[0]?.kind).toBe("text");
    expect(linkItems[0]?.text).toBe(linkText);

    // 4. 显式 Markdown 图片语法 ![alt](path) 正常原地切块
    const markdownImgText = "这是说明：![大嘴鸟](/workspace/generated/pelican.png) 请查收。";
    const imgItems = contentItems(markdownImgText, "msg-md-img");
    expect(imgItems).toHaveLength(3);
    expect(imgItems[0]?.kind).toBe("text");
    expect(imgItems[0]?.text).toBe("这是说明：");
    expect(imgItems[1]?.kind).toBe("image");
    expect(imgItems[1]?.imageRef?.path).toBe("/workspace/generated/pelican.png");
    expect(imgItems[2]?.kind).toBe("text");
    expect(imgItems[2]?.text).toBe("请查收。");
  });

  it("distinguishes streaming tool call arguments from active tool execution", () => {
    const partialAiMsg = new AIMessage({
      id: "ai-streaming-write",
      content: "正在撰写最终报告...",
      tool_calls: [
        {
          id: "call-write-1",
          name: "write_file",
          args: {
            path: "/workspace/outputs/report.md",
            content: "A".repeat(1500),
          },
        },
      ],
    });

    // 1. AIMessage 尚未包含 finish_reason，视为模型正在流式生成参数
    const streamingTurns = buildTranscript([partialAiMsg], [], true);
    const streamingTool = streamingTurns[0]?.work[0]?.tools[0];
    expect(streamingTool?.status).toBe("running");
    expect(streamingTool?.streamingInput).toBe(true);
    expect(streamingTool?.streamingChars).toBe(1500);

    // 2. AIMessage 包含 finish_reason="tool_calls"，说明模型已结束输出，正在执行工具节点
    const finishedAiMsg = new AIMessage({
      id: "ai-streaming-write",
      content: "正在撰写最终报告...",
      tool_calls: [
        {
          id: "call-write-1",
          name: "write_file",
          args: {
            path: "/workspace/outputs/report.md",
            content: "A".repeat(23140),
          },
        },
      ],
      response_metadata: { finish_reason: "tool_calls" },
    });
    const executingTurns = buildTranscript([finishedAiMsg], [], true);
    const executingTool = executingTurns[0]?.work[0]?.tools[0];
    expect(executingTool?.status).toBe("running");
    expect(executingTool?.streamingInput).toBeUndefined();
    expect(executingTool?.streamingChars).toBeUndefined();
  });
});
