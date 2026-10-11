import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import BackgroundTaskItem from "./BackgroundTaskItem.vue";
import type { TaskV1 } from "@/modules/chat/background-tasks/types";

describe("BackgroundTaskItem.vue", () => {
  const baseTask: TaskV1 = {
    version: 1,
    task_id: "4ce62cd1-4d07-493e-89ed-d107bdddc8dd",
    thread_id: "thread-1",
    graph_id: "showcase",
    origin_run_id: "origin-1",
    status: "running",
    reason_code: null,
    exit_code: null,
    created_at: "2026-10-11T10:00:00Z",
    started_at: "2026-10-11T10:00:01Z",
    finished_at: null,
    deadline_at: "2026-10-11T10:15:00Z",
    updated_at: "2026-10-11T10:00:05Z",
    cleanup_state: "not_required",
    output: {
      available: true,
      retained_bytes: 100,
      omitted_bytes: 0,
      truncated: false,
      updated_at: "2026-10-11T10:00:05Z",
    },
    delivery: {
      state: "not_ready",
      event_id: null,
      run_id: null,
      reason_code: null,
    },
    allowed_actions: ["read", "logs", "cancel"],
  };

  it("应当正确展示基础任务信息（ID缩略、状态及动作按钮）", () => {
    const wrapper = mount(BackgroundTaskItem, {
      props: {
        task: baseTask,
      },
    });

    expect(wrapper.text()).toContain("4ce62cd1");
    expect(wrapper.text()).toContain("运行中");
    expect(wrapper.find('[data-testid="task-view-logs-btn"]').exists()).toBe(
      true,
    );
    expect(wrapper.find('[data-testid="task-cancel-btn"]').exists()).toBe(true);
  });

  it("当 delivery.state === 'accepted' 且具备 run_id 时，应当显示'续接已接受'，绝不显示'已送达通知'", () => {
    const task: TaskV1 = {
      ...baseTask,
      status: "succeeded",
      delivery: {
        state: "accepted",
        event_id: "evt-1",
        run_id: "run-accepted-1234",
        reason_code: null,
      },
    };
    const wrapper = mount(BackgroundTaskItem, {
      props: { task },
    });

    const acceptedBadge = wrapper.find(
      '[data-testid="delivery-accepted-badge"]',
    );
    expect(acceptedBadge.exists()).toBe(true);
    expect(acceptedBadge.text()).toBe("续接已接受");
    expect(acceptedBadge.attributes("title")).toContain("run-accepted-1234");
    expect(acceptedBadge.attributes("title")).toContain(
      "续接请求已接受，等待原生处理",
    );
    expect(wrapper.text()).not.toContain("已送达通知");
  });

  it("当 delivery.state === 'unknown' 时，应当显示'续接待确认'，且不暴露重发或重试按钮", () => {
    const task: TaskV1 = {
      ...baseTask,
      status: "succeeded",
      delivery: {
        state: "unknown",
        event_id: null,
        run_id: null,
        reason_code: null,
      },
    };
    const wrapper = mount(BackgroundTaskItem, {
      props: { task },
    });

    const unknownBadge = wrapper.find('[data-testid="delivery-unknown-badge"]');
    expect(unknownBadge.exists()).toBe(true);
    expect(unknownBadge.text()).toBe("续接待确认");
    expect(unknownBadge.attributes("title")).toBe(
      "续接状态确认中，正在保持只读查询",
    );
    // 确保没有出现任何重试或重新执行按钮
    expect(wrapper.text()).not.toContain("重发");
    expect(wrapper.text()).not.toContain("重试");
  });

  it("当 delivery.state === 'suppressed' 时，应当显示'通知已抑制'", () => {
    const task: TaskV1 = {
      ...baseTask,
      status: "cancelled",
      delivery: {
        state: "suppressed",
        event_id: null,
        run_id: "old-run-id-kept-for-audit",
        reason_code: null,
      },
    };
    const wrapper = mount(BackgroundTaskItem, {
      props: { task },
    });

    const suppressedBadge = wrapper.find(
      '[data-testid="delivery-suppressed-badge"]',
    );
    expect(suppressedBadge.exists()).toBe(true);
    expect(suppressedBadge.text()).toBe("通知已抑制");
  });

  it("当 cleanup_state === 'unconfirmed' 时，应当如实展示'清理未确认'", () => {
    const task: TaskV1 = {
      ...baseTask,
      cleanup_state: "unconfirmed",
    };
    const wrapper = mount(BackgroundTaskItem, {
      props: { task },
    });

    expect(wrapper.text()).toContain("清理未确认");
  });

  it("点击日志和取消按钮应当正确触发事件，且取消中时禁用取消按钮", async () => {
    const wrapper = mount(BackgroundTaskItem, {
      props: {
        task: baseTask,
        isCancelling: false,
      },
    });

    await wrapper.find('[data-testid="task-view-logs-btn"]').trigger("click");
    expect(wrapper.emitted("viewLogs")).toEqual([[baseTask.task_id]]);

    await wrapper.find('[data-testid="task-cancel-btn"]').trigger("click");
    expect(wrapper.emitted("cancel")).toEqual([[baseTask.task_id]]);

    // 设置 isCancelling = true 时
    await wrapper.setProps({ isCancelling: true });
    const cancelBtn = wrapper.find('[data-testid="task-cancel-btn"]');
    expect(cancelBtn.attributes("disabled")).toBeDefined();
  });
});
