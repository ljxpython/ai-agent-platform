import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ChatAgentStatusBar from "./ChatAgentStatusBar.vue";

describe("ChatAgentStatusBar", () => {
  it("does not render when run is stopped/idle without error or interrupt", () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.find("div").exists()).toBe(false);
  });

  it("renders interrupted state with 查看审批 when isInterrupted is true", async () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: true,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("等待人工确认");
    expect(wrapper.text()).toContain("查看审批");
    expect(wrapper.text()).not.toContain("继续生成");
    expect(wrapper.text()).not.toContain("执行已暂停/中断");

    await wrapper.find("button").trigger("click");
    expect(wrapper.emitted("resume")).toHaveLength(1);
  });

  it("renders error message and formats runtime.tool.not_allowed correctly", () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        error: "runtime.tool.not_allowed: bash",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("工具「bash」已被项目策略禁用，无法执行");
  });
});
