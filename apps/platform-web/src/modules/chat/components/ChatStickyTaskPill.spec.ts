import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ChatStickyTaskPill from "./ChatStickyTaskPill.vue";

describe("ChatStickyTaskPill.vue (Composer Top Tray)", () => {
  it("does not render when totalTasks is 0", () => {
    const wrapper = mount(ChatStickyTaskPill, {
      props: {
        planView: {
          planTodos: [],
          ephemeralTodos: [],
          activeTask: null,
          totalTasks: 0,
          completedTasks: 0,
          allTasksCompleted: false,
          hasFrozenPlan: false,
        },
      },
    });

    expect(wrapper.find("[data-testid='composer-task-tray']").exists()).toBe(false);
  });

  it("renders progress ring in tray bar, expands upward to show task list, and emits openTasks", async () => {
    const wrapper = mount(ChatStickyTaskPill, {
      props: {
        planView: {
          planTodos: [
            { id: "1", content: "分析缺陷", status: "completed" },
            { id: "2", content: "修复代码", status: "in_progress" },
            { id: "3", content: "跑测试", status: "pending" },
          ],
          ephemeralTodos: [],
          activeTask: { id: "2", content: "修复代码", status: "in_progress" },
          totalTasks: 3,
          completedTasks: 1,
          allTasksCompleted: false,
          hasFrozenPlan: false,
        },
      },
    });

    expect(wrapper.find("[data-testid='composer-task-tray']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='task-progress-ring']").exists()).toBe(true);
    expect(wrapper.text()).toContain("正在执行：修复代码");
    expect(wrapper.text()).toContain("1/3");

    // 默认不展开详情列表
    expect(wrapper.find("[data-testid='task-tray-list']").exists()).toBe(false);

    // 点击底部托盘控制条向上展开待办清单
    await wrapper.find("[data-testid='toggle-task-tray']").trigger("click");
    expect(wrapper.find("[data-testid='task-tray-list']").exists()).toBe(true);
    expect(wrapper.text()).toContain("分析缺陷");
    expect(wrapper.text()).toContain("修复代码");
    expect(wrapper.text()).toContain("跑测试");

    // 在展开面板右上角点击“待办看板”触发 openTasks
    const openDrawerBtn = wrapper.find("[data-testid='open-task-drawer-btn']");
    expect(openDrawerBtn.exists()).toBe(true);
    await openDrawerBtn.trigger("click");
    expect(wrapper.emitted("openTasks")).toBeTruthy();
  });

  it("renders low-noise completed state without full-width green bar when all tasks are completed", () => {
    const wrapper = mount(ChatStickyTaskPill, {
      props: {
        planView: {
          planTodos: [
            { id: "1", content: "任务A", status: "completed" },
            { id: "2", content: "任务B", status: "completed" },
          ],
          ephemeralTodos: [],
          activeTask: null,
          totalTasks: 2,
          completedTasks: 2,
          allTasksCompleted: true,
          hasFrozenPlan: false,
        },
      },
    });

    expect(wrapper.find("[data-testid='task-completed-icon']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='task-progress-ring']").exists()).toBe(false);
    expect(wrapper.text()).toContain("已完成全部 2 项待办任务");
    expect(wrapper.text()).toContain("2/2");
  });
});


