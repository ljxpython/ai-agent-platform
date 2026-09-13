import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ChatStickyTaskPill from "./ChatStickyTaskPill.vue";

describe("ChatStickyTaskPill.vue", () => {
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

    expect(wrapper.find(".sticky").exists()).toBe(false);
  });

  it("renders sticky progress bar and emits openTasks", async () => {
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

    expect(wrapper.find(".sticky").exists()).toBe(true);
    expect(wrapper.text()).toContain("任务进度");
    expect(wrapper.text()).toContain("进行中: 修复代码");
    expect(wrapper.text()).toContain("1/3");

    // 点击查看待办看板
    const openBtn = wrapper.find("button");
    expect(openBtn.exists()).toBe(true);
    expect(wrapper.text()).toContain("查看待办看板 →");

    await wrapper.find("button:not([title])").trigger("click");
    expect(wrapper.emitted("openTasks")).toBeTruthy();

    // 点击微型折叠按钮展开详情
    const toggleBtn = wrapper.find("button[title='展开微型列表']");
    expect(toggleBtn.exists()).toBe(true);
    await toggleBtn.trigger("click");

    expect(wrapper.text()).toContain("分析缺陷");
    expect(wrapper.text()).toContain("修复代码");
    expect(wrapper.text()).toContain("跑测试");
  });

  it("can be dismissed to avoid covering chat and restored via mini chip", async () => {
    const wrapper = mount(ChatStickyTaskPill, {
      props: {
        planView: {
          planTodos: [{ id: "1", content: "任务A", status: "completed" }],
          ephemeralTodos: [],
          activeTask: null,
          totalTasks: 1,
          completedTasks: 1,
          allTasksCompleted: true,
          hasFrozenPlan: false,
        },
      },
    });

    expect(wrapper.text()).toContain("所有待办任务已顺利完成");

    // 点击收起按钮
    const dismissBtn = wrapper.find("[data-testid='dismiss-task-pill']");
    expect(dismissBtn.exists()).toBe(true);
    await dismissBtn.trigger("click");

    // 主胶囊已收起，显示微型恢复胶囊
    expect(wrapper.text()).not.toContain("所有待办任务已顺利完成");
    const restoreBtn = wrapper.find("[data-testid='restore-task-pill']");
    expect(restoreBtn.exists()).toBe(true);
    expect(restoreBtn.text()).toContain("任务 1/1");

    // 点击恢复
    await restoreBtn.trigger("click");
    expect(wrapper.text()).toContain("所有待办任务已顺利完成");
  });
});

