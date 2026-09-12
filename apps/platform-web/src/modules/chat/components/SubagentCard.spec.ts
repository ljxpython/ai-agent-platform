import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SubagentCard from "./SubagentCard.vue";
import type { ToolItem } from "../transcript";

describe("SubagentCard.vue", () => {
  it("renders subagent type and description gracefully", () => {
    const tool: ToolItem = {
      key: "task-tool-1",
      id: "call-1",
      name: "task",
      input: {
        subagent_type: "research",
        description: "只读分析 /workspace/report.py 脚本缺陷",
      },
      output: "Command(update={'messages': [ToolMessage(content='# 分析报告\\n\\n发现单价计算缺陷')]})",
      status: "finished",
    };

    const wrapper = mount(SubagentCard, {
      props: { tool },
      global: {
        stubs: {
          BaseIcon: true,
          MessageContent: true,
          SubtaskDetail: true,
        },
      },
    });

    expect(wrapper.text()).toContain("research");
    expect(wrapper.text()).toContain("子智能体");
    expect(wrapper.text()).toContain("已返回");
    expect(wrapper.text()).toContain("只读分析 /workspace/report.py 脚本缺陷");
  });

  it("expands to reveal parsed clean output and subtask detail", async () => {
    const tool: ToolItem = {
      key: "task-tool-2",
      id: "call-2",
      name: "task",
      input: {
        subagent_type: "research",
        description: "只读检查实际文件",
      },
      output: "Command(update={'messages': [ToolMessage(content='# 缺陷证据\\n\\n第 8 行未乘数量')]})",
      status: "finished",
    };

    const wrapper = mount(SubagentCard, {
      props: { tool },
      global: {
        stubs: {
          BaseIcon: true,
          MessageContent: {
            props: ["blocks"],
            template: "<div class='mock-content'>{{ blocks.map(b => b.text).join('') }}</div>",
          },
          SubtaskDetail: true,
        },
      },
    });

    // Before clicking expand, detail area is not rendered
    expect(wrapper.find(".mock-content").exists()).toBe(false);

    // Click to expand
    await wrapper.find("button").trigger("click");
    expect(wrapper.find(".mock-content").exists()).toBe(true);
    expect(wrapper.find(".mock-content").text()).toContain("# 缺陷证据\n\n第 8 行未乘数量");
    // Python Command and ToolMessage wrappers should be cleaned away
    expect(wrapper.find(".mock-content").text()).not.toContain("Command(");
    expect(wrapper.find(".mock-content").text()).not.toContain("ToolMessage(");
  });
});
