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

  it("renders timeout warning capsule without extra action buttons when turnState is timeout", () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        turnState: "timeout",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("上一回合执行超时，已完成的内容已保留");
    expect(wrapper.find("button").exists()).toBe(false);
    expect(wrapper.classes()).toContain("bg-amber-50");
  });

  it("renders stopping spinner state when turnState is stopping", () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: true,
        isInterrupted: false,
        turnState: "stopping",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("正在停止...");
    expect(wrapper.find("button").exists()).toBe(false);
    expect(wrapper.classes()).toContain("bg-blue-50");
  });

  it("renders unconfirmed stop with verify button and emits verifyStop when clicked", async () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        turnState: "stop_unconfirmed",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("停止结果待确认");
    expect(wrapper.text()).toContain("核实停止");
    expect(wrapper.text()).not.toContain("查看审批");

    const button = wrapper.find("button");
    expect(button.exists()).toBe(true);
    await button.trigger("click");
    expect(wrapper.emitted("verifyStop")).toHaveLength(1);
  });

  it("renders stopped state cleanly when turnState is stopped", () => {
    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        turnState: "stopped",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("已停止");
    expect(wrapper.find("button").exists()).toBe(false);
  });
});
