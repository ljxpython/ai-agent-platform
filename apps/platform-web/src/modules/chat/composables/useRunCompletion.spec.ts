import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useRunCompletion } from "./useRunCompletion";
import * as completionService from "@/services/threads/completion.service";

vi.mock("@/services/threads/completion.service", () => ({
  getRunCompletion: vi.fn(),
}));

describe("useRunCompletion composable", () => {
  const threadId = "5752312c-5893-4ba9-914e-d4b7748f42b8";
  const runId = "cf4d5956-c579-459d-a106-1c3fb05a639a";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("正常非运行态下自动查询 completion 并解析失败呈现", async () => {
    const threadRef = ref<string | null>(threadId);
    const runRef = ref<string | null>(runId);
    const isRunningRef = ref(false);

    vi.mocked(completionService.getRunCompletion).mockResolvedValueOnce({
      version: 1,
      thread_id: threadId,
      run_id: runId,
      availability: "available",
      completion: {
        event_id: "354bd564-c2b7-4d38-b538-f53f53a8d37a",
        graph_id: "agent_1",
        status: "error",
        reason: "business_error",
        reason_code: "runtime.model.retry_exhausted",
        model_error_code: "provider_overloaded",
        notification_code: "run_failed_provider_overloaded",
        occurred_at: "2026-10-09T04:52:44.707165Z",
        can_mark_read: false,
        read_at: null,
      },
      request_id: "req_comp",
    });

    const { data, failurePresentation } = useRunCompletion({
      threadId: threadRef,
      runId: runRef,
      isRunning: isRunningRef,
    });

    await vi.waitFor(() => {
      expect(data.value).toBeTruthy();
    });

    expect(data.value?.availability).toBe("available");
    expect(failurePresentation.value?.title).toBe("模型服务繁忙");
    expect(failurePresentation.value?.actionType).toBe("switch_model");
  });

  it("当正在运行中 (isRunning === true) 时坚决不发起查询", async () => {
    const threadRef = ref<string | null>(threadId);
    const runRef = ref<string | null>(runId);
    const isRunningRef = ref(true);

    const { data, loading } = useRunCompletion({
      threadId: threadRef,
      runId: runRef,
      isRunning: isRunningRef,
    });

    expect(completionService.getRunCompletion).not.toHaveBeenCalled();
    expect(data.value).toBeNull();
    expect(loading.value).toBe(false);
  });

  it("快速切换 Run 时触发代数防竞态，旧响应不覆盖新 Run", async () => {
    const threadRef = ref<string | null>(threadId);
    const runRef = ref<string | null>(runId);
    const isRunningRef = ref(false);

    let resolveFirst: (v: any) => void;
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    vi.mocked(completionService.getRunCompletion).mockImplementationOnce(
      () => firstPromise as any,
    );

    const { data } = useRunCompletion({
      threadId: threadRef,
      runId: runRef,
      isRunning: isRunningRef,
    });

    // 快速切换到 runId 2
    const runId2 = "22222222-3333-4444-5555-666666666666";
    vi.mocked(completionService.getRunCompletion).mockResolvedValueOnce({
      version: 1,
      thread_id: threadId,
      run_id: runId2,
      availability: "available",
      completion: {
        event_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        graph_id: "agent_2",
        status: "success",
        reason: "completed",
        reason_code: null,
        model_error_code: null,
        notification_code: null,
        occurred_at: "2026-10-09T05:00:00.000000Z",
        can_mark_read: false,
        read_at: null,
      },
      request_id: "req_2",
    });

    runRef.value = runId2;

    await vi.waitFor(() => {
      expect(data.value?.run_id).toBe(runId2);
    });

    // 此时旧请求 resolve
    resolveFirst!({
      version: 1,
      thread_id: threadId,
      run_id: runId,
      availability: "available",
      completion: {
        event_id: "old-event",
        graph_id: "agent_old",
        status: "error",
        reason: "business_error",
        reason_code: null,
        model_error_code: null,
        notification_code: null,
        occurred_at: "2026-10-09T04:00:00.000000Z",
        can_mark_read: false,
        read_at: null,
      },
      request_id: "req_old",
    });

    // 验证：当前数据依然是 runId2，未被旧数据覆盖！
    expect(data.value?.run_id).toBe(runId2);
  });
});
