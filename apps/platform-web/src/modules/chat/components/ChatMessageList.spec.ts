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
  } finally { wrapper.unmount(); vi.unstubAllGlobals(); }
});
