import { mount } from "@vue/test-utils";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { expect, it } from "vitest";
import ChatMessageList from "./ChatMessageList.vue";

it("renders branch button and emits fork with messageId and optional checkpointId", async () => {
  const wrapper = mount(ChatMessageList, {
    props: {
      messages: [
        new HumanMessage({ id: "user-1", content: "你好" }),
        new AIMessage({ id: "agent-1", content: "世界" }),
      ],
      calls: [],
      isRunning: false,
      canEdit: true,
    },
    global: { stubs: { MessageContent: true, ToolResult: true } },
  });

  try {
    const forkBtn = wrapper.findAll("button").find((item) => item.text() === "分支")!;
    expect(forkBtn.exists()).toBe(true);
    expect(forkBtn.attributes("title")).toBe("在新对话中分支");
    await forkBtn.trigger("click");
    expect(wrapper.emitted("fork")).toEqual([["agent-1", undefined]]);

    await wrapper.setProps({
      metadata: { "agent-1": { messageId: "agent-1", checkpointId: "chk-abc" } },
    });
    await forkBtn.trigger("click");
    expect(wrapper.emitted("fork")?.[1]).toEqual(["agent-1", "chk-abc"]);

    await wrapper.setProps({ isRunning: true });
    expect(forkBtn.attributes("disabled")).toBeDefined();
    expect(forkBtn.attributes("title")).toBe("仅可从已完成轮次分支");
  } finally {
    wrapper.unmount();
  }
});

it("hides 'Agent 正在处理当前回合' when assistant answer is complete and stream is not loading", async () => {
  const wrapper = mount(ChatMessageList, {
    props: {
      messages: [
        new HumanMessage({ id: "user-1", content: "请写一份方案" }),
        new AIMessage({ id: "agent-1", content: "方案已为您准备好如下..." }),
      ],
      calls: [],
      isRunning: true,
      stream: { isLoading: { value: false } } as any,
    },
    global: { stubs: { MessageContent: true, ToolResult: true } },
  });

  try {
    // 助手已完成回复且 stream 已经非 loading，即使底层 isRunning 因后台校验仍为 true，也不应挂着“处理当前回合”
    expect(wrapper.text()).not.toContain("Agent 正在处理当前回合");

    // 若正在流式传输中且只有用户消息，则应当展示
    await wrapper.setProps({
      messages: [new HumanMessage({ id: "user-1", content: "请写一份方案" })],
      stream: { isLoading: { value: true } } as any,
    });
    expect(wrapper.text()).toContain("Agent 正在处理当前回合");
  } finally {
    wrapper.unmount();
  }
});
