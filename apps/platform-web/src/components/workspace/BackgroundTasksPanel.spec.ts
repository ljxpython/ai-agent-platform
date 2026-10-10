import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { ref } from "vue";
import BackgroundTasksPanel from "./BackgroundTasksPanel.vue";
import type { TaskV1 } from "@/modules/chat/background-tasks/types";
import type { UseBackgroundTasksReturn } from "@/modules/chat/composables/useBackgroundTasks";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe("BackgroundTasksPanel.vue", () => {
  const mockTask: TaskV1 = {
    version: 1,
    task_id: "task-test-1111",
    thread_id: "thread-test-1",
    graph_id: "showcase",
    origin_run_id: "origin-1",
    status: "running",
    reason_code: null,
    exit_code: null,
    created_at: "2026-10-09T01:00:00Z",
    started_at: "2026-10-09T01:00:01Z",
    finished_at: null,
    deadline_at: "2026-10-09T01:15:00Z",
    updated_at: "2026-10-09T01:00:05Z",
    cleanup_state: "pending",
    output: {
      available: true,
      retained_bytes: 100,
      omitted_bytes: 0,
      truncated: false,
      updated_at: "2026-10-09T01:00:05Z",
    },
    delivery: {
      state: "not_ready",
      event_id: null,
      run_id: null,
      reason_code: null,
    },
    allowed_actions: ["read", "logs", "cancel"],
  };

  function createMockTaskState(
    overrides?: Partial<UseBackgroundTasksReturn>,
  ): UseBackgroundTasksReturn {
    return {
      tasks: ref([mockTask]),
      loading: ref(false),
      refreshing: ref(false),
      error: ref(null),
      nextCursor: ref(null),
      hasUnresolved: ref(true),
      latestDeliveryRunId: ref(null),
      hasActiveBackgroundTasks: ref(true),
      activeTaskCount: ref(1),
      activeLogTaskId: ref(null),
      logOutput: ref(null),
      loadingLog: ref(false),
      logError: ref(null),
      openTaskLog: vi.fn(),
      closeTaskLog: vi.fn(),
      fetchTaskLog: vi.fn(),
      cancellingTaskIds: ref(new Set()),
      cancelTask: vi.fn(),
      refresh: vi.fn(),
      ...overrides,
    };
  }

  it("正确渲染任务列表及卡片内容", () => {
    const mockState = createMockTaskState();
    const wrapper = mount(BackgroundTasksPanel, {
      props: {
        projectId: "p1",
        threadId: "t1",
      },
      global: {
        provide: {
          backgroundTasks: mockState,
        },
      },
    });

    expect(wrapper.text()).toContain("task-tes");
    expect(wrapper.text()).toContain("运行中");
    expect(wrapper.text()).toContain("日志");
    expect(wrapper.text()).toContain("取消");
  });

  it("展示空状态提示", () => {
    const mockState = createMockTaskState({
      tasks: ref([]),
      activeTaskCount: ref(0),
    });
    const wrapper = mount(BackgroundTasksPanel, {
      props: {
        projectId: "p1",
        threadId: "t1",
      },
      global: {
        provide: {
          backgroundTasks: mockState,
        },
      },
    });

    expect(wrapper.text()).toContain("暂无后台长任务");
  });

  it("点击查看日志触发 openTaskLog", async () => {
    const mockState = createMockTaskState();
    const wrapper = mount(BackgroundTasksPanel, {
      props: {
        projectId: "p1",
        threadId: "t1",
      },
      global: {
        provide: {
          backgroundTasks: mockState,
        },
      },
    });

    const logBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("日志"));
    expect(logBtn).toBeDefined();
    await logBtn?.trigger("click");
    expect(mockState.openTaskLog).toHaveBeenCalledWith("task-test-1111");
  });
});
