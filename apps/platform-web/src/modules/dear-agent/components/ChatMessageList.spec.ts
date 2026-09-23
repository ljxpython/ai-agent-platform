import { mount } from "@vue/test-utils";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { expect, it } from "vitest";
import ChatMessageList from "@/modules/chat/components/ChatMessageList.vue";

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

    // 若正在流式传输中且只有用户消息，由 :agent:loading 占位块展示“Agent 正在组织答复...”，底部不重复叠加“Agent 正在处理当前回合”
    await wrapper.setProps({
      messages: [new HumanMessage({ id: "user-1", content: "请写一份方案" })],
      stream: { isLoading: { value: true } } as any,
    });
    expect(wrapper.findAllComponents({ name: "MessageContent" })[1]?.props("blocks")).toEqual([
      expect.objectContaining({ kind: "loading", text: "Agent 正在组织答复..." }),
    ]);
    expect(wrapper.text()).not.toContain("Agent 正在处理当前回合");
  } finally {
    wrapper.unmount();
  }
});

it("keeps '执行步骤与工具调用' expanded after tool execution completes until user manually collapses it", async () => {
  const wrapper = mount(ChatMessageList, {
    props: {
      messages: [
        new HumanMessage({ id: "user-1", content: "批准，把剩余的完成吧" }),
        new AIMessage({
          id: "agent-step-1",
          content: "先运行检查",
          tool_calls: [{ name: "execute", args: { command: "python report.py" }, id: "call-1" }],
        }),
        new AIMessage({ id: "agent-final", content: "已修复完成" }),
      ],
      calls: [
        {
          id: "call-1",
          name: "execute",
          args: { command: "python report.py" },
          status: "completed",
          result: "ok",
        } as any,
      ],
      isRunning: true,
    },
    global: { stubs: { MessageContent: true, ToolResult: true } },
  });

  try {
    const details = wrapper.find("details");
    expect(details.exists()).toBe(true);
    expect(details.attributes("open")).toBeDefined();

    // 工具调用与回合全部完成后 (isRunning = false)，依然保持展开，不自动折叠
    await wrapper.setProps({ isRunning: false });
    expect(details.attributes("open")).toBeDefined();

    // 用户手动点击 summary 后才收起
    await details.find("summary").trigger("click");
    expect(details.attributes("open")).toBeUndefined();

    // 用户再次点击可重新展开
    await details.find("summary").trigger("click");
    expect(details.attributes("open")).toBeDefined();
  } finally {
    wrapper.unmount();
  }
});

