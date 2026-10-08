import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ChatAgentStatusBar from "./ChatAgentStatusBar.vue";
import type { BudgetViewModel } from "../budget/view-model";

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

  it("renders budget terminal stop even when isInterrupted=false and error=undefined (H04 scenario)", async () => {
    const budget: BudgetViewModel = {
      level: "error",
      isTerminal: true,
      title: "本次执行因额度限制停止",
      description: "模型调用额度已耗尽，任务可能尚未完成",
      code: "model_call_limit_reached",
      scope: "run",
      actionType: "adjust_draft",
      actionLabel: "调整请求",
    };

    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        budget,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.find("div").exists()).toBe(true);
    expect(wrapper.text()).toContain("本次执行因额度限制停止");
    expect(wrapper.text()).toContain("调整请求");

    const btn = wrapper.find("button");
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    expect(wrapper.emitted("action")).toEqual([["adjust_draft"]]);
  });

  it("renders thread-exhausted budget with 新建会话 action button", async () => {
    const budget: BudgetViewModel = {
      level: "error",
      isTerminal: true,
      title: "本会话累计调用额度已耗尽",
      description: "会话累计模型调用次数已达上限",
      code: "model_call_limit_reached",
      scope: "thread",
      actionType: "new_thread",
      actionLabel: "新建会话",
    };

    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: false,
        isInterrupted: false,
        budget,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("本会话累计调用额度已耗尽");
    expect(wrapper.text()).toContain("新建会话");

    const btn = wrapper.find("button");
    await btn.trigger("click");
    expect(wrapper.emitted("action")).toEqual([["new_thread"]]);
  });

  it("renders in-flight budget warning (Amber) when isRunning is true", async () => {
    const budget: BudgetViewModel = {
      level: "warning",
      isTerminal: false,
      title: "模型调用额度接近上限",
      description: "剩余模型调用 3 次，正在收尾",
      code: "model_call_limit_approaching",
      scope: "run",
      actionType: "none",
    };

    const wrapper = mount(ChatAgentStatusBar, {
      props: {
        isRunning: true,
        isInterrupted: false,
        budget,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.find("div").exists()).toBe(true);
    expect(wrapper.text()).toContain(
      "模型调用额度接近上限（剩余模型调用 3 次，正在收尾）",
    );
    expect(wrapper.attributes("aria-live")).toBe("polite");

    // In warning state while running, cancel button MUST be present
    const cancelBtn = wrapper.find("button");
    expect(cancelBtn.exists()).toBe(true);
    expect(cancelBtn.text()).toContain("取消");
    await cancelBtn.trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });
});
