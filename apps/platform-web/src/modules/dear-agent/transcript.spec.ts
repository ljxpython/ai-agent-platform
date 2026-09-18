import { describe, expect, it } from "vitest";
import { AIMessage, ToolMessage } from "@langchain/core/messages";
import {
  buildTranscript,
  contentItems,
  extractWorkspaceImageRefs,
} from "./transcript";
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

  it("renders images beneath inline code paths while preserving code text in Dear Agent", () => {
    // 模拟用户截图中的情况：说明文件存放路径，代码反引号包裹，并在该路径下方展示图片卡片
    const codeText = [
      "已再次发布 ✅",
      "",
      "图片地址：`/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png`",
      "",
      "就是上面的预览图——那只暖色夕阳下的白鹈鹕。还需要别的调整尽管说！",
    ].join("\n");

    const weakRefs = extractWorkspaceImageRefs(codeText);
    expect(weakRefs).toHaveLength(1);
    expect(weakRefs[0]?.path).toBe(
      "/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png",
    );

    const items = contentItems(codeText, "dear-msg-code");
    expect(items).toHaveLength(3);
    expect(items[0]?.kind).toBe("text");
    expect(items[0]?.text).toContain("图片地址：`/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png`");
    expect(items[1]?.kind).toBe("image");
    expect(items[1]?.imageRef?.path).toBe(
      "/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png",
    );
    expect(items[2]?.kind).toBe("text");
    expect(items[2]?.text).toContain("就是上面的预览图");

    // 显式 Markdown 图片语法正常切块
    const mdImgText = "图表预览：![鹈鹕](/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png)";
    const imgItems = contentItems(mdImgText, "dear-msg-md-img");
    expect(imgItems).toHaveLength(2);
    expect(imgItems[0]?.kind).toBe("text");
    expect(imgItems[0]?.text).toBe("图表预览：");
    expect(imgItems[1]?.kind).toBe("image");
    expect(imgItems[1]?.imageRef?.path).toBe(
      "/workspace/outputs/a9d3bf46bcc2988ed652743d4223c6f3f161dffd75f4fcf6fe7cf12d5dedf64a.png",
    );
  });
});
