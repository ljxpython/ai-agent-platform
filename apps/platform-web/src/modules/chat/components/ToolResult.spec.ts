import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ToolResult from "./ToolResult.vue";
import type { ToolItem } from "../transcript";

describe("ToolResult.vue", () => {
  it("renders write_todos with humanized title and subtitle", () => {
    const tool: ToolItem = {
      key: "todo-tool-1",
      id: "call-todo-1",
      name: "write_todos",
      input: {
        todos: [
          { content: "读取 report.py 分析缺陷", status: "in_progress" },
          { content: "修复计算逻辑", status: "pending" },
          { content: "执行测试验证", status: "completed" },
        ],
      },
      output: undefined,
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
        },
      },
    });

    expect(wrapper.text()).toContain("更新任务清单");
    expect(wrapper.text()).toContain("· 共 3 项");
    expect(wrapper.text()).toContain("已返回");
  });

  it("expands to render structured todo list and emits inspect for task board", async () => {
    const tool: ToolItem = {
      key: "todo-tool-2",
      id: "call-todo-2",
      name: "write_todos",
      input: [
        { content: "定位缺陷", status: "in_progress" },
        { content: "提交修复", status: "pending" },
      ],
      output: undefined,
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
        },
      },
    });

    // 初始折叠
    expect(wrapper.text()).not.toContain("待办计划 · 共 2 项");

    // 点击展开
    const toggleButton = wrapper.find("button");
    await toggleButton.trigger("click");

    expect(wrapper.text()).toContain("待办计划 · 共 2 项");
    expect(wrapper.text()).toContain("定位缺陷");
    expect(wrapper.text()).toContain("进行中");
    expect(wrapper.text()).toContain("提交修复");
    expect(wrapper.text()).toContain("待处理");

    // 检查在详情面板查看任务看板按钮
    const inspectBtn = wrapper.find(".pw-table-tool-button");
    expect(inspectBtn.exists()).toBe(true);
    expect(inspectBtn.text()).toContain("在详情面板查看任务看板 →");

    await inspectBtn.trigger("click");
    expect(wrapper.emitted("inspect")).toBeTruthy();
    expect(wrapper.emitted("inspect")![0]).toEqual([tool]);
  });
});
