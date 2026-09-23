import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { BaseMessage } from "@langchain/core/messages";
import TrajectoryView from "@/modules/chat/components/trajectory/TrajectoryView.vue";

describe("TrajectoryView component", () => {
  it("正常渲染空消息下的轨迹视图", () => {
    const wrapper = mount(TrajectoryView, {
      props: {
        messages: [],
        calls: [],
        isRunning: false,
      },
    });

    expect(wrapper.text()).toContain("0 轮 · 0 步");
    expect(wrapper.text()).toContain("0 工具");
    expect(wrapper.text()).toContain("暂无匹配的轨迹事件");
  });

  it("当有消息与工具调用时，能够渲染事件流水并展示检查器", async () => {
    const messages = [
      {
        type: "human",
        content: "查一下当前目录",
      } as unknown as BaseMessage,
      {
        type: "ai",
        content: "正在为你查询",
        tool_calls: [
          {
            id: "call-list",
            name: "list_dir",
            args: { path: "." },
          },
        ],
      } as unknown as BaseMessage,
      {
        type: "tool",
        tool_call_id: "call-list",
        name: "list_dir",
        content: JSON.stringify(["file1.txt", "file2.txt"]),
      } as unknown as BaseMessage,
      {
        type: "ai",
        content: "目录中有两个文件：file1.txt 和 file2.txt",
      } as unknown as BaseMessage,
    ];

    const wrapper = mount(TrajectoryView, {
      props: {
        messages,
        calls: [],
        isRunning: false,
      },
    });

    expect(wrapper.text()).toContain("1 轮 · 4 步");
    expect(wrapper.text()).toContain("1 工具");
    expect(wrapper.text()).toContain("list_dir");
    expect(wrapper.text()).toContain("Turn 1");

    // 点击 list_dir 工具行
    const rows = wrapper.findAll("[data-testid='trajectory-record-row']");
    const toolRow = rows.find((r) => r.text().includes("list_dir"));
    expect(toolRow).toBeDefined();

    if (toolRow) {
      await toolRow.trigger("click");
      // 检查器应该显示出 list_dir 的详情
      expect(wrapper.text()).toContain("Input Payload");
      expect(wrapper.text()).toContain("Output Result");
    }
  });

  it("过滤切换正常工作", async () => {
    const messages = [
      { type: "human", content: "hi" } as unknown as BaseMessage,
      {
        type: "ai",
        content: "",
        tool_calls: [{ id: "c1", name: "tool1", args: {} }],
      } as unknown as BaseMessage,
      {
        type: "tool",
        tool_call_id: "c1",
        name: "tool1",
        content: "Error: failed",
        status: "error",
      } as unknown as BaseMessage,
    ];

    const wrapper = mount(TrajectoryView, {
      props: {
        messages,
        calls: [],
        isRunning: false,
      },
    });

    expect(wrapper.text()).toContain("1 异常");

    // 点击“仅工具”
    const toolsFilterBtn = wrapper.findAll("button").find((b) => b.text().includes("仅工具"));
    expect(toolsFilterBtn).toBeDefined();
    await toolsFilterBtn?.trigger("click");
    expect(wrapper.text()).toContain("tool1");
    // 不再显示被过滤的用户消息
    expect(wrapper.findAll("[data-testid='trajectory-record-row']").length).toBe(1);
  });
});
