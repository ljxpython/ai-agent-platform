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

it("marks the latest user turn with data-is-last-user and computes GPT-style turn anchoring & streaming follow", async () => {
  const {
    computeTurnAnchorScrollTop,
    computeDynamicBottomSpacerHeight,
    computeStreamingFollowScrollTop,
    isChatViewportNearContentBottom,
  } = await import("../scroll-state");

  // 1. First turn: question moves to the top (scrollTop = 0), no bottom spacer needed
  expect(
    computeTurnAnchorScrollTop({
      turnCount: 1,
      userElementOffsetTop: 120,
      viewportClientHeight: 800,
    }),
  ).toBe(0);
  expect(
    computeDynamicBottomSpacerHeight({
      turnCount: 1,
      viewportClientHeight: 800,
      latestTurnHeightPx: 100,
    }),
  ).toBe(0);

  // 2. Subsequent turns (turnCount > 1): question stays at upper-middle (32% from top = 256px)
  const anchorTop = computeTurnAnchorScrollTop({
    turnCount: 2,
    userElementOffsetTop: 1000,
    viewportClientHeight: 800,
  });
  expect(anchorTop).toBe(1000 - Math.round(800 * 0.32)); // 744

  // Dynamic spacer pads the remaining 68% viewport height (544px) minus current turn height
  const spacerAtStart = computeDynamicBottomSpacerHeight({
    turnCount: 2,
    viewportClientHeight: 800,
    latestTurnHeightPx: 100,
  });
  expect(spacerAtStart).toBe(Math.round(800 * 0.68) - 100); // 444

  // As AI streams and turn height grows by 200px, spacer shrinks by 200px so scrollHeight stays constant
  const spacerAfterStream = computeDynamicBottomSpacerHeight({
    turnCount: 2,
    viewportClientHeight: 800,
    latestTurnHeightPx: 300,
  });
  expect(spacerAfterStream).toBe(spacerAtStart - 200);

  // 3. While streaming output is still inside the lower viewport (1000 + 300 = 1300 <= 744 + 800 - 36), scrollTop stays null (no upward jump)
  expect(
    computeStreamingFollowScrollTop({
      currentScrollTop: anchorTop,
      viewportClientHeight: 800,
      contentBottomOffsetTop: 1300,
    }),
  ).toBeNull();

  // Once streaming output exceeds the visible bottom limit (1600 > 744 + 800 - 36 = 1508), scrollTop advances smoothly
  expect(
    computeStreamingFollowScrollTop({
      currentScrollTop: anchorTop,
      viewportClientHeight: 800,
      contentBottomOffsetTop: 1600,
    }),
  ).toBe(1600 - 800 + 36);

  // Near-bottom check accounts for contentBottomOffsetTop even when dynamic spacer increases scrollHeight
  expect(
    isChatViewportNearContentBottom(
      { scrollTop: anchorTop, clientHeight: 800, scrollHeight: 1850 },
      1300,
    ),
  ).toBe(true);

  // 4. DOM attributes on ChatMessageList for multi-turn conversation
  const wrapper = mount(ChatMessageList, {
    props: {
      messages: [
        new HumanMessage({ id: "u-1", content: "第一个问题" }),
        new AIMessage({ id: "a-1", content: "第一个回答" }),
        new HumanMessage({ id: "u-2", content: "第二个问题" }),
        new AIMessage({ id: "a-2", content: "第二个回答" }),
      ],
      calls: [],
      isRunning: true,
    },
    global: { stubs: { MessageContent: true, ToolResult: true } },
  });
  try {
    const userArticles = wrapper.findAll("article[data-author='user']");
    expect(userArticles).toHaveLength(2);
    expect(userArticles[0]!.attributes("data-turn-index")).toBe("0");
    expect(userArticles[0]!.attributes("data-is-last-user")).toBeUndefined();
    expect(userArticles[1]!.attributes("data-turn-index")).toBe("1");
    expect(userArticles[1]!.attributes("data-is-last-user")).toBe("true");
  } finally {
    wrapper.unmount();
  }
});


