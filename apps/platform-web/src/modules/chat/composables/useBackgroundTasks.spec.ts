import { beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import { useBackgroundTasks } from "./useBackgroundTasks";
import * as service from "@/services/threads/background-tasks.service";
import type { TaskV1 } from "@/modules/chat/background-tasks/types";
import type { WorkspaceCapabilities } from "@/types/workspace";

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

  describe("能力矩阵与门禁 (ABF01)", () => {
    it("true/false (Local/启动关闭): 保留任务查询能力、日志与授权取消", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: true,
        background_tasks_start_enabled: false,
      });

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
        text: "log output test",
        retained_bytes: 15,
        omitted_bytes: 0,
        truncated: false,
        updated_at: "2026-10-09T01:00:05Z",
      });
      vi.mocked(service.cancelBackgroundTask).mockResolvedValueOnce({
        ...mockRunningTask,
        status: "cancel_requested",
      });

      const composable = useBackgroundTasks(projectId, threadId, {
        capabilities: caps,
      });

      expect(composable.queryEnabled.value).toBe(true);
      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(1));

      // 验证能够正常查询已有任务
      expect(service.listBackgroundTasks).toHaveBeenCalledTimes(1);

      // 验证能正常查看日志
      await composable.openTaskLog("task-1111");
      expect(composable.activeLogTaskId.value).toBe("task-1111");
      expect(composable.logOutput.value?.text).toBe("log output test");
      composable.closeTaskLog();
      expect(composable.activeLogTaskId.value).toBeNull();

      // 验证能正常授权取消并置位单飞锁
      await composable.cancelTask("task-1111");
      expect(composable.tasks.value[0]?.status).toBe("cancel_requested");
      expect(service.cancelBackgroundTask).toHaveBeenCalledWith(
        "proj-1",
        "thread-1",
        "task-1111",
        expect.stringContaining("cancel-task-1111-"),
      );
    });

    it("true/true (Docker/全开): 正常加载任务并触发 onRunDiscovered", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: true,
        background_tasks_start_enabled: true,
      });
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

      const composable = useBackgroundTasks(projectId, threadId, {
        capabilities: caps,
        onRunDiscovered,
      });

      expect(composable.queryEnabled.value).toBe(true);
      await vi.waitFor(() =>
        expect(onRunDiscovered).toHaveBeenCalledWith("run-delivered-999"),
      );
      expect(composable.tasks.value).toHaveLength(1);
      expect(composable.hasActiveBackgroundTasks.value).toBe(false);
    });

    it("false/false (无任务存储/未接入): 彻底禁用，零任务请求", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: false,
        background_tasks_start_enabled: false,
      });

      const composable = useBackgroundTasks(projectId, threadId, {
        capabilities: caps,
      });

      expect(composable.queryEnabled.value).toBe(false);
      // 零任务请求
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();
      expect(composable.tasks.value).toEqual([]);
      expect(composable.hasActiveBackgroundTasks.value).toBe(false);

      // 手动刷新亦不发起请求
      await composable.refresh();
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();

      // 日志和取消操作防守
      await composable.openTaskLog("task-1111");
      expect(service.getBackgroundTaskOutput).not.toHaveBeenCalled();
      await composable.cancelTask("task-1111");
      expect(service.cancelBackgroundTask).not.toHaveBeenCalled();
    });

    it("字段缺省 (undefined / null / {}): 按 false 处理，零任务请求", async () => {
      // 1. 完全不传 options
      const composableDefault = useBackgroundTasks(projectId, threadId);
      expect(composableDefault.queryEnabled.value).toBe(false);
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();
      expect(composableDefault.tasks.value).toEqual([]);

      // 2. 传 null
      const capsNull = ref<WorkspaceCapabilities | null>(null);
      const composableNull = useBackgroundTasks(projectId, threadId, {
        capabilities: capsNull,
      });
      expect(composableNull.queryEnabled.value).toBe(false);
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();

      // 3. 传 {} (无 background_tasks 字段)
      const capsEmpty = ref<WorkspaceCapabilities>({ workspace: true });
      const composableEmpty = useBackgroundTasks(projectId, threadId, {
        capabilities: capsEmpty,
      });
      expect(composableEmpty.queryEnabled.value).toBe(false);
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();
    });

    it("能力动态变化: false -> true 自动加载，true -> false 立即清理旧作用域", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: false,
        background_tasks_start_enabled: false,
      });

      vi.mocked(service.listBackgroundTasks).mockResolvedValue({
        version: 1,
        thread_id: "thread-1",
        items: [mockRunningTask],
        next_cursor: null,
        has_unresolved: false,
        latest_delivery_run_id: null,
      });

      const composable = useBackgroundTasks(projectId, threadId, {
        capabilities: caps,
      });

      expect(composable.queryEnabled.value).toBe(false);
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();

      // 动态开启
      caps.value = {
        workspace: true,
        background_tasks: true,
        background_tasks_start_enabled: false,
      };
      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(1));
      expect(service.listBackgroundTasks).toHaveBeenCalledTimes(1);

      // 动态关闭 -> 作用域被清空
      caps.value = {
        workspace: true,
        background_tasks: false,
        background_tasks_start_enabled: false,
      };
      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(0));
      expect(composable.queryEnabled.value).toBe(false);
      expect(composable.hasUnresolved.value).toBe(false);
    });

    it("切换会话: 重置作用域且不残留上一会话的任务", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: true,
        background_tasks_start_enabled: true,
      });

      vi.mocked(service.listBackgroundTasks).mockImplementation(
        async (_pid, tid) => {
          if (tid === "thread-2") {
            return {
              version: 1,
              thread_id: "thread-2",
              items: [],
              next_cursor: null,
              has_unresolved: false,
              latest_delivery_run_id: null,
            };
          }
          return {
            version: 1,
            thread_id: "thread-1",
            items: [mockRunningTask],
            next_cursor: null,
            has_unresolved: false,
            latest_delivery_run_id: null,
          };
        },
      );

      const composable = useBackgroundTasks(projectId, threadId, {
        capabilities: caps,
      });

      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(1));

      // 切换到 thread-2 (mock 返回空列表)
      threadId.value = "thread-2";
      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(0));
      expect(service.listBackgroundTasks).toHaveBeenCalledWith(
        "proj-1",
        "thread-2",
        { limit: 50 },
        expect.any(AbortSignal),
      );
    });

    it("作用域卸载 (onScopeDispose): 停止定时器与中止在途请求", async () => {
      const caps = ref<WorkspaceCapabilities>({
        workspace: true,
        background_tasks: true,
        background_tasks_start_enabled: true,
      });

      vi.mocked(service.listBackgroundTasks).mockResolvedValue({
        version: 1,
        thread_id: "thread-1",
        items: [mockRunningTask],
        next_cursor: null,
        has_unresolved: false,
        latest_delivery_run_id: null,
      });

      let composable!: ReturnType<typeof useBackgroundTasks>;
      const scope = effectScope();
      scope.run(() => {
        composable = useBackgroundTasks(projectId, threadId, {
          capabilities: caps,
        });
      });

      await vi.waitFor(() => expect(composable.tasks.value).toHaveLength(1));

      // 停止 scope
      scope.stop();

      // 卸载后手动调用 refresh 不应重新触发有效加载
      vi.clearAllMocks();
      await composable.refresh();
      expect(service.listBackgroundTasks).not.toHaveBeenCalled();
    });
  });
});
