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
