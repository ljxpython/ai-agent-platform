import { beforeEach, describe, expect, it, vi } from "vitest";
import { platformHttpClient } from "@/services/http/client";
import {
  cancelBackgroundTask,
  getBackgroundTask,
  getBackgroundTaskOutput,
  listBackgroundTasks,
} from "./background-tasks.service";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("background-tasks.service", () => {
  const projectId = "proj-test-123";
  const threadId = "3f435938-f5f2-42df-9a31-33839c623671";
  const taskId = "4ce62cd1-4d07-493e-89ed-d107bdddc8dd";

  const mockTask = {
    version: 1,
    task_id: taskId,
    thread_id: threadId,
    graph_id: "showcase_demo",
    origin_run_id: "734d3540-a0f8-4550-bdf7-f0fa8d0ae0e4",
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
      retained_bytes: 128,
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
  });

  it("listBackgroundTasks 成功返回校验通过的列表数据", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: {
        version: 1,
        thread_id: threadId,
        items: [mockTask],
        next_cursor: null,
        has_unresolved: true,
        latest_delivery_run_id: null,
      },
    });

    const result = await listBackgroundTasks(projectId, threadId, {
      limit: 10,
    });
    expect(result.items).toHaveLength(1);
    expect(result.has_unresolved).toBe(true);
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      `/api/langgraph/threads/${threadId}/background-tasks`,
      expect.objectContaining({
        headers: { "x-project-id": projectId },
        params: { limit: 10 },
      }),
    );
  });

  it("getBackgroundTask 成功读取单任务详情", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: mockTask,
    });

    const result = await getBackgroundTask(projectId, threadId, taskId);
    expect(result.task_id).toBe(taskId);
    expect(result.status).toBe("running");
  });

  it("getBackgroundTaskOutput 成功获取文本日志", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: {
        version: 1,
        task_id: taskId,
        thread_id: threadId,
        available: true,
        text: "hello log",
        retained_bytes: 9,
        omitted_bytes: 0,
        truncated: false,
        updated_at: "2026-10-09T01:00:05Z",
      },
    });

    const result = await getBackgroundTaskOutput(projectId, threadId, taskId);
    expect(result.text).toBe("hello log");
  });

  it("cancelBackgroundTask 带上 Idempotency-Key 并返回 202 响应", async () => {
    vi.mocked(platformHttpClient.post).mockResolvedValueOnce({
      data: {
        ...mockTask,
        status: "cancel_requested",
      },
    });

    const key = "idem-key-999";
    const result = await cancelBackgroundTask(projectId, threadId, taskId, key);
    expect(result.status).toBe("cancel_requested");
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      `/api/langgraph/threads/${threadId}/background-tasks/${taskId}/cancel`,
      {},
      expect.objectContaining({
        headers: {
          "x-project-id": projectId,
          "Idempotency-Key": key,
        },
      }),
    );
  });
});
