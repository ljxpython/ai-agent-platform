import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useBackgroundTasks } from "./useBackgroundTasks";
import * as service from "@/services/threads/background-tasks.service";
import type { TaskV1 } from "@/modules/chat/background-tasks/types";

vi.mock("@/services/threads/background-tasks.service");

describe("useBackgroundTasks", () => {
  const projectId = ref("proj-1");
  const threadId = ref("thread-1");

  const mockRunningTask: TaskV1 = {
    version: 1,
    task_id: "task-1111",
    thread_id: "thread-1",
    graph_id: "showcase",
    origin_run_id: "origin-run-1",
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

  beforeEach(() => {
    vi.clearAllMocks();
    projectId.value = "proj-1";
    threadId.value = "thread-1";
  });

  it("正确加载任务并派生活跃任务状态", async () => {
    vi.mocked(service.listBackgroundTasks).mockResolvedValueOnce({
      version: 1,
      thread_id: "thread-1",
      items: [mockRunningTask],
      next_cursor: null,
      has_unresolved: true,
      latest_delivery_run_id: null,
    });

    const composable = useBackgroundTasks(projectId, threadId);
    await vi.waitFor(() => expect(composable.loading.value).toBe(false));

    expect(composable.tasks.value).toHaveLength(1);
    expect(composable.hasActiveBackgroundTasks.value).toBe(true);
    expect(composable.activeTaskCount.value).toBe(1);
    expect(composable.hasUnresolved.value).toBe(true);
  });

  it("发现新完成 Run 时调用 onRunDiscovered", async () => {
    const onRunDiscovered = vi.fn();
    const taskWithDelivery: TaskV1 = {
      ...mockRunningTask,
      status: "succeeded",
      delivery: {
        state: "accepted",
        event_id: "evt-1",
        run_id: "run-delivered-999",
        reason_code: null,
      },
    };

    vi.mocked(service.listBackgroundTasks).mockResolvedValueOnce({
      version: 1,
      thread_id: "thread-1",
      items: [taskWithDelivery],
      next_cursor: null,
      has_unresolved: false,
      latest_delivery_run_id: "run-delivered-999",
    });

    useBackgroundTasks(projectId, threadId, { onRunDiscovered });
    await vi.waitFor(() =>
      expect(onRunDiscovered).toHaveBeenCalledWith("run-delivered-999"),
    );
    expect(onRunDiscovered).toHaveBeenCalledTimes(1);
  });

  it("打开与读取日志，关闭时重置", async () => {
    vi.mocked(service.listBackgroundTasks).mockResolvedValueOnce({
      version: 1,
      thread_id: "thread-1",
      items: [mockRunningTask],
      next_cursor: null,
      has_unresolved: false,
      latest_delivery_run_id: null,
    });
    vi.mocked(service.getBackgroundTaskOutput).mockResolvedValueOnce({
      version: 1,
      task_id: "task-1111",
      thread_id: "thread-1",
      available: true,
      text: "running test suite",
      retained_bytes: 18,
      omitted_bytes: 0,
      truncated: false,
      updated_at: "2026-10-09T01:00:05Z",
    });

    const composable = useBackgroundTasks(projectId, threadId);
    await composable.openTaskLog("task-1111");

    expect(composable.activeLogTaskId.value).toBe("task-1111");
    expect(composable.logOutput.value?.text).toBe("running test suite");

    composable.closeTaskLog();
    expect(composable.activeLogTaskId.value).toBeNull();
    expect(composable.logOutput.value).toBeNull();
  });

  it("取消任务时置位单飞锁并更新本地状态", async () => {
    vi.mocked(service.listBackgroundTasks).mockResolvedValue({
      version: 1,
      thread_id: "thread-1",
      items: [mockRunningTask],
      next_cursor: null,
      has_unresolved: false,
      latest_delivery_run_id: null,
    });
    vi.mocked(service.cancelBackgroundTask).mockResolvedValueOnce({
      ...mockRunningTask,
      status: "cancel_requested",
    });

    const composable = useBackgroundTasks(projectId, threadId);
    await vi.waitFor(() => expect(composable.tasks.value.length).toBe(1));

    await composable.cancelTask("task-1111");
    expect(composable.tasks.value[0]?.status).toBe("cancel_requested");
    expect(service.cancelBackgroundTask).toHaveBeenCalledWith(
      "proj-1",
      "thread-1",
      "task-1111",
      expect.stringContaining("cancel-task-1111-"),
    );
  });
});
