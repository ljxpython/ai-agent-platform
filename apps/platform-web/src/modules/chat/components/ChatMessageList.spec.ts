import { mount } from "@vue/test-utils";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { expect, it, vi } from "vitest";
import ChatMessageList from "./ChatMessageList.vue";

it("binds the original message toolbar to current message IDs and copies only the answer", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  const wrapper = mount(ChatMessageList, {
    props: { messages: [new HumanMessage({ id: "user-1", content: "问题" }), new AIMessage({ id: "answer-1", content: "回答" })], calls: [], isRunning: false, canEdit: true },
    global: { stubs: { MessageContent: true, ToolResult: true } },
  });
  try {
    const button = (label: string) => wrapper.findAll("button").find(item => item.text() === label)!;
    await button("编辑").trigger("click");
    expect(wrapper.emitted("edit")).toEqual([["user-1", "问题"]]);
    await button("重试").trigger("click");
    expect(wrapper.emitted("retry")).toEqual([["answer-1"]]);
    await wrapper.findAll("button").filter(item => item.text() === "复制")[1]!.trigger("click");
    expect(writeText).toHaveBeenCalledWith("回答");
    await wrapper.setProps({ editingMessageId: "user-1", editingMessageValue: "修改后" });
    expect(wrapper.get("textarea").element.value).toBe("修改后");
    await wrapper.get("textarea").setValue("再次修改");
    expect(wrapper.emitted("update:editingMessageValue")).toEqual([["再次修改"]]);
    await button("提交重发").trigger("click");
    expect(wrapper.emitted("submit-edit")).toHaveLength(1);

    // Fork button tests: visible for completed agent messages
    const forkBtn = wrapper.findAll("button").find(item => item.text() === "分支")!;
    expect(forkBtn.exists()).toBe(true);
    expect(forkBtn.attributes("title")).toBe("在新对话中分支");
    await forkBtn.trigger("click");
    expect(wrapper.emitted("fork")).toEqual([["answer-1", undefined]]);

    // Emits checkpointId when available in metadata
    await wrapper.setProps({
      metadata: { "answer-1": { messageId: "answer-1", checkpointId: "cp-123" } }
    });
    await forkBtn.trigger("click");
    expect(wrapper.emitted("fork")?.[1]).toEqual(["answer-1", "cp-123"]);

    // Disabled when isRunning
    await wrapper.setProps({ isRunning: true });
    expect(forkBtn.attributes("disabled")).toBeDefined();
    expect(forkBtn.attributes("title")).toBe("仅可从已完成轮次分支");
  } finally { wrapper.unmount(); vi.unstubAllGlobals(); }
});

it("keeps a stable agent bubble DOM node and loading placeholder across empty message-start until first token arrives", async () => {
  const userMsg = new HumanMessage({ id: "user-stable-1", content: "测试平滑输出" });
  const wrapper = mount(ChatMessageList, {
    props: {
      messages: [userMsg],
      calls: [],
      isRunning: true,
      canEdit: true,
    },
  });
  try {
    const articlesBefore = wrapper.findAll("article[data-author='agent']");
    expect(articlesBefore).toHaveLength(1);
    const initialElement = articlesBefore[0]!.element;
    expect(wrapper.text()).toContain("Agent 正在组织答复...");
    // Should NOT flash the redundant bottom live-step banner while pending placeholder is shown
    expect(wrapper.text()).not.toContain("Agent 正在处理当前回合");

    // Simulate SSE message-start arriving with empty content ""
    await wrapper.setProps({
      messages: [userMsg, new AIMessage({ id: "ai-stream-1", content: "" })],
    });
    const articlesAtStart = wrapper.findAll("article[data-author='agent']");
    expect(articlesAtStart).toHaveLength(1);
    // Exact same DOM node preserved (no unmount/remount flash!)
    expect(articlesAtStart[0]!.element).toBe(initialElement);
    expect(wrapper.text()).toContain("Agent 正在组织答复...");
    expect(wrapper.text()).not.toContain("Agent 正在处理当前回合");

    // Simulate first reasoning-delta arriving
    await wrapper.setProps({
      messages: [
        userMsg,
        new AIMessage({
          id: "ai-stream-1",
          content: [{ type: "reasoning", reasoning: "正在分析问题..." }],
        }),
      ],
    });
    const articlesDuringReasoning = wrapper.findAll("article[data-author='agent']");
    expect(articlesDuringReasoning[0]!.element).toBe(initialElement);
    expect(wrapper.text()).toContain("正在思考...");
    expect(wrapper.text()).toContain("正在分析问题...");
  } finally {
    wrapper.unmount();
  }
});

